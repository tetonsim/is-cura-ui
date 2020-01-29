#######################################
#   SmartSliceStage.py
#   Teton Simulation, Inc; Ultimaker
#   Last Modified October 17, 2019
#######################################

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


#   Filesystem Control
import os.path

#   Expose Ultimaker/Cura API
from UM.Logger import Logger
from UM.Application import Application
from UM.PluginRegistry import PluginRegistry

from cura.Stages.CuraStage import CuraStage
from cura.CuraApplication import CuraApplication

#
#   Stage Class Definition
#
class SmartSliceStage(CuraStage):
    def __init__(self, parent=None):
        super().__init__(parent)

        #   Connect Stage to Cura Application
        Application.getInstance().engineCreatedSignal.connect(self._engineCreated)
        self._connector = PluginRegistry.getInstance().getPluginObject("SmartSliceExtension").cloud

        #   Set Default Attributes
        self._was_buildvolume_hidden = None
        self._was_overhang_visible = None
        self._overhang_visible_preference = "view/show_overhang"
        self._default_toolset = None
        self._default_fallback_tool = None
        self._our_toolset = ("SmartSliceSelectTool",
                             "SmartSliceRequirements",
                             )
        #self._tool_blacklist = ("SelectionTool", "CameraTool")
        self._our_last_tool = None
        self._were_tools_enabled = None
        self._was_selection_face = None

    #   onStageSelected:
    #       This transitions the userspace/working environment from
    #       current stage into the Smart Slice User Environment.
    def onStageSelected(self):
        application = Application.getInstance()
        
        buildvolume = application.getBuildVolume()
        if buildvolume.isVisible():
            buildvolume.setVisible(False)
            self._was_buildvolume_hidden = True
            
        # Overhang visiualization
        self._was_overhang_visible = application.getPreferences().getValue(self._overhang_visible_preference)
        application.getPreferences().setValue(self._overhang_visible_preference, False)

        # Ensure we have tools defined and apply them here
        req_tool = self._our_toolset[1]
        our_tool = self._our_toolset[0]
        self.setToolVisibility(True)
        application.getController().setFallbackTool(req_tool) # Force __init__()
        application.getController().setFallbackTool(our_tool)
        self._previous_tool = application.getController().getActiveTool()
        #if self._previous_tool:
        #    application.getController().setActiveTool(our_tool)

        #  Set the Active Extruder for the Cloud interactions
        self._connector._proxy._activeMachineManager = CuraApplication.getInstance().getMachineManager()
        self._connector._proxy._activeExtruder = self._connector._proxy._activeMachineManager._global_container_stack.extruderList[0]

        self._connector.propertyHandler.cacheChanges()
        
    #   onStageDeselected:
    #       Sets attributes that allow the Smart Slice Stage to properly deactivate
    #       This occurs before the next Cura Stage is activated
    def onStageDeselected(self):
        application = Application.getInstance()
        
        if self._was_buildvolume_hidden:
            buildvolume = application.getBuildVolume()
            buildvolume.setVisible(True)
            self._is_buildvolume_hidden = None

        if self._was_overhang_visible is not None:
            application.getPreferences().setValue(self._overhang_visible_preference,
                                                  self._was_overhang_visible)

        # Recover if we have tools defined
        self.setToolVisibility(False)
        application.getController().setFallbackTool(self._default_fallback_tool)
        if self._previous_tool:
            application.getController().setActiveTool(self._default_fallback_tool)

        #  Hide all visible SmartSlice UI Components

        

    def getVisibleTools(self):
        visible_tools = []
        tools = Application.getInstance().getController().getAllTools().keys()
        for tool in tools:
            visible = True
            tool_metainfo = PluginRegistry.getInstance().getMetaData(tool).get("tool", {})
            keys = tool_metainfo.keys()
            if "visible" in keys:
                visible = tool_metainfo["visible"]

            if visible:
                visible_tools.append(tool)
        return visible_tools

    def setToolVisibility(self, our_tools_visible):
        plugin_registry = PluginRegistry.getInstance()
        for tool_id in Application.getInstance().getController().getAllTools().keys():
            tool_metadata = plugin_registry.getMetaData(tool_id)
            if tool_id in self._our_toolset:
                tool_metadata.get("tool", {})["visible"] = our_tools_visible
            elif tool_id in self._default_toolset:
                tool_metadata.get("tool", {})["visible"] = not our_tools_visible

            if "visible" in tool_metadata.get("tool", {}).keys():
                state = tool_metadata.get("tool", {})["visible"]
                Logger.log("d", "Visibility of <{}>: {}".format(tool_id, state))

        Application.getInstance().getController().toolsChanged.emit()

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

        base_path = PluginRegistry.getInstance().getPluginPath("SmartSliceStage")

        # Slicing windows in lower right corner
        component_path = os.path.join(base_path, "ui", "SmartSliceMain.qml")
        self.addDisplayComponent("main", component_path)

        # Top menu bar of stage
        component_path = os.path.join(base_path, "ui", "SmartSliceMenu.qml")
        self.addDisplayComponent("menu", component_path)

        # Setting state after all plugins are loaded
        self._was_buildvolume_hidden = not Application.getInstance().getBuildVolume().isVisible()

        # Get all visible tools and exclude our tools from the list
        self._default_toolset = self.getVisibleTools()
        for tool in self._default_toolset:
            if tool in self._our_toolset:
                self._default_toolset.remove(tool)
                
        self._default_fallback_tool = Application.getInstance().getController().getFallbackTool()

        # Undisplay our tools!
        self.setToolVisibility(False)
