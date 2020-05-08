import copy

from enum import Enum

from PyQt5.QtCore import pyqtSignal, pyqtProperty
from PyQt5.QtCore import QObject, QTime, QUrl

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Logger import Logger

from .SmartSliceProperty import SmartSlicePropertyEnum, SmartSlicePropertyColor
from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements

i18n_catalog = i18nCatalog("smartslice")

class SmartSliceCloudStatus():
    NoConnection = 1
    BadLogin = 2
    NoModel = 3
    NoConditions = 4
    ReadyToVerify = 5
    Underdimensioned = 6
    Overdimensioned = 7
    BusyValidating = 8
    BusyOptimizing = 9
    Optimized = 10

    Busy = (
        BusyValidating,
        BusyOptimizing
    )

    Optimizable = (
        Underdimensioned,
        Overdimensioned
    )

class SmartSliceCloudProxy(QObject):
    def __init__(self, connector) -> None:
        super().__init__()

        self.connector = connector

        # Primary Button (Slice/Validate/Optimize)
        self._sliceStatusEnum = 0
        self._sliceStatus = "_Status"
        self._sliceHint = "_Hint"
        self._sliceButtonText = "_ButtonText"
        self._sliceButtonEnabled = False
        self._sliceButtonVisible = True
        self._sliceButtonFillWidth = True
        self._sliceIconImage = ""
        self._sliceIconVisible = False
        self._sliceInfoOpen = False

        # Secondary Button (Preview/Cancel)
        self._secondaryButtonText = "_SecondaryText"
        self._secondaryButtonFillWidth = False
        self._secondaryButtonVisible = False

        # Proxy Values (DO NOT USE DIRECTLY)
        self._targetFactorOfSafety = 1.5
        self._targetMaximalDisplacement = 1.0

        self._safetyFactorColor = "#000000"
        self._maxDisplaceColor = "#000000"

        #  Use-case & Requirements Cache
        self.reqsMaxDeflect  = self._targetMaximalDisplacement

        # Properties (mainly) for the sliceinfo widget
        self._resultSafetyFactor = 0.0 #copy.copy(self._targetFactorOfSafety)
        self._resultMaximalDisplacement = 0.0 #copy.copy(self._targetMaximalDisplacement)
        self._resultTimeTotal = QTime(0, 0, 0, 1)
        self._resultTimeInfill = QTime(0, 0, 0, 1)
        self._resultTimeInnerWalls = QTime(0, 0, 0, 1)
        self._resultTimeOuterWalls = QTime(0, 0, 0, 1)
        self._resultTimeRetractions = QTime(0, 0, 0, 1)
        self._resultTimeSkin = QTime(0, 0, 0, 1)
        self._resultTimeSkirt = QTime(0, 0, 0, 1)
        self._resultTimeTravel = QTime(0, 0, 0, 1)
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

    #
    #   SLICE BUTTON WINDOW
    #
    sliceButtonClicked = pyqtSignal()
    secondaryButtonClicked = pyqtSignal()
    sliceStatusChanged = pyqtSignal()
    sliceStatusEnumChanged = pyqtSignal()
    sliceButtonFillWidthChanged = pyqtSignal()

    sliceHintChanged = pyqtSignal()
    sliceButtonVisibleChanged = pyqtSignal()
    sliceButtonEnabledChanged = pyqtSignal()
    sliceButtonTextChanged = pyqtSignal()
    sliceInfoOpenChanged = pyqtSignal()

    secondaryButtonTextChanged = pyqtSignal()
    secondaryButtonVisibleChanged = pyqtSignal()
    secondaryButtonFillWidthChanged = pyqtSignal()

    @pyqtProperty(int, notify=sliceStatusEnumChanged)
    def sliceStatusEnum(self):
        return self._sliceStatusEnum

    @sliceStatusEnum.setter
    def sliceStatusEnum(self, value):
        if self._sliceStatusEnum is not value:
            self._sliceStatusEnum = value
            self.sliceStatusEnumChanged.emit()

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

    resultTimeTotalChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeTotalChanged)
    def resultTimeTotal(self):
        return self._resultTimeTotal

    @resultTimeTotal.setter
    def resultTimeTotal(self, value: QTime):
        if self._resultTimeTotal is not value:
            self._resultTimeTotal = value
            self.resultTimeTotalChanged.emit()

    resultTimeInfillChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeInfillChanged)
    def resultTimeInfill(self):
        return self._resultTimeInfill

    @resultTimeInfill.setter
    def resultTimeInfill(self, value: QTime):
        if self._resultTimeInfill is not value:
            self._resultTimeInfill = value
            self.resultTimeInfillChanged.emit()

    resultTimeInnerWallsChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeInnerWallsChanged)
    def resultTimeInnerWalls(self):
        return self._resultTimeInnerWalls

    @resultTimeInnerWalls.setter
    def resultTimeInnerWalls(self, value: QTime):
        if self._resultTimeInnerWalls is not value:
            self._resultTimeInnerWalls = value
            self.resultTimeInnerWallsChanged.emit()

    resultTimeOuterWallsChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeOuterWallsChanged)
    def resultTimeOuterWalls(self):
        return self._resultTimeOuterWalls

    @resultTimeOuterWalls.setter
    def resultTimeOuterWalls(self, value: QTime):
        if self._resultTimeOuterWalls is not value:
            self._resultTimeOuterWalls = value
            self.resultTimeOuterWallsChanged.emit()

    resultTimeRetractionsChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeRetractionsChanged)
    def resultTimeRetractions(self):
        return self._resultTimeRetractions

    @resultTimeRetractions.setter
    def resultTimeRetractions(self, value: QTime):
        if self._resultTimeRetractions is not value:
            self._resultTimeRetractions = value
            self.resultTimeRetractionsChanged.emit()

    resultTimeSkinChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeSkinChanged)
    def resultTimeSkin(self):
        return self._resultTimeSkin

    @resultTimeSkin.setter
    def resultTimeSkin(self, value: QTime):
        if self._resultTimeSkin is not value:
            self._resultTimeSkin = value
            self.resultTimeSkinChanged.emit()

    resultTimeSkirtChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeSkirtChanged)
    def resultTimeSkirt(self):
        return self._resultTimeSkirt

    @resultTimeSkirt.setter
    def resultTimeSkirt(self, value: QTime):
        if self._resultTimeSkirt is not value:
            self._resultTimeSkirt = value
            self.resultTimeSkirtChanged.emit()

    resultTimeTravelChanged = pyqtSignal()

    @pyqtProperty(QTime, notify=resultTimeTravelChanged)
    def resultTimeTravel(self):
        return self._resultTimeTravel

    @resultTimeTravel.setter
    def resultTimeTravel(self, value: QTime):
        if self._resultTimeTravel is not value:
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

        total_time += self.resultTimeInfill.msecsSinceStartOfDay()
        total_time += self.resultTimeInnerWalls.msecsSinceStartOfDay()
        total_time += self.resultTimeOuterWalls.msecsSinceStartOfDay()
        total_time += self.resultTimeRetractions.msecsSinceStartOfDay()
        total_time += self.resultTimeSkin.msecsSinceStartOfDay()
        total_time += self.resultTimeSkirt.msecsSinceStartOfDay()
        total_time += self.resultTimeTravel.msecsSinceStartOfDay()

        self.percentageTimeInfill = 100.0 / total_time * self.resultTimeInfill.msecsSinceStartOfDay()
        self.percentageTimeInnerWalls = 100.0 / total_time * self.resultTimeInnerWalls.msecsSinceStartOfDay()
        self.percentageTimeOuterWalls = 100.0 / total_time * self.resultTimeOuterWalls.msecsSinceStartOfDay()
        self.percentageTimeRetractions = 100.0 / total_time * self.resultTimeRetractions.msecsSinceStartOfDay()
        self.percentageTimeSkin = 100.0 / total_time * self.resultTimeSkin.msecsSinceStartOfDay()
        self.percentageTimeSkirt = 100.0 / total_time * self.resultTimeSkirt.msecsSinceStartOfDay()
        self.percentageTimeTravel = 100.0 / total_time * self.resultTimeTravel.msecsSinceStartOfDay()

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
        if self.connector.status is SmartSliceCloudStatus.Optimized:
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
        if self.connector.status is SmartSliceCloudStatus.Optimized:
            self.maxDisplaceColor = SmartSlicePropertyColor.SuccessColor

        self.maxDisplaceColorChanged.emit()

    def updateColorUI(self):
        self.updateColorSafetyFactor()
        self.updateColorMaxDisplacement()
