import numpy

import pywim

from PyQt5.QtCore import pyqtProperty

from UM.i18n import i18nCatalog

from UM.Application import Application
from UM.Logger import Logger
from UM.Math.Matrix import Matrix
from UM.Signal import Signal
from UM.Tool import Tool
from UM.Scene.Selection import Selection
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator

from ..stage import SmartSliceScene
from ..stage import SmartSliceStage
from ..utils import getPrintableNodes
from ..utils import findChildSceneNode
from .BoundaryConditionList import BoundaryConditionListModel

i18n_catalog = i18nCatalog("smartslice")


class SelectionMode:
    AnchorMode = 1
    LoadMode = 2


class SmartSliceSelectTool(Tool):
    def __init__(self, extension: 'SmartSliceExtension'):
        super().__init__()
        self.extension = extension

        self._connector = extension.cloud  # SmartSliceCloudConnector
        self._mode = SelectionMode.AnchorMode

        self.setExposedProperties(
            "AnchorSelectionActive",
            "LoadSelectionActive",
            "SelectionMode",
        )

        Selection.selectedFaceChanged.connect(self._onSelectedFaceChanged)

        self._selection_mode = SelectionMode.AnchorMode

        self._bc_list = None

        self._controller.activeToolChanged.connect(self._onActiveStateChanged)

    toolPropertyChanged = Signal()
    selectedFaceChanged = Signal()

    @staticmethod
    def getInstance():
        return Application.getInstance().getController().getTool(
            "SmartSlicePlugin_SelectTool"
        )

    def setActiveBoundaryConditionList(self, bc_list):
        self._bc_list = bc_list

    def _onSelectionChanged(self):
        super()._onSelectionChanged()

    def updateFromJob(self, job: pywim.smartslice.job.Job):
        """
        When loading a saved smart slice job, get all associated smart slice selection data and load into scene
        """
        self._bc_list = None

        normal_mesh = getPrintableNodes()[0]

        smart_slice_node = findChildSceneNode(normal_mesh, SmartSliceScene.Root)
        if smart_slice_node is None:
            # add smart slice scene to node
            SmartSliceScene.Root().initialize(normal_mesh)
            smart_slice_node = findChildSceneNode(normal_mesh, SmartSliceScene.Root)

        self.setActiveBoundaryConditionList(BoundaryConditionListModel())

        step = job.chop.steps[0]

        smart_slice_node.loadStep(step)
        smart_slice_node.setOrigin()

        self.redraw()

        controller = Application.getInstance().getController()
        for c in controller.getScene().getRoot().getAllChildren():
            if isinstance(c, SmartSliceScene.Root):
                c.setVisible(False)

        return

    def _onSelectedFaceChanged(self, curr_sf=None):
        """
        Gets face id and triangles from current face selection
        """
        if getPrintableNodes() and Selection.isSelected(getPrintableNodes()[0]): # Fixes bug for when scene is unselected
            if not self.getEnabled():
                return

            curr_sf = Selection.getSelectedFace()
            if curr_sf is None:
                return

            node, face_id = curr_sf

            if self._bc_list is None:
                return

            bc_node = self._bc_list.getActiveNode()

            if bc_node is None:
                return

            smart_slice_node = findChildSceneNode(node, SmartSliceScene.Root)

            selected_triangles = list(smart_slice_node.getInteractiveMesh().select_planar_face(face_id))

            bc_node.setMeshDataFromPywimTriangles(selected_triangles)

            self._connector.updateStatus()

            self.selectedFaceChanged.emit()

    def redraw(self):
        if not self.getEnabled():
            return

    def _onActiveStateChanged(self):
        if not self.getEnabled():
            return

        controller = Application.getInstance().getController()
        stage = controller.getActiveStage()

        if stage.getPluginId() == self.getPluginId():
            controller.setFallbackTool(stage._our_toolset[0])
        else:
            return

        if Selection.hasSelection():
            Selection.setFaceSelectMode(True)
            Logger.log("d", "Enabled faceSelectMode!")
        else:
            Selection.setFaceSelectMode(False)
            Logger.log("d", "Disabled faceSelectMode!")

        self.extension.cloud._onApplicationActivityChanged()

    def setSelectionMode(self, mode):
        Selection.clearFace()
        self._selection_mode = mode
        Logger.log("d", "Changed selection mode to enum: {}".format(mode))

    def getSelectionMode(self):
        return self._selection_mode

    def setAnchorSelection(self):
        self.setSelectionMode(SelectionMode.AnchorMode)

    def getAnchorSelectionActive(self):
        return self._selection_mode is SelectionMode.AnchorMode

    def setLoadSelection(self):
        self.setSelectionMode(SelectionMode.LoadMode)

    def getLoadSelectionActive(self):
        return self._selection_mode is SelectionMode.LoadMode
