import copy

from enum import Enum

from PyQt5.QtCore import pyqtSignal, pyqtProperty
from PyQt5.QtCore import QObject, QTime, QUrl

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Logger import Logger

from .SmartSliceProperty import SmartSlicePropertyEnum, SmartSlicePropertyColor

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

        # Properties (mainly) for the login window
        self._loginStatus = "Please log in with your credentials below."
        self._loginName = ""
        self._loginPassword = ""

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

        # Secondary Button (Preview/Cancel)
        self._secondaryButtonText = "_SecondaryText"
        self._secondaryButtonFillWidth = False
        self._secondaryButtonVisible = False

        # Confirm Changes Dialog
        self._confirmationWindowEnabled = False
        self._confirmationText = ""

        # Proxy Values (DO NOT USE DIRECTLY)
        self._targetFactorOfSafety = 1.5
        self._targetMaximalDisplacement = 1.0
        self._loadsApplied = 0
        self._anchorsApplied = 0
        self._loadMagnitude = 10.0
        self._loadDirection = False

        #  QML-Python Buffer Variables
        self._bufferMagnitude = self._loadMagnitude
        self._bufferDeflect = self._targetMaximalDisplacement
        self._bufferSafety = self._targetFactorOfSafety
        self._safetyFactorColor = "#000000"
        self._maxDisplaceColor = "#000000"

        #  Use-case & Requirements Cache
        self.reqsSafetyFactor = self._targetFactorOfSafety
        self.reqsMaxDeflect  = self._targetMaximalDisplacement
        self.reqsLoadMagnitude = self._loadMagnitude
        self.reqsLoadDirection = self._loadDirection

        # Properties (mainly) for the sliceinfo widget
        self._resultSafetyFactor = copy.copy(self._targetFactorOfSafety)
        self._resultMaximalDisplacement = copy.copy(self._targetMaximalDisplacement)
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

    # Properties (mainly) for the login window

    loginStatusChanged = pyqtSignal()

    @pyqtProperty(str, notify=loginStatusChanged)
    def loginStatus(self):
        return self._loginStatus

    @loginStatus.setter
    def loginStatus(self, value):
        if self._loginStatus is not value:
            Logger.log("d", "loginStatus: <{}> -> <{}>".format(self._loginStatus, value))
            self._loginStatus = value
            self.loginStatusChanged.emit()

    loginNameChanged = pyqtSignal()

    @pyqtProperty(str, notify=loginNameChanged)
    def loginName(self):
        return self._loginName

    @loginName.setter
    def loginName(self, value):
        if self._loginName is not value:
            Logger.log("d", "loginName: <{}> -> <{}>".format(self._loginName, value))
            self._loginName = value
            self.loginNameChanged.emit()

    loginPasswordChanged = pyqtSignal()

    @pyqtProperty(str, notify=loginPasswordChanged)
    def loginPassword(self):
        return self._loginPassword

    @loginPassword.setter
    def loginPassword(self, value):
        if self._loginPassword is not value:
            Logger.log("d", "loginPassword: <secret!>")
            self._loginPassword = value
            self.loginPasswordChanged.emit()

    @pyqtProperty(bool, notify=loginPasswordChanged)
    def loginResult(self):
        return self.connector.login()

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

    #
    #   CONFIRMATION WINDOW
    #

    confirmationWindowEnabledChanged = pyqtSignal()
    confirmationWindowTextChanged = pyqtSignal()
    confirmationConfirmClicked = pyqtSignal()
    confirmationCancelClicked = pyqtSignal()

    @pyqtProperty(bool, notify=confirmationWindowEnabledChanged)
    def confirmationWindowEnabled(self):
        return self._confirmationWindowEnabled

    @confirmationWindowEnabled.setter
    def confirmationWindowEnabled(self, value):
        if self._confirmationWindowEnabled is not value:
            self._confirmationWindowEnabled = value
            self.confirmationWindowEnabledChanged.emit()

    @pyqtProperty(str, notify=confirmationWindowTextChanged)
    def confirmationWindowText(self):
        return self._confirmationText

    @confirmationWindowText.setter
    def confirmationWindowText(self, value):
        if self._confirmationText is not value:
            self._confirmationText = value
            self.confirmationWindowTextChanged.emit()

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


    #  Used for detecting changes in UI during Sensitive Times, e.g. Validation/Optimization
    settingEditedChanged = pyqtSignal()
    bufferMagnitudeChanged = pyqtSignal()
    bufferDisplacementChanged = pyqtSignal()
    bufferSafetyFactorChanged = pyqtSignal()


    #  NOTE:  Never gets read.  Included to separate cache from buffer
    @pyqtProperty(bool, notify=settingEditedChanged)
    def settingEdited(self):
        return True

    """
      settingEdited()
        Throws a prompt which indicates that a buffered setting has been modified.
    """
    @settingEdited.setter
    def settingEdited(self, value):
        Logger.log("w", "TODO"); return
        if value:
            if self._loadMagnitude != self._bufferMagnitude:
                self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.LoadMagnitude)
                self.connector.propertyHandler._changedValues.append(0) #  Keep '_propertiesChanged' index aligned with '_changedValues'
                self.connector.confirmPendingChanges()
            if self.connector.status in {SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
                if self._targetMaximalDisplacement != self._bufferDeflect:
                    self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.MaxDisplacement)
                    self.connector.propertyHandler._changedValues.append(0) #  Keep '_propertiesChanged' index aligned with '_changedValues'
                    self.connector.confirmPendingChanges()
                if self._targetFactorOfSafety != self._bufferSafety:
                    self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.FactorOfSafety)
                    self.connector.propertyHandler._changedValues.append(0) #  Keep '_propertiesChanged' index aligned with '_changedValues'
                    self.connector.confirmPendingChanges()


    #  Buffers for separating current change in text from property values
    @pyqtProperty(float, notify=bufferMagnitudeChanged)
    def bufferMagnitude(self):
        return self._bufferMagnitude

    @bufferMagnitude.setter
    def bufferMagnitude(self, value):
        self._bufferMagnitude = value

    @pyqtProperty(float, notify=bufferDisplacementChanged)
    def bufferDisplacement(self):
        return self._bufferDeflect

    @bufferDisplacement.setter
    def bufferDisplacement(self, value):
        self._bufferDeflect = value

    @pyqtProperty(float, notify=bufferSafetyFactorChanged)
    def bufferSafetyFactor(self):
        return self._bufferSafety

    @bufferSafetyFactor.setter
    def bufferSafetyFactor(self, value):
        self._bufferSafety = value


    #
    # USE-CASE REQUIREMENTS
    #   * Safety Factor
    #   * Max Displacement
    #   * Load Magnitude/Direction
    #

    # Safety Factor

    targetFactorOfSafetyChanged = pyqtSignal()
    resultSafetyFactorChanged = pyqtSignal()

    def setFactorOfSafety(self):
        self._targetFactorOfSafety = self.reqsSafetyFactor
        self.targetFactorOfSafetyChanged.emit()

    @pyqtProperty(float, notify=targetFactorOfSafetyChanged)
    def targetFactorOfSafety(self):
        return self._targetFactorOfSafety

    @targetFactorOfSafety.setter
    def targetFactorOfSafety(self, value):
        Logger.log("w", "TODO"); return
        if value == self._targetFactorOfSafety:
            return
        if self.connector.status is SmartSliceCloudStatus.BusyOptimizing or (self.connector.status is SmartSliceCloudStatus.Optimized):
            self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.FactorOfSafety)
            self.connector.propertyHandler._changedValues.append(value)
            self.connector.confirmPendingChanges()
        elif self.connector.status in SmartSliceCloudStatus.Optimizable:
            self.reqsSafetyFactor = value
            self.setFactorOfSafety()
            self.connector.prepareOptimization()
        else:
            self.reqsSafetyFactor = value
            self.setFactorOfSafety()

    @pyqtProperty(float, notify=resultSafetyFactorChanged)
    def resultSafetyFactor(self):
        return self._resultSafetyFactor

    @resultSafetyFactor.setter
    def resultSafetyFactor(self, value):
        if self._resultSafetyFactor is not value:
            self._resultSafetyFactor = value
            self.resultSafetyFactorChanged.emit()

    # Max Displacement

    targetMaximalDisplacementChanged = pyqtSignal()
    resultMaximalDisplacementChanged = pyqtSignal()

    def setMaximalDisplacement(self):
        self._targetMaximalDisplacement = self.reqsMaxDeflect
        self.targetMaximalDisplacementChanged.emit()

    @pyqtProperty(float, notify=targetMaximalDisplacementChanged)
    def targetMaximalDisplacement(self):
        return self._targetMaximalDisplacement

    @targetMaximalDisplacement.setter
    def targetMaximalDisplacement(self, value):
        Logger.log("w", "TODO"); return
        if value == self._targetMaximalDisplacement:
            return
        if self.connector.status is SmartSliceCloudStatus.BusyOptimizing or (self.connector.status is SmartSliceCloudStatus.Optimized):
            self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.MaxDisplacement)
            self.connector.propertyHandler._changedValues.append(value)
            self.connector.confirmPendingChanges()
        elif self.connector.status in SmartSliceCloudStatus.Optimizable:
            self.reqsMaxDeflect = value
            self.setMaximalDisplacement()
            self.connector.prepareOptimization()
        else:
            self.reqsMaxDeflect = value # SET CACHE
            self.setMaximalDisplacement()


    @pyqtProperty(float, notify=resultMaximalDisplacementChanged)
    def resultMaximalDisplacement(self):
        return self._resultMaximalDisplacement

    @resultMaximalDisplacement.setter
    def resultMaximalDisplacement(self, value):
        if self._resultMaximalDisplacement is not value:
            self._resultMaximalDisplacement = value
            self.resultMaximalDisplacementChanged.emit()


    #   Load Direction/Magnitude
    loadMagnitudeChanged = pyqtSignal()
    loadDirectionChanged = pyqtSignal()

    def setLoadMagnitude(self):
        self._loadMagnitude = self.reqsLoadMagnitude
        self.loadMagnitudeChanged.emit()

    @pyqtProperty(float, notify=loadMagnitudeChanged)
    def loadMagnitude(self):
        return self._loadMagnitude

    @loadMagnitude.setter
    def loadMagnitude(self, value):
        Logger.log("w", "TODO"); return
        if value == self._loadMagnitude:
            return
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.LoadMagnitude)
            self.connector.propertyHandler._changedValues.append(value)
            self.connector.confirmPendingChanges()
        else:
            self.reqsLoadMagnitude = value
            self.setLoadMagnitude()
            self.connector.prepareValidation()

    def setLoadDirection(self):
        self._loadDirection = self.reqsLoadDirection
        #self.loadDirectionChanged.emit()

    @pyqtProperty(bool, notify=loadDirectionChanged)
    def loadDirection(self):
        Logger.log("d", "Load Direction has been set to " + str(self._loadDirection))
        return self._loadDirection

    @loadDirection.setter
    def loadDirection(self, value):
        Logger.log("w", "TODO"); return
        if value == self.reqsLoadDirection:
            return
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            self.connector.propertyHandler._propertiesChanged.append(SmartSlicePropertyEnum.LoadDirection)
            self.connector.propertyHandler._changedValues.append(value)
            self.connector.confirmPendingChanges()
        else:
            self.reqsLoadDirection = value
            self.setLoadDirection()

            select_tool = Application.getInstance().getController().getTool("SmartSlicePlugin_SelectTool")
            select_tool._handle.setFace(self.connector.propertyHandler._loadedTris)
            select_tool._handle.drawSelection()

            self.connector.propertyHandler.applyLoad()
            self.connector.prepareValidation()

    #  NOTE:  This should only be accessed by QML
    def _applyLoad(self):
        self.connector.propertyHandler.applyLoad()

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
        Logger.log("w", "TODO"); return
        if self.connector.status is SmartSliceCloudStatus.BusyValidating:
            self._propertyChanged = SmartSlicePropertyEnum.Material
            self._changedMaterial = value
            self.connector.confirmPendingChanges()
        elif self._materialName is not value:
            self._materialName = value
            self.materialNameChanged.emit()
            self.connector.prepareValidation()

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
        if self._resultSafetyFactor > self.reqsSafetyFactor:
            self.safetyFactorColor = SmartSlicePropertyColor.WarningColor
        elif self._resultSafetyFactor < self.reqsSafetyFactor:
            self.safetyFactorColor = SmartSlicePropertyColor.ErrorColor
        else:
            self.safetyFactorColor = SmartSlicePropertyColor.SuccessColor
        #  Override if part has gone through optimization
        if self.connector.status is SmartSliceCloudStatus.Optimized:
            self.safetyFactorColor = SmartSlicePropertyColor.SuccessColor

        self.safetyFactorColorChanged.emit()

    def updateColorMaxDisplacement(self):
        #  Update Maximal Displacement Color
        if self._resultMaximalDisplacement < self.reqsMaxDeflect:
            self.maxDisplaceColor = SmartSlicePropertyColor.WarningColor
        elif self._resultMaximalDisplacement > self.reqsMaxDeflect:
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
