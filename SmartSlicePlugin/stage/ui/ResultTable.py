import json
import math

from typing import Dict, List
from enum import Enum
from datetime import time

from PyQt5.QtCore import QAbstractListModel, QObject, QModelIndex
from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QTime
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from UM.Logger import Logger
from UM.Signal import Signal
from UM.Application import Application

import pywim

class ResultsTableHeader(Enum):
    Rank = 0
    Time = 1
    Mass = 2
    Strength = 3
    Displacement = 4
    Cost = 5
    Length = 6

    @staticmethod
    def rolesAsBytes():
        return {
            ResultsTableHeader.Rank.value: str.encode(ResultsTableHeader.Rank.name.lower()),
            ResultsTableHeader.Time.value: str.encode(ResultsTableHeader.Time.name.lower()),
            ResultsTableHeader.Mass.value: str.encode(ResultsTableHeader.Mass.name.lower()),
            ResultsTableHeader.Strength.value: str.encode(ResultsTableHeader.Strength.name.lower()),
            ResultsTableHeader.Displacement.value: str.encode(ResultsTableHeader.Displacement.name.lower()),
        }

    @staticmethod
    def numRoles():
        return len(ResultsTableHeader.rolesAsBytes())

class ResultTableData(QAbstractListModel):

    selectedRowChanged = pyqtSignal()
    sortColumnChanged = pyqtSignal()
    sortOrderChanged = pyqtSignal()
    locationChanged = pyqtSignal()
    heightChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._results = [] # List[pywim.smartslice.result.Analysis]
        self._resultsDict = [] # List[Dict[]] --> A list of dictionary items for sorting

        self._selectedRow = 0
        self._sortColumn = 0
        self._sortOrder = Qt.AscendingOrder

        self.updateDisplaySignal = Signal() # Tells the owner of the table when to  update the display (like when a row is clicked)
        self.resultsUpdated = Signal()

        self._xLocation = 0
        self._yLocation = 0
        self._locationSet = False

        self._height = 0
        self._heightSet = False

    def setResults(self, results: List[pywim.smartslice.result.Analysis], requested_result=0):

        self.beginRemoveRows(QModelIndex(), 0, len(self._resultsDict) - 1)
        self._results.clear()
        self._resultsDict.clear()
        self.endRemoveRows()

        self._results = results
        self.selectedRow = -1

        self.sortColumn = 0
        self.sortOrder = Qt.AscendingOrder

        rank = 0
        row = 0
        for result in self._results:
            rank += 1
            self._resultsDict.append(self.analysisToResultDict(rank, result))
            if rank - 1 == requested_result:
                row = rank - 1

        self.beginInsertRows(QModelIndex(), 0, len(self._resultsDict) - 1)
        self.endInsertRows()

        self.selectedRow = row
        self.sortByColumn(0, Qt.AscendingOrder)
        self.updateDisplaySignal.emit(self._resultsDict[row])
        self.resultsUpdated.emit()

    def roleNames(self):
        return ResultsTableHeader.rolesAsBytes()

    @pyqtProperty(bool, notify=locationChanged)
    def locationSet(self):
        return self._locationSet

    @pyqtProperty(int, notify=locationChanged)
    def xLocation(self):
        return self._xLocation

    @pyqtProperty(int, notify=locationChanged)
    def yLocation(self):
        return self._yLocation

    @pyqtSlot(int, int)
    def setLocation(self, x, y):
        self._xLocation = x
        self._yLocation = y
        self._locationSet = True
        self.locationChanged.emit()

    @pyqtProperty(bool, notify=heightChanged)
    def heightSet(self):
        return self._heightSet

    @pyqtProperty(int, notify=heightChanged)
    def height(self):
        return self._height

    @pyqtSlot(int)
    def setHeight(self, height):
        self._height = height
        self._heightSet = True
        self.heightChanged.emit()

    @pyqtProperty(int, notify=selectedRowChanged)
    def selectedRow(self):
        return self._selectedRow

    @selectedRow.setter
    def selectedRow(self, value):
        if self._selectedRow is not value:
            self._selectedRow = value
            self.selectedRowChanged.emit()

    @pyqtProperty(int, notify=sortColumnChanged)
    def sortColumn(self):
        return self._sortColumn

    @sortColumn.setter
    def sortColumn(self, value):
        if self._sortColumn is not value:
            self._sortColumn = value
            self.sortColumnChanged.emit()

    @pyqtProperty(int, notify=sortOrderChanged)
    def sortOrder(self):
        return self._sortOrder

    @sortOrder.setter
    def sortOrder(self, value):
        if self._sortOrder is not value:
            self._sortOrder = value
            self.sortOrderChanged.emit()

    @property
    def analyses(self):
        return self._results

    @pyqtSlot(QObject, result=int)
    def rowCount(self, parent=None) -> int:
        return len(self._resultsDict)

    def getSelectedResultId(self):
        if self._selectedRow >= 0 and self._selectedRow < len(self._resultsDict):
            return self._resultsDict[self._selectedRow][ResultsTableHeader.Rank.value] - 1
        return 0

    def data(self, index, role):
        if len(self._resultsDict) > index.row():
            if len(ResultsTableHeader.rolesAsBytes()) > role:
                value = self._resultsDict[index.row()][role]

                if role == ResultsTableHeader.Time.value:
                    pytime = value.toPyTime()
                    return "{}h {}m".format(pytime.hour, pytime.minute)

                elif role == ResultsTableHeader.Mass.value:
                    return "{}g".format(round(value, 0))

                elif role == ResultsTableHeader.Displacement.value:
                    return "{} mm".format(round(value, 2))

                elif role == ResultsTableHeader.Strength.value:
                    return round(value, 1)

                else:
                    return value

        return None

    @pyqtSlot(int)
    def sortByColumn(self, column=0, order=None):

        if column >= ResultsTableHeader.numRoles():
            return

        if order is None:
            if column != self.sortColumn:
                self.sortOrder = Qt.AscendingOrder
            else:
                if self.sortOrder == Qt.AscendingOrder:
                    self.sortOrder = Qt.DescendingOrder
                else:
                    self.sortOrder = Qt.AscendingOrder
        else:
            self.sortOrder = order

        self.sortColumn = column

        descending = True if self.sortOrder is Qt.DescendingOrder else False

        rank = self._resultsDict[self._selectedRow][ResultsTableHeader.Rank.value]

        self._resultsDict.sort(reverse=descending, key=lambda result: result[column])

        self.beginRemoveRows(QModelIndex(), 0, len(self._resultsDict) - 1)
        self.endRemoveRows()

        self.beginInsertRows(QModelIndex(), 0, len(self._resultsDict) - 1)
        self.endInsertRows()

        i = 0
        for result in self._resultsDict:
            if result[ResultsTableHeader.Rank.value] == rank:
                self.selectedRow = i
            i += 1

    @pyqtSlot(int)
    def rowClicked(self, row):
        if row < len(self._resultsDict):
            self.selectedRow = row
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.updateDisplaySignal.emit(self._resultsDict[row])
            QApplication.restoreOverrideCursor()

    @pyqtSlot()
    def previewClicked(self):
        Application.getInstance().getController().setActiveStage("PreviewStage")

    @classmethod
    def analysisToResultDict(self, rank, result: pywim.smartslice.result.Analysis):
        material_data = self.calculateAdditionalMaterialInfo(result)
        qprint_time = QTime(0, 0, 0, 0)

        return {
            ResultsTableHeader.Rank.value: rank,
            ResultsTableHeader.Time.value: qprint_time.addSecs(result.print_time),
            ResultsTableHeader.Strength.value: result.structural.min_safety_factor,
            ResultsTableHeader.Displacement.value: result.structural.max_displacement,
            ResultsTableHeader.Length.value: material_data[0][0],
            ResultsTableHeader.Mass.value: material_data[1][0],
            ResultsTableHeader.Cost.value: material_data[2][0]
        }

    @classmethod
    def calculateAdditionalMaterialInfo(self, result: pywim.smartslice.result.Analysis):

        _material_volume = [result.extruders[0].material_volume]

        application = Application.getInstance()

        global_stack = application.getGlobalContainerStack()
        if global_stack is None:
            return

        _material_lengths = []
        _material_weights = []
        _material_costs = []
        _material_names = []

        material_preference_values = json.loads(application.getPreferences().getValue("cura/material_settings"))

        Logger.log("d", "global_stack.extruderList: {}".format(global_stack.extruderList))

        for extruder_stack in global_stack.extruderList:
            position = extruder_stack.position
            if type(position) is not int:
                position = int(position)
            if position >= len(_material_volume):
                continue
            amount = _material_volume[position]
            # Find the right extruder stack. As the list isn't sorted because it's a annoying generator, we do some
            # list comprehension filtering to solve this for us.
            density = extruder_stack.getMetaDataEntry("properties", {}).get("density", 0)
            material = extruder_stack.material
            radius = extruder_stack.getProperty("material_diameter", "value") / 2

            weight = float(amount) * float(density) / 1000
            cost = 0.

            material_guid = material.getMetaDataEntry("GUID")
            material_name = material.getName()

            if material_guid in material_preference_values:
                material_values = material_preference_values[material_guid]

                if material_values and "spool_weight" in material_values:
                    weight_per_spool = float(material_values["spool_weight"])
                else:
                    weight_per_spool = float(extruder_stack.getMetaDataEntry("properties", {}).get("weight", 0))

                cost_per_spool = float(material_values["spool_cost"] if material_values and "spool_cost" in material_values else 0)

                if weight_per_spool != 0:
                    cost = cost_per_spool * weight / weight_per_spool
                else:
                    cost = 0

            # Material amount is sent as an amount of mm^3, so calculate length from that
            if radius != 0:
                length = round((amount / (math.pi * radius ** 2)) / 1000, 2)
            else:
                length = 0

            _material_weights.append(weight)
            _material_lengths.append(length)
            _material_costs.append(cost)
            _material_names.append(material_name)

        return _material_lengths, _material_weights, _material_costs, _material_names


