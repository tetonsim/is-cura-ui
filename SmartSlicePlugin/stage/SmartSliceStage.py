#
#   Contains backend-interface for Smart Slice Stage
#
#   A STAGE is the component within Cura that contains all other
#   related major features.  This provides a vehicle to transition
#   between Smart Slice and other major Cura stages (e.g. 'Prepare')
#
#   SmartSliceStage is responsible for transitioning into the Smart
#   Slice user environment. This enables SmartSlice features, such as
#   setting anchors/loads and requesting AWS jobs.
#

import os.path

from PyQt5.QtCore import pyqtProperty
from PyQt5.QtCore import QObject

from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Application import Application
from UM.PluginRegistry import PluginRegistry
from UM.Message import Message
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Signal import Signal
from UM.Version import Version
from UM.View.GL.OpenGL import OpenGL

from cura.Stages.CuraStage import CuraStage
from cura.CuraApplication import CuraApplication

from . import SmartSliceScene
from ..utils import findChildSceneNode, getPrintableNodes
from ..utils import getModifierMeshes, intersectingNodes

i18n_catalog = i18nCatalog("smartslice")


#
#   Stage Class Definition
#
class SmartSliceStage(CuraStage):
    smartSliceNodeChanged = Signal()

    def __init__(self, extension, parent=None):
        super().__init__(parent)

        app = CuraApplication.getInstance()

        self.smartslice_messages = []
        self.visible_smartslice_messages = []

        #   Connect Stage to Cura Application
        app.engineCreatedSignal.connect(self._engineCreated)
        app.activityChanged.connect(self._checkScene)

        self._connector = extension

        self._previous_view = None
        self._previous_tool = None

        self._extruderDialog = None

        #   Set Default Attributes
        self._default_toolset = None
        self._default_fallback_tool = None
        self._our_toolset = (
            "SmartSlicePlugin_SelectTool",
            "SmartSlicePlugin_RequirementsTool",
        )

        self._invalid_scene_message = None
        self._parent_prompt = None

    @staticmethod
    def getInstance() -> 'SmartSliceStage':
        return Application.getInstance().getController().getStage(
            "SmartSlicePlugin"
        )

    @pyqtProperty(QObject, constant=True)
    def proxy(self):
        return self._connector.getProxy()

    @pyqtProperty(QObject, constant=True)
    def api(self):
        return self._connector.getAPI()

    def _scene_not_ready(self, text):
        app = CuraApplication.getInstance()

        if self._invalid_scene_message and self._invalid_scene_message.visible:
            self._invalid_scene_message.hide()

        title = i18n_catalog.i18n("Invalid print for Smart Slice")

        self._invalid_scene_message = Message(
            title=title, text=text, lifetime=30, dismissable=True
        )
        self._invalid_scene_message.show()

        app.getController().setActiveStage("PrepareStage")

    def _exit_stage_if_scene_is_invalid(self):
        printable_nodes = getPrintableNodes()
        if len(printable_nodes) == 0:
            self._scene_not_ready(
                i18n_catalog.i18n("Smart Slice requires a printable model on the build plate.")
            )
            return None
        elif len(printable_nodes) > 1:
            self._scene_not_ready(
                i18n_catalog.i18n(
                    "Only one printable model can be used with Smart Slice. " + \
                    "Please remove any additional models."
                )
            )
            return None
        return printable_nodes[0]

    #   onStageSelected:
    #       This transitions the userspace/working environment from
    #       current stage into the Smart Slice User Environment.
    def onStageSelected(self):
        if not SmartSliceStage.getSelectFaceSupported():
            error_message = Message(
                title="Smart Slice: OpenGL error",
                text="You are running an outdated version of OpenGL which may not"
                     " support selecting faces in Smart Slice. Please update OpenGL to at least version 4.1"
            )
            error_message.show()

        application = CuraApplication.getInstance()
        controller = application.getController()
        extruderManager = application.getExtruderManager()

        Selection.clear()

        printable_node = self._exit_stage_if_scene_is_invalid()

        if not printable_node:
            return

        self._previous_view = controller.getActiveView().name

        self._connector.api_connection.openConnection()

        # When the Smart Slice stage is active we want to use our SmartSliceView
        # to control the rendering of various nodes. Views are referred to by their
        # plugin name.
        controller.setActiveView('SmartSlicePlugin')

        self._connector.propertyHandler.jobCheck()

        if not Selection.hasSelection():
            Selection.add(printable_node)

        aabb = printable_node.getBoundingBox()
        if aabb:
            controller.getCameraTool().setOrigin(aabb.center)

        smart_slice_node = findChildSceneNode(printable_node, SmartSliceScene.Root)

        if not smart_slice_node:
            smart_slice_node = SmartSliceScene.Root()

            try:
                smart_slice_node.initialize(printable_node)
            except Exception as exc:
                Logger.logException("e", "Unable to analyze geometry")
                self._scene_not_ready(
                    i18n_catalog.i18n("Smart Slice could not analyze the geometry for face selection. It may be ill-formed.")
                )
                if smart_slice_node:
                    printable_node.removeChild(smart_slice_node)
                return

            self.smartSliceNodeChanged.emit(smart_slice_node)

        for c in controller.getScene().getRoot().getAllChildren():
            if isinstance(c, SmartSliceScene.Root):
                c.setVisible(True)

        for mesh in getModifierMeshes():
            mesh.setSelectable(False)

            # Remove any HighlightFace if they exist
            for node in mesh.getChildren():
                if isinstance(node, SmartSliceScene.HighlightFace):
                    mesh.removeChild(node)
                elif isinstance(node, SmartSliceScene.Root):
                    mesh.removeChild(node)

        # We have modifier meshes in the scene, we need to change their parent
        # to the intersecting printable node
        if self._changeParent():
            self._parentAssigned()

        # Ensure we have tools defined and apply them here
        use_tool = self._our_toolset[0]
        self.setToolVisibility(True)
        controller.setFallbackTool(use_tool)
        self._previous_tool = controller.getActiveTool()
        if self._previous_tool:
            controller.setActiveTool(use_tool)

        self._connector.updateSliceWidget()

        if self._invalid_scene_message and self._invalid_scene_message.visible:
            self._invalid_scene_message.hide()

    #   onStageDeselected:
    #       Sets attributes that allow the Smart Slice Stage to properly deactivate
    #       This occurs before the next Cura Stage is activated
    def onStageDeselected(self):
        application = CuraApplication.getInstance()
        controller = application.getController()
        if self._previous_view:
            controller.setActiveView(self._previous_view)

        # Recover if we have tools defined
        self.setToolVisibility(False)
        controller.setFallbackTool(self._default_fallback_tool)
        if self._previous_tool:
            controller.setActiveTool(self._default_fallback_tool)

        for c in controller.getScene().getRoot().getAllChildren():
            if isinstance(c, SmartSliceScene.Root):
                c.setVisible(False)
            elif isinstance(c, SmartSliceScene.HighlightFace):
                c.setVisible(False)

        for mesh in getModifierMeshes():
            mesh.setSelectable(True)

    @staticmethod
    def getVisibleTools():
        visible_tools = []
        tools = CuraApplication.getInstance().getController().getAllTools()

        for name in tools:
            visible = True
            tool_metainfo = tools[name].getMetaData()

            if "visible" in tool_metainfo.keys():
                visible = tool_metainfo["visible"]

            if visible:
                visible_tools.append(name)

            Logger.log(
                "d", "Visibility of <{}>: {}".format(name, visible)
            )

        return visible_tools

    # Function to make our tools either visible or not and the other tools the opposite
    def setToolVisibility(self, our_tools_visible):
        controller = CuraApplication.getInstance().getController()
        tools = controller.getAllTools()

        for name in tools:
            tool_meta_data = tools[name].getMetaData()

            if name in self._our_toolset:
                tool_meta_data["visible"] = our_tools_visible
                controller.toolEnabledChanged.emit(name, our_tools_visible)
            elif name in self._default_toolset:
                tool_meta_data["visible"] = not our_tools_visible
                controller.toolEnabledChanged.emit(name, not our_tools_visible)

            Logger.log(
                "d", "Visibility of <{}>: {}".format(name, tool_meta_data["visible"])
            )

        # Turn off face to lay flat mode if it's on
        if tools["RotateTool"].getSelectFaceToLayFlatMode() and our_tools_visible:
            tools["RotateTool"].setSelectFaceToLayFlatMode(False)

        CuraApplication.getInstance().getController().toolsChanged.emit()

    @property
    def our_toolset(self):
        """
        Generates a dictionary of tool id and instance from our id list in __init__.
        """
        our_toolset_with_objects = {}
        for tool in self._our_toolset:
            our_toolset_with_objects[tool] = PluginRegistry.getInstance().getPluginObject(tool)
        return our_toolset_with_objects

    @property
    def our_first_tool(self):
        """
        Takes the first tool if out of our tool dictionary.
        Defining a dict here is the way Cura's controller works.
        """
        return list(self.our_toolset.keys())[0]

    def _engineCreated(self):
        """
        Executed when the Qt/QML engine is up and running.
        This is at the time when all plugins are loaded, slots registered and basic signals connected.
        """

        base_path = PluginRegistry.getInstance().getPluginPath("SmartSlicePlugin")

        # Slicing windows in lower right corner
        component_path = os.path.join(base_path, "stage", "ui", "SmartSliceMain.qml")
        self.addDisplayComponent("main", component_path)

        # Top menu bar of stage
        component_path = os.path.join(base_path, "stage", "ui", "SmartSliceMenu.qml")
        self.addDisplayComponent("menu", component_path)

        # Get all visible tools and exclude our tools from the list
        self._default_toolset = self.getVisibleTools()
        for tool in self._default_toolset:
            if tool in self._our_toolset:
                self._default_toolset.remove(tool)

        self._default_fallback_tool = CuraApplication.getInstance().getController().getFallbackTool()

        # Undisplay our tools!
        self.setToolVisibility(False)

    def _checkScene(self):
        active_stage = CuraApplication.getInstance().getController().getActiveStage()

        if active_stage and active_stage.getPluginId() == self.getPluginId():
            self._exit_stage_if_scene_is_invalid()

    def _parentAssigned(self):
        if not self._parent_prompt:
            self._parent_prompt = Message(
                title="Smart Slice",
                text="Modifier meshes without an assigned parent have been added as a child to the intersecting printable model.",
                lifetime=15,
                dismissable=True
            )

        self._parent_prompt.show()

    def _changeParent(self) -> bool:
        if len(getModifierMeshes()) == 0:
            return False

        parent_changed = False
        for node in getPrintableNodes():
            for intersecting_node in intersectingNodes(node):
                if intersecting_node.getParent() != node:
                    position = intersecting_node.getWorldPosition()
                    intersecting_node.setParent(node)
                    intersecting_node.setPosition(position, SceneNode.TransformSpace.World)
                    parent_changed = True

        return parent_changed

    ##  Get whether the select face feature is supported.
    #   \return True if it is supported, or False otherwise.
    @staticmethod
    def getSelectFaceSupported() -> bool:
        # Use a dummy postfix, since an equal version with a postfix is considered smaller normally.
        return Version(OpenGL.getInstance().getOpenGLVersion()) >= Version("4.1 dummy-postfix")
