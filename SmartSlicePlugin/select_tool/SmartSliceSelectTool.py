from typing import Tuple, List, cast

import numpy
import time

import pywim

from PyQt5.QtCore import pyqtProperty

from UM.i18n import i18nCatalog

from UM.Event import Event, MouseEvent
from UM.Application import Application
from UM.Logger import Logger
from UM.Math.Plane import Plane
from UM.Math.Quaternion import Quaternion
from UM.Signal import Signal
from UM.Tool import Tool
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Selection import Selection
from UM.Scene.ToolHandle import ToolHandle
from UM.PluginRegistry import PluginRegistry
from UM.View.SelectionPass import SelectionPass

from ..stage import SmartSliceScene
from ..utils import getPrintableNodes
from ..utils import findChildSceneNode
from ..utils import angleBetweenVectors
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
            "SurfaceType"
        )

        Selection.selectedFaceChanged.connect(self._onSelectedFaceChanged)

        self._selection_mode = SelectionMode.AnchorMode

        self._bc_list = None

        self._controller.activeToolChanged.connect(self._onActiveStateChanged)

        self._angle = None
        self._rotating = False
        self._select = True
        self._selected_face = None

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

    def _onSelectedFaceChanged(self, current_surface=None):
        """
        Gets face id and triangles from current face selection
        """
        if getPrintableNodes() and Selection.isSelected(getPrintableNodes()[0]): # Fixes bug for when scene is unselected
            if not self.getEnabled() or not self._select:
                return

            if self._bc_list is None:
                return

            bc_node = self._bc_list.getActiveNode()

            if bc_node is None:
                return

            try:
                selected_face, axis = self._getSelectedTriangles(current_surface, bc_node.surface_type)
            except Exception as exc:
                Logger.logException("e", "Unable to select face")
                selected_face = None

            if selected_face is not None:
                bc_node.selection = Selection.getSelectedFace()
                bc_node.setMeshDataFromPywimTriangles(selected_face, axis)

            self.selectedFaceChanged.emit(bc_node)

    def _getSelectedTriangles(
        self,
        current_surface : Tuple[SceneNode, int],
        surface_type : SmartSliceScene.HighlightFace.SurfaceType
    ) -> Tuple[pywim.geom.tri.Face, pywim.geom.Vector]:

        if current_surface is None:
            current_surface = Selection.getSelectedFace()

        if current_surface is None:
            return None, None

        node, face_id = current_surface

        smart_slice_node = findChildSceneNode(node, SmartSliceScene.Root)

        if surface_type == SmartSliceScene.HighlightFace.SurfaceType.Flat:
            selected_face = smart_slice_node._interactive_mesh.select_planar_face(face_id)
        elif surface_type == SmartSliceScene.HighlightFace.SurfaceType.Concave:
            selected_face = smart_slice_node._interactive_mesh.select_concave_face(face_id)
        elif surface_type == SmartSliceScene.HighlightFace.SurfaceType.Convex:
            selected_face = smart_slice_node._interactive_mesh.select_convex_face(face_id)

        axis = None
        if surface_type == SmartSliceScene.HighlightFace.SurfaceType.Flat:
            axis = selected_face.planar_axis()
        else:
            axis = selected_face.rotation_axis()

        return selected_face, axis

    def redraw(self):
        if not self.getEnabled():
            return

    def _onActiveStateChanged(self):

        stage = self._controller.getActiveStage()

        if stage.getPluginId() == self.getPluginId():
            self._controller.setFallbackTool(stage._our_toolset[0])
        else:
            return

        if Selection.hasSelection():
            # self._changeRenderMode(True)
            Selection.setFaceSelectMode(True)
            Logger.log("d", "Enabled faceSelectMode!")
        else:
            # self._changeRenderMode(False)
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

    def getSurfaceType(self):
        if self._bc_list:
            bc_node = self._bc_list.getActiveNode()
            if bc_node:
                return bc_node.surface_type

        return SmartSliceScene.HighlightFace.SurfaceType.Flat

    def setSurfaceType(self, surface_type : SmartSliceScene.HighlightFace.SurfaceType):
        if self._bc_list:
            bc_node = self._bc_list.getActiveNode()
            if bc_node:
                bc_node.surface_type = surface_type

    def setSurfaceTypeFlat(self):
        self.setSurfaceType(SmartSliceScene.HighlightFace.SurfaceType.Flat)

    def setSurfaceTypeConcave(self):
        self.setSurfaceType(SmartSliceScene.HighlightFace.SurfaceType.Concave)

    def setSurfaceTypeConvex(self):
        self.setSurfaceType(SmartSliceScene.HighlightFace.SurfaceType.Convex)

    def event(self, event: Event) -> bool:

        if not self._selection_pass:
            self._selection_pass = cast(SelectionPass, Application.getInstance().getRenderer().getRenderPass("selection"))
            if not self._selection_pass:
                return False

        # Tool activated - make sure we render the faces
        if event.type == Event.ToolActivateEvent:
            self._changeRenderMode(faces=True)
            self._enabled = True
            if self._bc_list and self._bc_list.getActiveNode():
                self._controller.getScene().sceneChanged.emit(self._bc_list.getActiveNode())
            return False

        # Tool deactivated - make sure we render the faces
        if event.type == Event.ToolDeactivateEvent:
            self._changeRenderMode(faces=False)
            self._enabled = False
            if self._bc_list and self._bc_list.getActiveNode():
                self._controller.getScene().sceneChanged.emit(self._bc_list.getActiveNode())
                self._bc_list = None
            return False

        if not self.getEnabled():
            return False

        # Not a load face - make sure we render faces
        if not self._bc_list or not self._bc_list.getActiveNode() or isinstance(self._bc_list.getActiveNode(), SmartSliceScene.AnchorFace):
            self._changeRenderMode(faces=True)
            return False

        active_node = self._bc_list.getActiveNode() # Load face
        rotator = active_node.getRotator()          # Rotator on the load face
        arrow = active_node.activeArrow             # Active arrow on the load face

        if event.type == Event.MousePressEvent:

            # Must be a left mouse event to select or rotate
            if MouseEvent.LeftButton not in event.buttons:
                return False

            pixel_color = self._selection_pass.getIdAtPosition(event.x, event.y)

            # We did not click the tool - we need to select the surface under it if it exists
            # TODO - This is a little hacky.... we should implement a SelectionPass just for this Tool
            if not pixel_color or not arrow.isAxis(pixel_color):
                if Selection.hasSelection() and not Selection.getFaceSelectMode():
                    self._changeRenderMode(faces=True)
                    select_tool = PluginRegistry.getInstance().getPluginObject("SelectionTool")
                    return select_tool.event(event)

            # Rotator isn't enabled - we don't need to do anything
            if not rotator.isEnabled():
                return False

            # If we made it here, we have clicked the tool. Set the locked color to our tool color, and set the plane
            # the user will be constrained to drag in
            self.setLockedAxis(pixel_color)
            self.setDragPlane(Plane(rotator.rotation_axis))

            self.setDragStart(event.x, event.y)
            self._rotating = True
            self._angle = 0
            return True

        if event.type == Event.MouseMoveEvent:

            # Rotator isn't enabled - we don't need to do anything
            if not rotator.isEnabled():
                return False

            event = cast(MouseEvent, event)

            # Turn the shader on for the rotator and arrow if the mouse is hovered on them
            # in the above, pixel_color is the color of the solid mesh of the pixekl the mouse is on
            # For some reason, "ActiveAxis" means the color of the tool we are interested in
            if not self._rotating:
                self._changeRenderMode(faces=False)
                pixel_color = self._selection_pass.getIdAtPosition(event.x, event.y)

                if rotator.isAxis(pixel_color):
                    rotator.setActiveAxis(pixel_color)
                    arrow.setActiveAxis(pixel_color)
                else:
                    rotator.setActiveAxis(None)
                    arrow.setActiveAxis(None)

                return False

            # We are rotating. Check to ensure we have a starting position for the mouse
            if not self.getDragStart():
                self.setDragStart(event.x, event.y)
                if not self.getDragStart(): #May have set it to None.
                    return False

            self.operationStarted.emit(self)

            drag_start = self.getDragStart() - rotator.center
            drag_position = self.getDragPosition(event.x, event.y)
            if not drag_position:
                return False
            drag_end = drag_position - rotator.center

            # Project the vectors back to the plane of the rotator
            drag_start = drag_start - drag_start.dot(rotator.rotation_axis) * rotator.rotation_axis
            drag_end = drag_end - drag_end.dot(rotator.rotation_axis) * rotator.rotation_axis

            angle = angleBetweenVectors(drag_start, drag_end)

            axes_length = (rotator.rotation_axis.normalized() - drag_end.cross(drag_start).normalized()).length()
            angle = -angle if axes_length < 1.e-2 else angle

            rotation = Quaternion.fromAngleAxis(angle, rotator.rotation_axis)

            self._angle += angle
            active_node.rotateArrow(angle)
            self.setDragStart(event.x, event.y)

            return True

        # Finished the rotation - reset everything and update the arrow direction
        if event.type == Event.MouseReleaseEvent:
            if self._rotating:
                self.setDragPlane(None)
                self.setLockedAxis(ToolHandle.NoAxis)
                self._angle = None
                self._rotating = False
                self.propertyChanged.emit()
                active_node.facePropertyChanged.emit(active_node)
                # self._changeRenderMode(faces=True)
                self.operationStopped.emit(self)

                return True

        return False

    def _changeRenderMode(self, faces=True):
        if Selection.hasSelection() and Selection.getFaceSelectMode() != faces:
            self._select = False
            Selection.setFaceSelectMode(faces)
            if self._selection_pass:
                self._selection_pass.render()
            self._select = True
