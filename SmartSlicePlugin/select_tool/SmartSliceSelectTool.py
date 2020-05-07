import numpy

from PyQt5.QtCore import pyqtProperty

from UM.i18n import i18nCatalog

from UM.Application import Application
from UM.Logger import Logger
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Signal import Signal
from UM.Tool import Tool
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

class SmartSliceSelection:
    def __init__(self):
        self.triangles = [] # List[pywim.geom.tri.Triangle]

    def reset(self):
        self.triangles.clear()

    def triangleIds(self):
        return [t.id for t in self.triangles]

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

        self._selection_mode = SelectionMode.AnchorMode
        self._scene = self.getController().getScene()
        self._scene_node_name = None
        self._interactive_mesh = None # pywim.geom.tri.Mesh

        self.load_face = SmartSliceSelection()
        self.anchor_face = SmartSliceSelection()

        self.force = Force(magnitude=10.)

        self._controller.activeToolChanged.connect(self._onActiveStateChanged)

    toolPropertyChanged = Signal()
    selectedFaceChanged = Signal()

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
        fvalue = float(value)
        if self.force.pull == fvalue:
            return
        self.force.magnitude = fvalue

        Logger.log("d", "Load magnitude changed, new force vector: {}".format(self.force.loadVector()))

        self.propertyChanged.emit()
        self.toolPropertyChanged.emit("LoadMagnitude")

    @pyqtProperty(bool)
    def loadDirection(self):
        return self.force.pull

    @loadDirection.setter
    def loadDirection(self, value : bool):
        if self.force.pull == value:
            return
        self.force.pull = bool(value)
        self._handle.drawSelection(self._selection_mode)

        Logger.log("d", "Load direction changed, new force vector: {}".format(self.force.loadVector()))

        self.propertyChanged.emit()
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

            if self._scene_node_name is None or sn.getName() != self._scene_node_name:

                mesh_data = sn.getMeshData()

                if mesh_data:
                    Logger.log('d', 'Compute interactive mesh from SceneNode {}'.format(sn.getName()))

                    self._scene_node_name = sn.getName()
                    self._interactive_mesh = makeInteractiveMesh(mesh_data)

                    self.load_face.reset()
                    self.anchor_face.reset()

                    self._handle.clearSelection()

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

        selected_triangles = list(self._interactive_mesh.select_planar_face(face_id))

        if self.getLoadSelectionActive():
            self.load_face.triangles = selected_triangles

            if len(self.load_face.triangles) > 0:
                tri = self.load_face.triangles[0]

                # Convert from a pywim.geom.Vector to UM.Math.Vector
                self.force.normal = Vector(
                    tri.normal.r,
                    tri.normal.s,
                    tri.normal.t
                )
        else:
            self.anchor_face.triangles = selected_triangles

        self._handle.drawSelection(self._selection_mode, selected_triangles)

        self.selectedFaceChanged.emit()

        #self.extension.cloud.prepareValidation()

    def redraw(self):
        if not self.getEnabled():
            return

        if self.getLoadSelectionActive():
            self._handle.drawSelection(self._selection_mode, self.load_face.triangles)
        else:
            self._handle.drawSelection(self._selection_mode, self.anchor_face.triangles)

    def _onActiveStateChanged(self):
        if not self.getEnabled():
            return

        controller = Application.getInstance().getController()
        stage = controller.getActiveStage()

        if stage.getPluginId() == self.getPluginId():
            controller.setFallbackTool(stage._our_toolset[0])

        if Selection.hasSelection():
            Selection.setFaceSelectMode(True)
            Logger.log("d", "Enabled faceSelectMode!")
        else:
            Selection.setFaceSelectMode(False)
            Logger.log("d", "Disabled faceSelectMode!")

        self._calculateMesh()

    def setSelectionMode(self, mode):
        Selection.clearFace()
        self._selection_mode = mode
        Logger.log("d", "Changed selection mode to enum: {}".format(mode))

    def getSelectionMode(self):
        return self._selection_mode

    def setAnchorSelection(self):
        self.setSelectionMode(SelectionMode.AnchorMode)

        self._handle.clearSelection()

        if len(self.anchor_face.triangles) > 0:
            self._handle.drawSelection(
                self._selection_mode,
                self.anchor_face.triangles
            )

    def getAnchorSelectionActive(self):
        return self._selection_mode is SelectionMode.AnchorMode

    def setLoadSelection(self):
        self.setSelectionMode(SelectionMode.LoadMode)

        self._handle.clearSelection()

        if len(self.load_face.triangles) > 0:
            self._handle.drawSelection(
                self._selection_mode,
                self.load_face.triangles
            )

    def getLoadSelectionActive(self):
        return self._selection_mode is SelectionMode.LoadMode
