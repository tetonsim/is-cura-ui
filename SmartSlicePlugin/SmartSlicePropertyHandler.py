#
#  Contains procedures for handling Cura Properties in accordance with SmartSlice
#

import time, threading

from PyQt5.QtCore import QObject

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Message import Message
from UM.Logger import Logger
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.GroupedOperation import GroupedOperation

from cura.CuraApplication import CuraApplication

from .SmartSliceCloudStatus import SmartSliceCloudStatus
from .SmartSliceDecorator import SmartSliceRemovedDecorator
from .select_tool.SmartSliceSelectTool import SmartSliceSelectTool
from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements
from .utils import getModifierMeshes, getPrintableNodes, getNodeActiveExtruder
from .stage.SmartSliceScene import Root, HighlightFace, LoadFace

from . import SmartSliceProperty

import pywim

i18n_catalog = i18nCatalog("smartslice")

"""
  SmartSlicePropertyHandler(connector)
    connector: CloudConnector, used for interacting with rest of SmartSlice plugin

    The Property Handler contains functionality for manipulating all settings that
      affect Smart Slice validation/optimization results.

    It manages a cache of properties including Global/Extruder container properties
      retrieved from Cura's backend, as well as SmartSlice settings (e.g. Load/Anchor)
"""
class SmartSlicePropertyHandler(QObject):

    def __init__(self, connector):
        super().__init__()

        self.connector = connector
        self.proxy = connector._proxy

        controller = Application.getInstance().getController()

        self._global_properties = SmartSliceProperty.GlobalProperty.CreateAll()
        self._extruder_properties = SmartSliceProperty.ExtruderProperty.CreateAll()
        self._selected_material = SmartSliceProperty.SelectedMaterial()
        self._scene = SmartSliceProperty.Scene()
        self._root = SmartSliceProperty.SmartSliceSceneRoot()
        self._active_extruder = SmartSliceProperty.ActiveExtruder()

        self._mod_mesh_removal_msg = None

        sel_tool = SmartSliceSelectTool.getInstance()

        req_tool = SmartSliceRequirements.getInstance()

        self._req_tool_properties = [
            SmartSliceProperty.ToolProperty(req_tool, "TargetSafetyFactor"),
            SmartSliceProperty.ToolProperty(req_tool, "MaxDisplacement")
        ]

        self._properties = \
            self._global_properties + \
            self._extruder_properties + \
            self._req_tool_properties + \
            [
                self._scene,
                self._root,
                self._selected_material,
                self._active_extruder
            ]

        self._propertiesChanged = []

        self._activeMachineManager = CuraApplication.getInstance().getMachineManager()
        self._activeMachineManager.printerConnectedStatusChanged.connect(self.printerCheck)
        self.printerCheck()

        Root.faceAdded.connect(self._faceAdded)
        Root.faceRemoved.connect(self._faceRemoved)
        Root.rootChanged.connect(self._onRootChanged)

        HighlightFace.facePropertyChanged.connect(self._faceChanged)

        sel_tool.selectedFaceChanged.connect(self._faceChanged)
        sel_tool.toolPropertyChanged.connect(self._onSelectToolPropertyChanged)
        req_tool.toolPropertyChanged.connect(self._onRequirementToolPropertyChanged)

        controller.getScene().getRoot().childrenChanged.connect(self._onSceneNodeChanged)
        controller.getScene().rootChanged.connect(self._onSceneRootChanged)

        controller.getScene().getRoot().childrenChanged.connect(self.loadSceneNodes)
        controller.getScene().getRoot().childrenChanged.connect(self._reset)

        self._cancelChanges = False
        self._addProperties = True
        self._confirmDialog = None

        #  Attune to scene changes and mesh changes
        controller.getTool("ScaleTool").operationStopped.connect(self._onSceneNodeChanged)
        controller.getTool("RotateTool").operationStopped.connect(self._onSceneNodeChanged)

        CuraApplication.getInstance().getExtruderManager().activeExtruderChanged.connect(self._onActiveExtruderChanged)

        # Warnings for untested materials
        self._material_warnings = set() # Set[guid]

        # SmartSliceStage.SmartSliceStage.getInstance().smartSliceNodeChanged.connect(self._onSmartSliceNodeChanged)

    def _faceAdded(self, face):
        if isinstance(face, LoadFace):
            prop = SmartSliceProperty.SmartSliceLoadFace(face)
        else:
            prop = SmartSliceProperty.SmartSliceFace(face)

        prop.cache()
        self._properties.append(prop)
        self.confirmPendingChanges(self._root)

    def _faceChanged(self, face):
        for prop in self._properties:
            if isinstance(prop, SmartSliceProperty.SmartSliceFace) and face == prop.highlight_face:
                self.confirmPendingChanges(prop)
                break

    def _faceRemoved(self, face):
        for prop in self._properties:
            if isinstance(prop, SmartSliceProperty.SmartSliceFace) and face == prop.highlight_face:
                self._properties.remove(prop)
                break
        self.confirmPendingChanges(self._root)

    def _reset(self, *args):
        if len(getPrintableNodes()) == 0 and (not self._confirmDialog or not self._confirmDialog.visible):
            self.connector.clearJobs()
            self.resetProperties()

    #  Check that a printer has been set-up by the wizard.
    def printerCheck(self):
        if self._activeMachineManager.activeMachine is not None:
            self._onMachineChanged()
            self._activeMachineManager.activeMachine.propertyChanged.connect(self._onGlobalPropertyChanged)
            self._activeMachineManager.activeMaterialChanged.connect(self._onMaterialChanged)

    def jobCheck(self):
        show_warning = self._getMaterialGUID() not in self._material_warnings
        self.connector.updateStatus(show_warnings=show_warning)

    def buildSceneNode(self, node):
        scene_node = SmartSliceProperty.SceneNode(node, node.getName())
        self._properties.append(scene_node)
        Logger.log("d", "Tracking properties for {}".format(node.getName()))
        stack = node.callDecoration('getStack')
        stack.propertyChanged.connect(self._onSceneNodePropertyChanged)
        node.parentChanged.connect(scene_node.parentChanged)
        node.parentChanged.connect(self.sceneNodeRemoved)
        node.callDecoration("getActiveExtruderChangedSignal").connect(self._onSceneNodeChanged)
        scene_node.cache()

    def loadSceneNodes(self, root):
        names = [p.mesh_name for p in self._properties if isinstance(p, SmartSliceProperty.SceneNode)]
        for node in getPrintableNodes() + getModifierMeshes():
            if node.getName() not in names:
                self.buildSceneNode(node)

    def sceneNodeRemoved(self, parent_node):
        for property in self._properties:
            if isinstance(property, SmartSliceProperty.SceneNode) and property.parent_changed:
                Logger.log("d", "Stopped tracking for {}".format(property.mesh_name))
                self._properties.remove(property)
                break

    def cacheChanges(self):
        for p in self._properties:
            p.cache()

    def restoreCache(self):
        """
        Restores all cached values for properties upon user cancellation
        """

        for p in self._properties:
            if p.changed():
                p.restore()

        self._addProperties = False
        self._cleanRootCache()
        self._activeMachineManager.forceUpdateAllSettings()
        self._addProperties = True

    def _cleanRootCache(self):
        """
        Cleans the cache for the Root children and their individual tracking
        """
        highlight_faces = self._root.value()

        for prop in self._properties:
            if isinstance(prop, SmartSliceProperty.SmartSliceFace) and prop.highlight_face not in highlight_faces:
                self._properties.remove(prop)

        self._root.cache()

    def getProperty(self, key, property_name, context = None):
        for p in self._properties:
            if p.name == key:
                return p.value()
        return None

    def getGlobalProperty(self, key):
        for p in self._global_properties:
            if p.name == key:
                return p.value()

    def getExtruderProperty(self, key):
        for p in self._extruder_properties:
            if p.name == key:
                return p.value()

    def _onGlobalPropertyChanged(self, key: str, property_name: str):
        self.confirmPendingChanges(
            list(filter(lambda p: p.name == key, self._global_properties))
        )

    def _onExtruderPropertyChanged(self, key: str, property_name: str):
        self.confirmPendingChanges(
            list(filter(lambda p: p.name == key, self._extruder_properties))
        )

    def _onActiveExtruderChanged(self):
        self.confirmPendingChanges(self._active_extruder)

    def _onMachineChanged(self):
        active_extruder_index = CuraApplication.getInstance().getExtruderManager().activeExtruderIndex
        self._activeMachineManager.activeMachine.extruderList[active_extruder_index].propertyChanged.connect(self._onExtruderPropertyChanged)
        self.confirmPendingChanges([self._active_extruder, self._selected_material])

        self._onActiveExtruderChanged()
        CuraApplication.getInstance().getExtruderManager().activeExtruderChanged.connect(self._onActiveExtruderChanged)

    def _onMaterialChanged(self):
        self.confirmPendingChanges([self._active_extruder, self._selected_material])

        # If we've spawned a cancellation from the event, don't update the status
        if self._confirmDialog and self._confirmDialog.visible:
            return

        active_stage = CuraApplication.getInstance().getController().getActiveStage()

        if active_stage and active_stage.getPluginId() == self.connector.extension.getPluginId():
            self.connector.updateStatus(show_warnings=True)

        # If we're not in the stage, remove the GUID from the list of warnings so we'll show it again
        else:
            material_guid = self._getMaterialGUID()
            if material_guid and material_guid in self._material_warnings:
                self._material_warnings.remove(material_guid)

    def _getMaterialGUID(self):
        nodes = getPrintableNodes()
        if len(nodes) > 0:
            machine_extruder = getNodeActiveExtruder(nodes[0])
            return machine_extruder.material.getMetaData().get("GUID", "")
        return None

    def materialWarned(self, guid):
        if guid not in self._material_warnings:
            self._material_warnings.add(guid)

    def _onRootChanged(self, root: Root):
        if root is not None:
            self._root = SmartSliceProperty.SmartSliceSceneRoot(root)

            for prop in self._properties:
                if isinstance(prop, SmartSliceProperty.SmartSliceSceneRoot):
                    self._properties.remove(prop)
                    break

            self._properties.append(self._root)
            self._cleanRootCache()

    def _onSceneRootChanged(self, node=None):
        self._scene.cacheSmartSliceNodes()
        self.confirmPendingChanges(self._scene)

    def _onSceneNodeChanged(self, node=None):
        self._scene.cacheSmartSliceNodes()
        tracked_nodes = list(filter(lambda p: isinstance(p, SmartSliceProperty.SceneNode), self._properties))
        self.confirmPendingChanges(tracked_nodes + [self._scene])

    def _onSceneNodePropertyChanged(self, key=None, property_name=None):
        if key not in SmartSliceProperty.ExtruderProperty.NAMES:
            return

        self.confirmPendingChanges(
            list(filter(lambda p: isinstance(p, SmartSliceProperty.SceneNode), self._properties))
        )

    def _onSelectToolPropertyChanged(self, property_name):
        self.confirmPendingChanges(
            list(filter(lambda p: p.name == property_name, self._sel_tool_properties))
        )

    def _onRequirementToolPropertyChanged(self, property_name):
        # We handle changes in the requirements tool differently, depending on the current
        # status. We only need to ask for confirmation if the model has been optimized
        if self.connector.status in {SmartSliceCloudStatus.Underdimensioned, SmartSliceCloudStatus.Overdimensioned }:
            self.connector.prepareOptimization()
        else:
            self.confirmPendingChanges(
                list(filter(lambda p: p.name == property_name, self._req_tool_properties)),
                revalidationRequired=False
            )

        self.connector._proxy.targetSafetyFactorChanged.emit()
        self.connector._proxy.targetMaximalDisplacementChanged.emit()

    def confirmPendingChanges(self, props, revalidationRequired=True):
        if not props:
            return

        if isinstance(props, SmartSliceProperty.TrackedProperty):
            props = [props]

        changes = [p.changed() for p in props]

        if not any(changes):
            return

        if self.connector.status in {SmartSliceCloudStatus.Queued, SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            if self._addProperties and not self._cancelChanges:
                self.showConfirmDialog(revalidationRequired)
        else:
            self.connector.status = SmartSliceCloudStatus.Cancelling
            self.connector.updateStatus()
            for p in props:
                p.cache()

    def showConfirmDialog(self, revalidationRequired : bool):
        if self._confirmDialog and self._confirmDialog.visible:
            return

        #  Create a Confirmation Dialog Component
        if self.connector.status in SmartSliceCloudStatus.busy() and self.connector.cloudJob.job_type is pywim.smartslice.job.JobType.validation:
            self._confirmDialog = Message(
                title="Lose Validation Results?",
                text="Modifying this setting will invalidate your results.\nDo you want to continue and lose the current\n validation results?",
                lifetime=0
            )

            self._confirmDialog.actionTriggered.connect(self.onConfirmActionRevalidate)

        elif self.connector.status == SmartSliceCloudStatus.Optimized or self.connector.status in SmartSliceCloudStatus.busy():
            self._confirmDialog = Message(
                title="Smart Slice Warning",
                text="Modifying this setting will invalidate your results.\nDo you want to continue and lose your \noptimization results?",
                lifetime=0
            )

            if revalidationRequired:
                self._confirmDialog.actionTriggered.connect(self.onConfirmActionRevalidate)
            else:
                self._confirmDialog.actionTriggered.connect(self.onConfirmActionReoptimize)
        else:
            # we're not in a state where we need to ask for confirmation
            return

        self._confirmDialog.addAction(
            "cancel",
            i18n_catalog.i18nc("@action", "Cancel"),
            "", "",
            button_style=Message.ActionButtonStyle.SECONDARY
        )

        self._confirmDialog.addAction(
            "continue",
            i18n_catalog.i18nc("@action", "Continue"),
            "", ""
        )

        self._confirmDialog.show()

    def onConfirmActionRevalidate(self, msg, action):
        if action == "cancel":
            self.cancelChanges()
        elif action == "continue":
            self.connector.status = SmartSliceCloudStatus.Cancelling
            self.connector.updateStatus()
            self.connector.cancelCurrentJob()
            self.cacheChanges()
            self._reset()

        msg.hide()

    def onConfirmActionReoptimize(self, msg, action):
        if action == "cancel":
            self.cancelChanges()
        elif action == "continue":
            self.connector.cancelCurrentJob()
            self.connector.prepareOptimization()
            self.cacheChanges()
            self._reset()
        msg.hide()

    def cancelChanges(self):
        Logger.log ("d", "Canceling Change in Smart Slice Environment")

        self._cancelChanges = True
        self.restoreCache()
        self._cancelChanges = False

        SmartSliceSelectTool.getInstance().redraw()

        if self._confirmDialog:
            self._confirmDialog.hide()

    def askToRemoveModMesh(self):
        if self._mod_mesh_removal_msg is not None:
            self.removeModMeshes(self._mod_mesh_removal_msg, 'continue')
        else:
            self._mod_mesh_removal_msg = Message(
                title="Smart Slice Warning",
                text="Modifier meshes will be removed for the optimization.\nDo you want to Continue?",
                lifetime=600,
                dismissable=False
            )
            self._mod_mesh_removal_msg.addAction(
                "cancel",
                i18n_catalog.i18nc("@action", "Cancel"),
                "", "",
                button_style=Message.ActionButtonStyle.SECONDARY
            )
            self._mod_mesh_removal_msg.addAction(
                "continue",
                i18n_catalog.i18nc("@action", "Continue"),
                "", ""
            )
            self._mod_mesh_removal_msg.actionTriggered.connect(self.removeModMeshes)
            self._mod_mesh_removal_msg.show()

    def removeModMeshes(self, msg, action):
        """ Associated Action for askToRemoveModMesh() """
        self._mod_mesh_removal_msg = None
        msg.hide()
        if action == "continue":
            op = GroupedOperation()
            for node in getModifierMeshes():
                node.addDecorator(SmartSliceRemovedDecorator)
                op.addOperation(RemoveSceneNodeOperation(node))
            op.push()
            self.connector.status = SmartSliceCloudStatus.RemoveModMesh
            self.connector.doOptimization()
        else:
            self.connector.prepareOptimization()

    def resetProperties(self):
        self.cacheChanges()
        self._propertiesChanged.clear()
