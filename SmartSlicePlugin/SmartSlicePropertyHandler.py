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
from UM.Workspace.WorkspaceMetadataStorage import WorkspaceMetadataStorage

from cura.CuraApplication import CuraApplication

from .SmartSliceCloudStatus import SmartSliceCloudStatus
from .select_tool.SmartSliceSelectTool import SmartSliceSelectTool
from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements
from .utils import getModifierMeshes, getPrintableNodes
from .stage.SmartSliceScene import Root

from . import SmartSliceProperty

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

    EXTRUDER_KEYS = [
        "wall_extruder_nr",         # Both wall extruder drop down
        "wall_0_extruder_nr",       # Outer wall extruder
        "wall_x_extruder_nr",       # Inner wall extruder
        "infill_extruder_nr"        # Infill extruder
    ]

    def __init__(self, connector):
        super().__init__()

        self.connector = connector
        self.proxy = connector._proxy

        controller = Application.getInstance().getController()

        self._global_properties = SmartSliceProperty.GlobalProperty.CreateAll()
        self._extruder_properties = SmartSliceProperty.ExtruderProperty.CreateAll()
        self._selected_material = SmartSliceProperty.SelectedMaterial()
        self._scene = SmartSliceProperty.Scene()

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
                self._selected_material,
                self._scene,
            ]

        self._propertiesChanged = []

        self._activeMachineManager = CuraApplication.getInstance().getMachineManager()
        self._activeMachineManager.printerConnectedStatusChanged.connect(self.printerCheck)
        self.printerCheck()

        Root.faceAdded.connect(self._faceAdded)
        Root.faceRemoved.connect(self._faceRemoved)
        Root.loadPropertyChanged.connect(self._faceChanged)

        sel_tool.selectedFaceChanged.connect(self._faceChanged)
        sel_tool.toolPropertyChanged.connect(self._onSelectToolPropertyChanged)
        req_tool.toolPropertyChanged.connect(self._onRequirementToolPropertyChanged)
        controller.getScene().getRoot().childrenChanged.connect(self.loadModifierMesh)
        controller.getScene().getRoot().childrenChanged.connect(self._reset)

        self._cancelChanges = False
        self._addProperties = True
        self._confirmDialog = None

        #  Attune to scene changes and mesh changes
        controller.getScene().getRoot().childrenChanged.connect(self._onSceneChanged)
        controller.getTool("ScaleTool").operationStopped.connect(self._onMeshTransformationChanged)
        controller.getTool("RotateTool").operationStopped.connect(self._onMeshTransformationChanged)

        # SmartSliceStage.SmartSliceStage.getInstance().smartSliceNodeChanged.connect(self._onSmartSliceNodeChanged)

    def _faceAdded(self, face):
        prop = SmartSliceProperty.SmartSliceFace(face)
        prop.cache()
        self._properties.append(prop)

    def _faceChanged(self):
        face_properties = [prop for prop in self._properties if isinstance(prop, SmartSliceProperty.SmartSliceFace)]
        self.confirmPendingChanges(face_properties)

    def _faceRemoved(self, face):
        for prop in self._properties:
            if isinstance(prop, SmartSliceProperty.SmartSliceFace) and face == prop.face:
                self._properties.remove(prop)
                break
        self._faceChanged()

    def _reset(self, *args):
        if len(getPrintableNodes()) == 0:
            self.connector.clearJobs()
            self.resetProperties()

    #  Check that a printer has been set-up by the wizard.
    def printerCheck(self):
        if self._activeMachineManager.activeMachine is not None:
            self._onMachineChanged()
            self._activeMachineManager.activeMachine.propertyChanged.connect(self._onGlobalPropertyChanged)
            self._activeMachineManager.activeMaterialChanged.connect(self._onMaterialChanged)

    def buildModifierMeshTrackedProperty(self, node):
        modMesh = SmartSliceProperty.ModifierMesh(node, node.getName())
        self._properties.append(modMesh)
        Logger.log("d", "Tracking properties for {}".format(node.getName()))
        modMesh.cache()
        stack = node.callDecoration('getStack')
        stack.propertyChanged.connect(self._onModMeshChanged)
        node.parentChanged.connect(modMesh.parentChanged)
        node.parentChanged.connect(self.modMeshRemoved)

    def loadModifierMesh(self, root):
        names = [p.mesh_name for p in self._properties if isinstance(p, SmartSliceProperty.ModifierMesh)]
        for node in getModifierMeshes():
            if node.getName() not in names:
                self.buildModifierMeshTrackedProperty(node)

    def modMeshRemoved(self, parent_node):
        for property in self._properties:
            if isinstance(property, SmartSliceProperty.ModifierMesh) and property.parent_changed:
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
            p.restore()

        self._addProperties = False
        self._activeMachineManager.forceUpdateAllSettings()
        self._addProperties = True

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

    def _onMachineChanged(self):
        self._activeExtruder = self._activeMachineManager.activeMachine.extruderList[0]
        self._activeExtruder.propertyChanged.connect(self._onExtruderPropertyChanged)
        self._material = self._activeExtruder.material

    def _onMaterialChanged(self):
        self.confirmPendingChanges(self._selected_material)

    def _onSceneChanged(self, changed_node):
        self.confirmPendingChanges(self._scene)

    def _onModMeshChanged(self, scene_node, infill_node):
        self.confirmPendingChanges(
            list(filter(lambda p: isinstance(p, SmartSliceProperty.ModifierMesh), self._properties))
        )

    def _onMeshTransformationChanged(self, unused):
        self.confirmPendingChanges(self._scene)

    def _onSelectToolPropertyChanged(self, property_name):
        self.confirmPendingChanges(
            list(filter(lambda p: p.name == property_name, self._sel_tool_properties))
        )

    def _onRequirementToolPropertyChanged(self, property_name):
        # We handle changes in the requirements tool differently, depending on the current
        # status. We only need to ask for confirmation if the model has been optimized
        if self.connector.status in { SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.Underdimensioned, SmartSliceCloudStatus.Overdimensioned }:
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

        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
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
        if self.connector.status is SmartSliceCloudStatus.BusyValidating:
            self._confirmDialog = Message(
                title="Lose Validation Results?",
                text="Modifying this setting will invalidate your results.\nDo you want to continue and lose the current\n validation results?",
                lifetime=0
            )

            self._confirmDialog.actionTriggered.connect(self.onConfirmActionRevalidate)

        elif self.connector.status in { SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized }:
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

        msg.hide()

    def onConfirmActionReoptimize(self, msg, action):
        if action == "cancel":
            self.cancelChanges()
        elif action == "continue":
            self.connector.cancelCurrentJob()
            self.connector.prepareOptimization()
            self.cacheChanges()
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
                op.addOperation(RemoveSceneNodeOperation(node))
            op.push()
            self.connector.status = SmartSliceCloudStatus.RemoveModMesh
            self.connector.doOptimization()
        else:
            self.connector.prepareOptimization()

    def resetProperties(self):
        self.cacheChanges()
        self._propertiesChanged.clear()
