from PyQt5.QtCore import QAbstractListModel, QObject, QModelIndex
from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from UM.Logger import Logger
from UM.Scene.Selection import Selection
from UM.Signal import Signal

from cura.CuraApplication import CuraApplication

from ..utils import findChildSceneNode, getPrintableNodes
from ..stage import SmartSliceScene


class BoundaryConditionListModel(QAbstractListModel):
    Anchor = 0
    Force = 1

    loadDirectionChanged = pyqtSignal(SmartSliceScene.LoadFace)
    loadMagnitudeChanged = pyqtSignal(SmartSliceScene.LoadFace)

    def __init__(self, parent=None):
        super().__init__(parent)

        # TODO can we get rid of self._bcs and dynamically return
        # the data in self.data() from digging into self._smart_slice_node?
        # Will the ordering of the children scene nodes be predictable?

        self._bcs = []  # List[HighlightFace]
        self._bc_type = BoundaryConditionListModel.Anchor
        self._smart_slice_scene_node = None
        self._active_node = None

    def _setup(self):
        # scene = CuraApplication.getInstance().getController().getScene().getRoot()
        selected_node = Selection.getSelectedObject(0)

        if not selected_node:
            Logger.warning("No node selected for creating boundary conditions")
            return

        self._smart_slice_scene_node = findChildSceneNode(selected_node, SmartSliceScene.Root)

        if not self._smart_slice_scene_node:
            Logger.warning("No SmartSlice node found for creating boundary conditions")
            return

        self._smart_slice_scene_node.childrenChanged.connect(self._smartSliceSceneChanged)

        self._populateList()

    def _populateList(self):
        if self._bc_type == BoundaryConditionListModel.Anchor:
            node_type = SmartSliceScene.AnchorFace
        else:
            node_type = SmartSliceScene.LoadFace

        self._active_node = None

        self.beginRemoveRows(QModelIndex(), 0, len(self._bcs) - 1)
        self._bcs.clear()
        self.endRemoveRows()

        for c in self._smart_slice_scene_node.getChildren():
            if isinstance(c, node_type):
                self._bcs.append(c)

        self.beginInsertRows(QModelIndex(), 0, len(self._bcs) - 1)
        self.endInsertRows()

        self.select()

    def _smartSliceSceneChanged(self, node=None):
        self._populateList()

    def getActiveNode(self):
        return self._active_node

    def roleNames(self):
        return {
            0: b'name'
        }

    @pyqtProperty(int)
    def boundaryConditionType(self) -> int:
        return self._bc_type

    @boundaryConditionType.setter
    def boundaryConditionType(self, value: int):
        self._bc_type = value
        self._setup()

    @pyqtProperty(bool, notify=loadDirectionChanged)
    def loadDirection(self) -> bool:
        if isinstance(self._active_node, SmartSliceScene.LoadFace):
            return self._active_node.force.pull
        return False

    @loadDirection.setter
    def loadDirection(self, value: bool):
        if isinstance(self._active_node, SmartSliceScene.LoadFace):
            self._active_node.setArrowDirection(value)
            self._smart_slice_scene_node.magnitudeChanged()

    @pyqtProperty(float, notify=loadMagnitudeChanged)
    def loadMagnitude(self) -> float:
        if isinstance(self._active_node, SmartSliceScene.LoadFace):
            return self._active_node.force.magnitude
        return 0.0

    @loadMagnitude.setter
    def loadMagnitude(self, value: float):
        if isinstance(self._active_node, SmartSliceScene.LoadFace):
            self._active_node.force.magnitude = value
            self._smart_slice_scene_node.magnitudeChanged()

    @pyqtSlot(QObject, result=int)
    def rowCount(self, parent=None) -> int:
        return len(self._bcs)

    def data(self, index, role):
        if len(self._bcs) > index.row():
            if role == 0:
                return self._bcs[index.row()].getName()
        return None

    @pyqtSlot(int)
    def activate(self, index=0):
        for n in self._bcs:
            n.setVisible(False)

        if index >= 0 and len(self._bcs) > index:
            self.select(index)
        elif len(self._bcs) > 0:
            self.select(0)

        if isinstance(self._active_node, SmartSliceScene.LoadFace):
            self.loadMagnitudeChanged.emit(self._active_node)

        active_tool = CuraApplication.getInstance().getController().getActiveTool()

        if active_tool:
            active_tool.setActiveBoundaryConditionList(self)

        if not self._bcs and self._smart_slice_scene_node:
            self.add()

    @pyqtSlot()
    def deactivate(self):
        for n in self._bcs:
            n.setVisible(False)

    @pyqtSlot()
    def add(self):
        if len(self._bcs) == 0:
            N = 1
        else:
            N = int(self._bcs[-1].getName().split(" ")[1]) + 1

        if self._bc_type == BoundaryConditionListModel.Anchor:
            bc = SmartSliceScene.AnchorFace('Anchor ' + str(N))
        else:
            bc = SmartSliceScene.LoadFace('Load ' + str(N))
            bc.force.magnitude = 10.0

        self._smart_slice_scene_node.addFace(bc)

    @pyqtSlot(int)
    def remove(self, index=None):
        if index is not None and len(self._bcs) > index:
            self._smart_slice_scene_node.removeFace(self._bcs[index])

    @pyqtSlot(int)
    def select(self, index=None):
        for n in self._bcs:
            n.setVisible(False)

        if index is not None and 0 <= index < len(self._bcs):
            self._active_node = self._bcs[index]

        if self._active_node:
            self._active_node.setVisible(True)

        if self._smart_slice_scene_node:
            CuraApplication.getInstance().getController().getScene().sceneChanged.emit(
                self._smart_slice_scene_node
            )
