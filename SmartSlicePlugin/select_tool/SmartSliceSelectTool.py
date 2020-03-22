import numpy

from PyQt5.QtCore import pyqtProperty

from UM.i18n import i18nCatalog

from UM.Application import Application
from UM.Version import Version
from UM.Logger import Logger
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Signal import Signal
from UM.Tool import Tool

from UM.View.GL.OpenGL import OpenGL
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode

#  Local Imports
from ..utils import makeInteractiveMesh
from .SmartSliceSelectHandle import SelectionMode
from .SmartSliceSelectHandle import SmartSliceSelectHandle

i18n_catalog = i18nCatalog("smartslice")

class Force:
    def __init__(self, normal : Vector = None, magnitude : float = 0.0, pull : bool = True):
        self.normal = normal if normal else Vector(1.0, 0.0, 0.0)
        self.magnitude = magnitude
        self.pull = pull

    def loadVector(self, rotation : Matrix = None) -> Vector:
        scale = self.magnitude if self.pull else -self.magnitude

        v = Vector(
            self.normal.x * scale,
            self.normal.y * scale,
            self.normal.z * scale,
        )

        if rotation:
            vT = numpy.dot(rotation.getData(), v.getData())
            return Vector(vT[0], vT[1], vT[2])

        return v

class SmartSliceSelectTool(Tool):
    def __init__(self, extension : 'SmartSliceExtension'):
        super().__init__()
        self.extension = extension
        self._handle = SmartSliceSelectHandle(self.extension, self)

        self.setExposedProperties(
            "AnchorSelectionActive",
            "LoadSelectionActive",
            "SelectionMode",
            "LoadMagnitude",
            "LoadDirection"
        )

        Selection.selectedFaceChanged.connect(self._onSelectedFaceChanged)

        self._scene = self.getController().getScene()
        self._scene_node_name = None
        self._interactive_mesh = None # pywim.geom.tri.Mesh
        self._load_face = None
        self._anchor_face = None

        self.force = Force(magnitude=10.)

        self._controller.activeToolChanged.connect(self._onActiveStateChanged)

    toolPropertyChanged = Signal()

    @staticmethod
    def getInstance():
        return Application.getInstance().getController().getTool(
            "SmartSlicePlugin_SelectTool"
        )

    @pyqtProperty(float)
    def loadMagnitude(self):
        return self.force.magnitude

    @loadMagnitude.setter
    def loadMagnitude(self, value : float):
        self.force.magnitude = float(value)
        Logger.log("d", "Load magnitude changed, new force vector: {}".format(self.force.loadVector()))
        self.toolPropertyChanged.emit("LoadMagnitude")

    @pyqtProperty(bool)
    def loadDirection(self):
        return self.force.pull

    @loadDirection.setter
    def loadDirection(self, value : bool):
        self.force.pull = bool(value)
        self._handle.drawSelection()
        Logger.log("d", "Load direction changed, new force vector: {}".format(self.force.loadVector()))
        self.toolPropertyChanged.emit("LoadDirection")

    # These additional getters/setters are necessary to work with setting properties
    # from QML via the UM.ActiveToolProxy
    def getLoadMagnitude(self) -> float:
        return self.loadMagnitude

    def setLoadMagnitude(self, value : float):
        self.loadMagnitude = value

    def getLoadDirection(self) -> bool:
        return self.loadDirection

    def setLoadDirection(self, value : bool):
        self.loadDirection = value

    def _calculateMesh(self):
        scene = Application.getInstance().getController().getScene()
        nodes = Selection.getAllSelectedObjects()

        if len(nodes) > 0:
            sn = nodes[0]
            #self._handle._connector._proxy._activeExtruderStack = nodes[0].callDecoration("getExtruderStack")

            if self._scene_node_name is None or sn.getName() != self._scene_node_name:

                mesh_data = sn.getMeshData()

                if mesh_data:
                    Logger.log('d', 'Compute interactive mesh from SceneNode {}'.format(sn.getName()))

                    self._scene_node_name = sn.getName()
                    self._interactive_mesh = makeInteractiveMesh(mesh_data)
                    self._load_face = None
                    self._anchor_face = None

                    self._handle.clearSelection()
                    self._handle._connector._proxy._anchorsApplied = 0
                    self._handle._connector._proxy._loadsApplied = 0
                    self.extension.cloud._onApplicationActivityChanged()

                    controller = Application.getInstance().getController()
                    camTool = controller.getCameraTool()
                    aabb = sn.getBoundingBox()
                    if aabb:
                        camTool.setOrigin(aabb.center)

    def _onSelectedFaceChanged(self, curr_sf=None):
        if not self.getEnabled():
            return

        curr_sf = Selection.getSelectedFace()
        if curr_sf is None:
            return

        self._calculateMesh()

        scene_node, face_id = curr_sf

        self._handle._connector.propertyHandler.onSelectedFaceChanged(scene_node, face_id)

        loadedTris = self._handle._connector.propertyHandler._loadedTris
        if self.getLoadSelectionActive() and loadedTris:
            # Convert from a pywim.geom.Vector to UM.Math.Vector
            self.force.normal = Vector(
                loadedTris[0].normal.r,
                loadedTris[0].normal.s,
                loadedTris[0].normal.t
            )

    def setFaceVisible(self, scene_node, face_id):
        ph = self._handle._connector.propertyHandler

        if self.getAnchorSelectionActive():
            self._handle._arrow = False
            self._anchor_face = (ph._anchoredNode, ph._anchoredID)
            self._handle.setFace(ph._anchoredTris)

        else:
            self._handle._arrow = True
            self._load_face = (ph._loadedNode, ph._loadedID)
            self._handle.setFace(ph._loadedTris)

        Application.getInstance().activityChanged.emit()

    def _onActiveStateChanged(self):
        controller = Application.getInstance().getController()
        active_tool = controller.getActiveTool()
        Logger.log("d", "Application.getInstance().getController().getActiveTool(): {}".format(active_tool))

        if active_tool == self:
            stage = controller.getActiveStage()
            controller.setFallbackTool(stage._our_toolset[0])
            if Selection.hasSelection():
                Selection.setFaceSelectMode(True)
                Logger.log("d", "Enabled faceSelectMode!")
            else:
                Selection.setFaceSelectMode(False)
                Logger.log("d", "Disabled faceSelectMode!")

            self._calculateMesh()

    ##  Get whether the select face feature is supported.
    #   \return True if it is supported, or False otherwise.
    def getSelectFaceSupported(self) -> bool:
        # Use a dummy postfix, since an equal version with a postfix is considered smaller normally.
        return Version(OpenGL.getInstance().getOpenGLVersion()) >= Version("4.1 dummy-postfix")

    def setSelectionMode(self, mode):
        Selection.clearFace()
        self._handle._connector.propertyHandler._selection_mode = mode
        Logger.log("d", "Changed selection mode to enum: {}".format(mode))
        #self._handle._connector.propertyHandler.selectedFacesChanged.emit()
        #self._onSelectedFaceChanged()

    def getSelectionMode(self):
        return self._handle._connector.propertyHandler._selection_mode

    def setAnchorSelection(self):
        self._handle.clearSelection()
        self.setSelectionMode(SelectionMode.AnchorMode)
        if self._handle._connector._proxy._anchorsApplied > 0:
            self._handle.drawSelection()

    def getAnchorSelectionActive(self):
        return self._handle._connector.propertyHandler._selection_mode is SelectionMode.AnchorMode

    def setLoadSelection(self):
        self._handle.clearSelection()
        self.setSelectionMode(SelectionMode.LoadMode)
        if self._handle._connector._proxy._loadsApplied > 0:
            self._handle.drawSelection()

    def getLoadSelectionActive(self):
        return self._handle._connector.propertyHandler._selection_mode is SelectionMode.LoadMode
