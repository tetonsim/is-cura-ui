import copy
import json
import math
import numpy

from typing import Dict, List

from PyQt5.QtCore import pyqtSignal, pyqtProperty, pyqtSlot
from PyQt5.QtCore import QObject, QUrl, QAbstractListModel

from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Operations.SetParentOperation import SetParentOperation
from cura.Scene.ZOffsetDecorator import ZOffsetDecorator

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Logger import Logger
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Settings.SettingInstance import SettingInstance
from UM.Scene.SceneNode import SceneNode
from UM.Scene.GroupDecorator import GroupDecorator
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Math.Matrix import Matrix
from UM.Qt.Duration import Duration
from UM.Signal import Signal

from .SmartSliceCloudStatus import SmartSliceCloudStatus
from .SmartSliceProperty import SmartSlicePropertyColor
from .SmartSliceJobHandler import SmartSliceJobHandler
from .SmartSliceDecorator import SmartSliceAddedDecorator, SmartSliceRemovedDecorator
from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements
from .select_tool.SmartSliceSelectTool import SmartSliceSelectTool
from .stage.ui.ResultTable import ResultsTableHeader, ResultTableData
from .utils import getNodeActiveExtruder
from .utils import getModifierMeshes
from .utils import getPrintableNodes
from .components import Dialog

import pywim

i18n_catalog = i18nCatalog("smartslice")

# Serves as a bridge between the main UI in QML and data regarding Smart Slice
class SmartSliceCloudProxy(QObject):
    def __init__(self) -> None:
        super().__init__()

        # Primary Button (Slice/Validate/Optimize)
        self._sliceStatusEnum = SmartSliceCloudStatus.Errors
        self._sliceStatus = "_Status"
        self._sliceHint = "_Hint"
        self._sliceButtonText = "_ButtonText"
        self._sliceButtonEnabled = False
        self._sliceButtonVisible = True
        self._sliceButtonFillWidth = True
        self._sliceIconImage = ""
        self._sliceIconVisible = False
        self._sliceInfoOpen = False
        self._errors = {}

        self._job_progress = 0
        self._progress_bar_visible = False

        # Secondary Button (Preview/Cancel)
        self._secondaryButtonText = "_SecondaryText"
        self._secondaryButtonFillWidth = False
        self._secondaryButtonVisible = False

        self._loadDialog = Dialog.Dialog()
        self._resultsTableDialog = Dialog.Dialog()

        # Proxy Values (DO NOT USE DIRECTLY)
        self._targetFactorOfSafety = 2.0
        self._targetMaximalDisplacement = 1.0

        self._safetyFactorColor = "#000000"
        self._maxDisplaceColor = "#000000"

        #  Use-case & Requirements Cache
        self.reqsMaxDeflect  = self._targetMaximalDisplacement

        # Results table
        self._resultsTable = ResultTableData()
        self._resultsTable.updateDisplaySignal.connect(self.updatePropertiesFromResults)
        self._resultsTable.resultsUpdated.connect(self._resultsTableUpdated)

        # Properties (mainly) for the sliceinfo widget
        self._resultSafetyFactor = 0.0 #copy.copy(self._targetFactorOfSafety)
        self._resultMaximalDisplacement = 0.0 #copy.copy(self._targetMaximalDisplacement)
        self._resultTimeTotal = Duration()
        self._resultTimeInfill = Duration()
        self._resultTimeInnerWalls = Duration()
        self._resultTimeOuterWalls = Duration()
        self._resultTimeRetractions = Duration()
        self._resultTimeSkin = Duration()
        self._resultTimeSkirt = Duration()
        self._resultTimeTravel = Duration()
        self._resultTimes = (
            self._resultTimeInfill,
            self._resultTimeInnerWalls,
            self._resultTimeOuterWalls,
            self._resultTimeRetractions,
            self._resultTimeSkin,
            self._resultTimeSkirt,
            self._resultTimeTravel
        )
        self._percentageTimeInfill = 0.0
        self._percentageTimeInnerWalls = 0.0
        self._percentageTimeOuterWalls = 0.0
        self._percentageTimeRetractions = 0.0
        self._percentageTimeSkin = 0.0
        self._percentageTimeSkirt = 0.0
        self._percentageTimeTravel = 0.0

        self.resultTimeInfillChanged.connect(self._onResultTimeChanged)
        self.resultTimeInnerWallsChanged.connect(self._onResultTimeChanged)
        self.resultTimeOuterWallsChanged.connect(self._onResultTimeChanged)
        self.resultTimeRetractionsChanged.connect(self._onResultTimeChanged)
        self.resultTimeSkinChanged.connect(self._onResultTimeChanged)
        self.resultTimeSkirtChanged.connect(self._onResultTimeChanged)
        self.resultTimeTravelChanged.connect(self._onResultTimeChanged)

        self._materialName = None
        self._materialCost = 0.0
        self._materialLength = 0.0
        self._materialWeight = 0.0

    # Properties (mainly) for the sliceinfo widget

    # For main window dialog
    closeSavePromptClicked = pyqtSignal()
    escapeSavePromptClicked = pyqtSignal()
    savePromptClicked = pyqtSignal()

    #
    #   SLICE BUTTON WINDOW
    #
    sliceButtonClicked = pyqtSignal()
    secondaryButtonClicked = pyqtSignal()
    sliceStatusChanged = pyqtSignal()
    sliceStatusEnumChanged = pyqtSignal()
    sliceButtonFillWidthChanged = pyqtSignal()

    smartSliceErrorsChanged = pyqtSignal()
    sliceHintChanged = pyqtSignal()
    sliceButtonVisibleChanged = pyqtSignal()
    sliceButtonEnabledChanged = pyqtSignal()
    sliceButtonTextChanged = pyqtSignal()
    sliceInfoOpenChanged = pyqtSignal()

    progressBarVisibleChanged = pyqtSignal()
    jobProgressChanged = pyqtSignal()

    secondaryButtonTextChanged = pyqtSignal()
    secondaryButtonVisibleChanged = pyqtSignal()
    secondaryButtonFillWidthChanged = pyqtSignal()

    resultsTableUpdated = pyqtSignal()

    optimizationResultAppliedToScene = Signal()

    @pyqtProperty(QObject, constant=True)
    def loadDialog(self):
        return self._loadDialog

    @pyqtProperty(QObject, notify=resultsTableUpdated)
    def resultsTableDialog(self):
        return self._resultsTableDialog

    @pyqtProperty(bool, notify=sliceStatusEnumChanged)
    def isValidated(self):
        return self._sliceStatusEnum in SmartSliceCloudStatus.optimizable()

    @pyqtProperty(bool, notify=sliceStatusEnumChanged)
    def isOptimized(self):
        return self._sliceStatusEnum is SmartSliceCloudStatus.Optimized

    @pyqtProperty(bool, notify=sliceStatusEnumChanged)
    def errorsExist(self):
        return self._sliceStatusEnum is SmartSliceCloudStatus.Errors

    @pyqtProperty(int, notify=sliceStatusEnumChanged)
    def sliceStatusEnum(self):
        return self._sliceStatusEnum

    @sliceStatusEnum.setter
    def sliceStatusEnum(self, value):
        if self._sliceStatusEnum is not value:
            self._sliceStatusEnum = value
            self.sliceStatusEnumChanged.emit()

    @pyqtProperty("QVariantMap", notify=smartSliceErrorsChanged)
    def errors(self) -> Dict[str, str]:
        return self._errors

    @errors.setter
    def errors(self, value: Dict[str, str]):
        self._errors = value
        self.smartSliceErrorsChanged.emit()

    @pyqtProperty(str, notify=sliceStatusChanged)
    def sliceStatus(self):
        return self._sliceStatus

    @sliceStatus.setter
    def sliceStatus(self, value):
        if self._sliceStatus is not value:
            self._sliceStatus = value
            self.sliceStatusChanged.emit()

    @pyqtProperty(str, notify=sliceHintChanged)
    def sliceHint(self):
        return self._sliceHint

    @sliceHint.setter
    def sliceHint(self, value):
        if self._sliceHint is not value:
            self._sliceHint = value
            self.sliceHintChanged.emit()

    @pyqtProperty(str, notify=sliceButtonTextChanged)
    def sliceButtonText(self):
        return self._sliceButtonText

    @sliceButtonText.setter
    def sliceButtonText(self, value):
        if self._sliceButtonText is not value:
            self._sliceButtonText = value
            self.sliceButtonTextChanged.emit()

    @pyqtProperty(bool, notify=sliceInfoOpenChanged)
    def sliceInfoOpen(self):
        return self._sliceInfoOpen

    @sliceInfoOpen.setter
    def sliceInfoOpen(self, value):
        if self._sliceInfoOpen is not value:
            self._sliceInfoOpen = value
            self.sliceInfoOpenChanged.emit()

    @pyqtProperty(str, notify=secondaryButtonTextChanged)
    def secondaryButtonText(self):
        return self._secondaryButtonText

    @secondaryButtonText.setter
    def secondaryButtonText(self, value):
        if self._secondaryButtonText is not value:
            self._secondaryButtonText = value
            self.secondaryButtonTextChanged.emit()

    @pyqtProperty(bool, notify=sliceButtonEnabledChanged)
    def sliceButtonEnabled(self):
        return self._sliceButtonEnabled

    @sliceButtonEnabled.setter
    def sliceButtonEnabled(self, value):
        if self._sliceButtonEnabled is not value:
            self._sliceButtonEnabled = value
            self.sliceButtonEnabledChanged.emit()

    @pyqtProperty(bool, notify=sliceButtonVisibleChanged)
    def sliceButtonVisible(self):
        return self._sliceButtonVisible

    @sliceButtonVisible.setter
    def sliceButtonVisible(self, value):
        if self._sliceButtonVisible is not value:
            self._sliceButtonVisible = value
            self.sliceButtonVisibleChanged.emit()

    @pyqtProperty(bool, notify=sliceButtonFillWidthChanged)
    def sliceButtonFillWidth(self):
        return self._sliceButtonFillWidth

    @sliceButtonFillWidth.setter
    def sliceButtonFillWidth(self, value):
        if self._sliceButtonFillWidth is not value:
            self._sliceButtonFillWidth = value
            self.sliceButtonFillWidthChanged.emit()

    @pyqtProperty(bool, notify=secondaryButtonFillWidthChanged)
    def secondaryButtonFillWidth(self):
        return self._secondaryButtonFillWidth

    @secondaryButtonFillWidth.setter
    def secondaryButtonFillWidth(self, value):
        if self._secondaryButtonFillWidth is not value:
            self._secondaryButtonFillWidth = value
            self.secondaryButtonFillWidthChanged.emit()

    @pyqtProperty(bool, notify=secondaryButtonVisibleChanged)
    def secondaryButtonVisible(self):
        return self._secondaryButtonVisible

    @secondaryButtonVisible.setter
    def secondaryButtonVisible(self, value):
        if self._secondaryButtonVisible is not value:
            self._secondaryButtonVisible = value
            self.secondaryButtonVisibleChanged.emit()

    sliceIconImageChanged = pyqtSignal()

    @pyqtProperty(QUrl, notify=sliceIconImageChanged)
    def sliceIconImage(self):
        return self._sliceIconImage

    @sliceIconImage.setter
    def sliceIconImage(self, value):
        if self._sliceIconImage is not value:
            self._sliceIconImage = value
            self.sliceIconImageChanged.emit()

    sliceIconVisibleChanged = pyqtSignal()

    @pyqtProperty(bool, notify=sliceIconVisibleChanged)
    def sliceIconVisible(self):
        return self._sliceIconVisible

    @sliceIconVisible.setter
    def sliceIconVisible(self, value):
        if self._sliceIconVisible is not value:
            self._sliceIconVisible = value
            self.sliceIconVisibleChanged.emit()

    resultSafetyFactorChanged = pyqtSignal()
    targetSafetyFactorChanged = pyqtSignal()
    updateTargetUi = pyqtSignal()

    @pyqtProperty(float, notify=targetSafetyFactorChanged)
    def targetSafetyFactor(self):
        return SmartSliceRequirements.getInstance().targetSafetyFactor

    @pyqtProperty(float, notify=resultSafetyFactorChanged)
    def resultSafetyFactor(self):
        return self._resultSafetyFactor

    @resultSafetyFactor.setter
    def resultSafetyFactor(self, value):
        if self._resultSafetyFactor != value:
            self._resultSafetyFactor = value
            self.resultSafetyFactorChanged.emit()

    @pyqtProperty(int, notify=jobProgressChanged)
    def jobProgress(self):
        return self._job_progress

    @jobProgress.setter
    def jobProgress(self, value):
        if self._job_progress != value:
            self._job_progress = value
            self.jobProgressChanged.emit()

    @pyqtProperty(bool, notify=progressBarVisibleChanged)
    def progressBarVisible(self):
        return self._progress_bar_visible

    @progressBarVisible.setter
    def progressBarVisible(self, value):
        if self._progress_bar_visible is not value:
            self._progress_bar_visible = value
            self.progressBarVisibleChanged.emit()

    # Max Displacement

    targetMaximalDisplacementChanged = pyqtSignal()
    resultMaximalDisplacementChanged = pyqtSignal()

    @pyqtProperty(float, notify=targetMaximalDisplacementChanged)
    def targetMaximalDisplacement(self):
        return SmartSliceRequirements.getInstance().maxDisplacement

    @pyqtProperty(float, notify=resultMaximalDisplacementChanged)
    def resultMaximalDisplacement(self):
        return self._resultMaximalDisplacement

    @resultMaximalDisplacement.setter
    def resultMaximalDisplacement(self, value):
        if self._resultMaximalDisplacement != value:
            self._resultMaximalDisplacement = value
            self.resultMaximalDisplacementChanged.emit()

    #
    #   SMART SLICE RESULTS
    #

    @pyqtProperty(QAbstractListModel, notify=resultsTableUpdated)
    def resultsTable(self):
        return self._resultsTable

    def _resultsTableUpdated(self):
        self.resultsTableUpdated.emit()

    resultTimeTotalChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeTotalChanged)
    def resultTimeTotal(self):
        return self._resultTimeTotal

    @resultTimeTotal.setter
    def resultTimeTotal(self, value):
        if self._resultTimeTotal != value:
            self._resultTimeTotal = value
            self.resultTimeTotalChanged.emit()

    resultTimeInfillChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeInfillChanged)
    def resultTimeInfill(self):
        return self._resultTimeInfill

    @resultTimeInfill.setter
    def resultTimeInfill(self, value):
        if self._resultTimeInfill != value:
            self._resultTimeInfill = value
            self.resultTimeInfillChanged.emit()

    resultTimeInnerWallsChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeInnerWallsChanged)
    def resultTimeInnerWalls(self):
        return self._resultTimeInnerWalls

    @resultTimeInnerWalls.setter
    def resultTimeInnerWalls(self, value):
        if self._resultTimeInnerWalls != value:
            self._resultTimeInnerWalls = value
            self.resultTimeInnerWallsChanged.emit()

    resultTimeOuterWallsChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeOuterWallsChanged)
    def resultTimeOuterWalls(self):
        return self._resultTimeOuterWalls

    @resultTimeOuterWalls.setter
    def resultTimeOuterWalls(self, value):
        if self._resultTimeOuterWalls !=value:
            self._resultTimeOuterWalls = value
            self.resultTimeOuterWallsChanged.emit()

    resultTimeRetractionsChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeRetractionsChanged)
    def resultTimeRetractions(self):
        return self._resultTimeRetractions

    @resultTimeRetractions.setter
    def resultTimeRetractions(self, value):
        if self._resultTimeRetractions != value:
            self._resultTimeRetractions = value
            self.resultTimeRetractionsChanged.emit()

    resultTimeSkinChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeSkinChanged)
    def resultTimeSkin(self):
        return self._resultTimeSkin

    @resultTimeSkin.setter
    def resultTimeSkin(self, value):
        if self._resultTimeSkin != value:
            self._resultTimeSkin = value
            self.resultTimeSkinChanged.emit()

    resultTimeSkirtChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeSkirtChanged)
    def resultTimeSkirt(self):
        return self._resultTimeSkirt

    @resultTimeSkirt.setter
    def resultTimeSkirt(self, value):
        if self._resultTimeSkirt != value:
            self._resultTimeSkirt = value
            self.resultTimeSkirtChanged.emit()

    resultTimeTravelChanged = pyqtSignal()

    @pyqtProperty(QObject, notify=resultTimeTravelChanged)
    def resultTimeTravel(self):
        return self._resultTimeTravel

    @resultTimeTravel.setter
    def resultTimeTravel(self, value):
        if self._resultTimeTravel != value:
            self._resultTimeTravel = value
            self.resultTimeTravelChanged.emit()

    percentageTimeInfillChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeInfillChanged)
    def percentageTimeInfill(self):
        return self._percentageTimeInfill

    @percentageTimeInfill.setter
    def percentageTimeInfill(self, value):
        if not self._percentageTimeInfill == value:
            self._percentageTimeInfill = value
            self.percentageTimeInfillChanged.emit()

    percentageTimeInnerWallsChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeInnerWallsChanged)
    def percentageTimeInnerWalls(self):
        return self._percentageTimeInnerWalls

    @percentageTimeInnerWalls.setter
    def percentageTimeInnerWalls(self, value):
        if not self._percentageTimeInnerWalls == value:
            self._percentageTimeInnerWalls = value
            self.percentageTimeInnerWallsChanged.emit()

    percentageTimeOuterWallsChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeOuterWallsChanged)
    def percentageTimeOuterWalls(self):
        return self._percentageTimeOuterWalls

    @percentageTimeOuterWalls.setter
    def percentageTimeOuterWalls(self, value):
        if not self._percentageTimeOuterWalls == value:
            self._percentageTimeOuterWalls = value
            self.percentageTimeOuterWallsChanged.emit()

    percentageTimeRetractionsChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeRetractionsChanged)
    def percentageTimeRetractions(self):
        return self._percentageTimeRetractions

    @percentageTimeRetractions.setter
    def percentageTimeRetractions(self, value):
        if not self._percentageTimeRetractions == value:
            self._percentageTimeRetractions = value
            self.percentageTimeRetractionsChanged.emit()

    percentageTimeSkinChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeSkinChanged)
    def percentageTimeSkin(self):
        return self._percentageTimeSkin

    @percentageTimeSkin.setter
    def percentageTimeSkin(self, value):
        if not self._percentageTimeSkin == value:
            self._percentageTimeSkin = value
            self.percentageTimeSkinChanged.emit()

    percentageTimeSkirtChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeSkirtChanged)
    def percentageTimeSkirt(self):
        return self._percentageTimeSkirt

    @percentageTimeSkirt.setter
    def percentageTimeSkirt(self, value):
        if not self._percentageTimeSkirt == value:
            self._percentageTimeSkirt = value
            self.percentageTimeSkirtChanged.emit()

    percentageTimeTravelChanged = pyqtSignal()

    @pyqtProperty(float, notify=percentageTimeTravelChanged)
    def percentageTimeTravel(self):
        return self._percentageTimeTravel

    @percentageTimeTravel.setter
    def percentageTimeTravel(self, value):
        if not self._percentageTimeTravel == value:
            self._percentageTimeTravel = value
            self.percentageTimeTravelChanged.emit()

    def _onResultTimeChanged(self):
        total_time = 0

        #for result_time in self._resultTimes:
        #    total_time += result_time.msecsSinceStartOfDay()

        total_time += self.resultTimeInfill
        total_time += self.resultTimeInnerWalls
        total_time += self.resultTimeOuterWalls
        total_time += self.resultTimeRetractions
        total_time += self.resultTimeSkin
        total_time += self.resultTimeSkirt
        total_time += self.resultTimeTravel

        self.percentageTimeInfill = 100.0 / total_time * self.resultTimeInfill
        self.percentageTimeInnerWalls = 100.0 / total_time * self.resultTimeInnerWalls
        self.percentageTimeOuterWalls = 100.0 / total_time * self.resultTimeOuterWalls
        self.percentageTimeRetractions = 100.0 / total_time * self.resultTimeRetractions
        self.percentageTimeSkin = 100.0 / total_time * self.resultTimeSkin
        self.percentageTimeSkirt = 100.0 / total_time * self.resultTimeSkirt
        self.percentageTimeTravel = 100.0 / total_time * self.resultTimeTravel

    materialNameChanged = pyqtSignal()

    @pyqtProperty(str, notify=materialNameChanged)
    def materialName(self):
        return self._materialName

    @materialName.setter
    def materialName(self, value):
        Logger.log("w", "TODO")
        self._materialName = value
        self.materialNameChanged.emit()

    materialLengthChanged = pyqtSignal()

    @pyqtProperty(float, notify=materialLengthChanged)
    def materialLength(self):
        return self._materialLength

    @materialLength.setter
    def materialLength(self, value):
        if not self._materialLength == value:
            self._materialLength = value
            self.materialLengthChanged.emit()

    materialWeightChanged = pyqtSignal()

    @pyqtProperty(float, notify=materialWeightChanged)
    def materialWeight(self):
        return self._materialWeight

    @materialWeight.setter
    def materialWeight(self, value):
        if not self._materialWeight == value:
            self._materialWeight = value
            self.materialWeightChanged.emit()

    materialCostChanged = pyqtSignal()

    @pyqtProperty(float, notify=materialCostChanged)
    def materialCost(self):
        return self._materialCost

    @materialCost.setter
    def materialCost(self, value):
        if not self._materialCost == value:
            self._materialCost = value
            self.materialCostChanged.emit()

    #
    #   UI Color Handling
    #
    safetyFactorColorChanged = pyqtSignal()
    maxDisplaceColorChanged = pyqtSignal()

    @pyqtProperty(str, notify=safetyFactorColorChanged)
    def safetyFactorColor(self):
        return self._safetyFactorColor

    @safetyFactorColor.setter
    def safetyFactorColor(self, value):
        self._safetyFactorColor = value

    @pyqtProperty(str, notify=maxDisplaceColorChanged)
    def maxDisplaceColor(self):
        return self._maxDisplaceColor

    @maxDisplaceColor.setter
    def maxDisplaceColor(self, value):
        self._maxDisplaceColor = value

    def updateColorSafetyFactor(self):
        #  Update Safety Factor Color
        if self._resultSafetyFactor > self.targetSafetyFactor:
            self.safetyFactorColor = SmartSlicePropertyColor.WarningColor
        elif self._resultSafetyFactor < self.targetSafetyFactor:
            self.safetyFactorColor = SmartSlicePropertyColor.ErrorColor
        else:
            self.safetyFactorColor = SmartSlicePropertyColor.SuccessColor
        #  Override if part has gone through optimization
        if self._sliceStatusEnum == SmartSliceCloudStatus.Optimized:
            self.safetyFactorColor = SmartSlicePropertyColor.SuccessColor

        self.safetyFactorColorChanged.emit()

    def updateColorMaxDisplacement(self):
        #  Update Maximal Displacement Color
        if self._resultMaximalDisplacement < self.targetMaximalDisplacement:
            self.maxDisplaceColor = SmartSlicePropertyColor.WarningColor
        elif self._resultMaximalDisplacement > self.targetMaximalDisplacement:
            self.maxDisplaceColor = SmartSlicePropertyColor.ErrorColor
        else:
            self.maxDisplaceColor = SmartSlicePropertyColor.SuccessColor
        # Override if part has gone through optimization
        if self._sliceStatusEnum == SmartSliceCloudStatus.Optimized:
            self.maxDisplaceColor = SmartSlicePropertyColor.SuccessColor

        self.maxDisplaceColorChanged.emit()

    def updateColorUI(self):
        self.updateColorSafetyFactor()
        self.updateColorMaxDisplacement()

    # Updates the properties from a job setup
    def updatePropertiesFromJob(self, job: pywim.smartslice.job.Job):

        select_tool = SmartSliceSelectTool.getInstance()
        select_tool.updateFromJob(job)

        requirements = SmartSliceRequirements.getInstance()
        requirements.targetSafetyFactor = job.optimization.min_safety_factor
        requirements.maxDisplacement = job.optimization.max_displacement

    # Updates the properties
    def updatePropertiesFromResults(self, result):

        self.resultSafetyFactor = result[ResultsTableHeader.Strength.value]
        self.resultMaximalDisplacement = result[ResultsTableHeader.Displacement.value]
        self.resultTimeTotal = Duration(result[ResultsTableHeader.Time.value])

        # TODO: Modify the block as soon as we have the single print times again!
        #self.resultTimeInfill = QTime(1, 0, 0, 0)
        #self.resultTimeInnerWalls = QTime(0, 20, 0, 0)
        #self.resultTimeOuterWalls = QTime(0, 15, 0, 0)
        #self.resultTimeRetractions = QTime(0, 5, 0, 0)
        #self.resultTimeSkin = QTime(0, 10, 0, 0)
        #self.resultTimeSkirt = QTime(0, 1, 0, 0)
        #self.resultTimeTravel = QTime(0, 30, 0, 0)

        self.materialLength = result[ResultsTableHeader.Length.value]
        self.materialWeight = result[ResultsTableHeader.Mass.value]
        self.materialCost = result[ResultsTableHeader.Cost.value]

        # Below is commented out because we don't necessarily need it right now.
        # We aren't sending multiple materials to optimize, so the material here
        # won't change. And this assignment causes the "Lose Validation Results"
        # pop-up to show.
        #self.materialName = material_extra_info[3][pos]

        if self._sliceStatusEnum == SmartSliceCloudStatus.Optimized:
            result_id = result[ResultsTableHeader.Rank.value] - 1
            self.updateSceneFromOptimizationResult(self._resultsTable.analyses[result_id])

    def updateStatusFromResults(self, job: pywim.smartslice.job.Job, results: pywim.smartslice.result.Result):

        if job:
            if job.type == pywim.smartslice.job.JobType.validation:
                if results:
                    self.optimizationStatus()
                    self.sliceInfoOpen = True
                else:
                    self._sliceStatusEnum = SmartSliceCloudStatus.ReadyToVerify
            else:
                self.optimizationStatus()
                self.sliceInfoOpen = True
        else:
            self._sliceStatusEnum = SmartSliceCloudStatus.Errors

        Application.getInstance().activityChanged.emit()

    def optimizationStatus(self):
        req_tool = SmartSliceRequirements.getInstance()
        if req_tool.maxDisplacement > self.resultMaximalDisplacement and req_tool.targetSafetyFactor < self.resultSafetyFactor:
            self._sliceStatusEnum = SmartSliceCloudStatus.Overdimensioned
        elif req_tool.maxDisplacement <= self.resultMaximalDisplacement or req_tool.targetSafetyFactor >= self.resultSafetyFactor:
            self._sliceStatusEnum = SmartSliceCloudStatus.Underdimensioned
        else:
            self._sliceStatusEnum = SmartSliceCloudStatus.Optimized

    def updateSceneFromOptimizationResult(self, analysis: pywim.smartslice.result.Analysis):
        our_only_node =  getPrintableNodes()[0]
        active_extruder = getNodeActiveExtruder(our_only_node)

        # TODO - Move this into a common class or function to apply an am.Config to GlobalStack/ExtruderStack
        if analysis.print_config.infill:

            infill_density = analysis.print_config.infill.density
            infill_pattern = analysis.print_config.infill.pattern

            if infill_pattern is None or infill_pattern == pywim.am.InfillType.unknown:
                infill_pattern = pywim.am.InfillType.grid

            infill_pattern_name = SmartSliceJobHandler.INFILL_SMARTSLICE_CURA[infill_pattern]

            extruder_dict = {
                "wall_line_count": analysis.print_config.walls,
                "top_layers": analysis.print_config.top_layers,
                "bottom_layers": analysis.print_config.bottom_layers,
                "infill_sparse_density": analysis.print_config.infill.density,
                "infill_pattern": infill_pattern_name
            }

            Logger.log("d", "Optimized extruder settings: {}".format(extruder_dict))

            for key, value in extruder_dict.items():
                if value is not None:
                    active_extruder.setProperty(key, "value", value, set_from_cache=True)

            Application.getInstance().getMachineManager().forceUpdateAllSettings()
            self.optimizationResultAppliedToScene.emit()

        # Remove any modifier meshes which are present from a previous result
        mod_meshes = getModifierMeshes()
        if len(mod_meshes) > 0:
            op = GroupedOperation()
            for node in mod_meshes:
                node.addDecorator(SmartSliceRemovedDecorator())
                op.addOperation(RemoveSceneNodeOperation(node))
            op.push()
            Application.getInstance().getController().getScene().sceneChanged.emit(node)

        # Add in the new modifier meshes
        for modifier_mesh in analysis.modifier_meshes:
            # Building the scene node
            modifier_mesh_node = CuraSceneNode()
            modifier_mesh_node.setName("SmartSliceMeshModifier")
            modifier_mesh_node.setSelectable(True)
            modifier_mesh_node.setCalculateBoundingBox(True)

            # Use the data from the SmartSlice engine to translate / rotate / scale the mod mesh
            parent_transformation = our_only_node.getLocalTransformation()
            modifier_mesh_transform_matrix = parent_transformation.multiply(Matrix(modifier_mesh.transform))
            modifier_mesh_node.setTransformation(modifier_mesh_transform_matrix)

            # Building the mesh

            # # Preparing the data from pywim for MeshBuilder
            modifier_mesh_vertices = [[v.x, v.y, v.z] for v in modifier_mesh.vertices ]
            modifier_mesh_indices = [[triangle.v1, triangle.v2, triangle.v3] for triangle in modifier_mesh.triangles]

            # Doing the actual build
            modifier_mesh_data = MeshBuilder()
            modifier_mesh_data.setVertices(numpy.asarray(modifier_mesh_vertices, dtype=numpy.float32))
            modifier_mesh_data.setIndices(numpy.asarray(modifier_mesh_indices, dtype=numpy.int32))
            modifier_mesh_data.calculateNormals()

            modifier_mesh_node.setMeshData(modifier_mesh_data.build())
            modifier_mesh_node.calculateBoundingBoxMesh()

            active_build_plate = Application.getInstance().getMultiBuildPlateModel().activeBuildPlate
            modifier_mesh_node.addDecorator(BuildPlateDecorator(active_build_plate))
            modifier_mesh_node.addDecorator(SliceableObjectDecorator())
            modifier_mesh_node.addDecorator(SmartSliceAddedDecorator())

            bottom = modifier_mesh_node.getBoundingBox().bottom

            z_offset_decorator = ZOffsetDecorator()
            z_offset_decorator.setZOffset(bottom)
            modifier_mesh_node.addDecorator(z_offset_decorator)

            stack = modifier_mesh_node.callDecoration("getStack")
            settings = stack.getTop()

            modifier_mesh_node_infill_pattern = SmartSliceJobHandler.INFILL_SMARTSLICE_CURA[modifier_mesh.print_config.infill.pattern]
            definition_dict = {
                "infill_mesh" : True,
                "infill_pattern" : modifier_mesh_node_infill_pattern,
                "infill_sparse_density": modifier_mesh.print_config.infill.density,
                "wall_line_count": modifier_mesh.print_config.walls,
                "top_layers": modifier_mesh.print_config.top_layers,
                "bottom_layers": modifier_mesh.print_config.bottom_layers,
                }
            Logger.log("d", "Optimized modifier mesh settings: {}".format(definition_dict))

            for key, value in definition_dict.items():
                if value is not None:
                    definition = stack.getSettingDefinition(key)
                    new_instance = SettingInstance(definition, settings)
                    new_instance.setProperty("value", value)

                    new_instance.resetState()  # Ensure that the state is not seen as a user state.
                    settings.addInstance(new_instance)

            op = GroupedOperation()
            # First add node to the scene at the correct position/scale, before parenting, so the eraser mesh does not get scaled with the parent
            op.addOperation(AddSceneNodeOperation(
                modifier_mesh_node,
                Application.getInstance().getController().getScene().getRoot()
            ))
            op.addOperation(SetParentOperation(
                modifier_mesh_node,
                Application.getInstance().getController().getScene().getRoot()
            ))
            op.push()

            # emit changes and connect error tracker
            Application.getInstance().getController().getScene().sceneChanged.emit(modifier_mesh_node)

