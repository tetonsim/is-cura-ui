#
#  Contains procedures for handling Cura Properties in accordance with SmartSlice
#

import time, threading

from PyQt5.QtCore import QObject

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Selection import Selection
from UM.Message import Message
from UM.Signal import Signal
from UM.Logger import Logger
from UM.Settings.SettingInstance import InstanceState
from UM.Math.Vector import Vector
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.GroupedOperation import GroupedOperation

from cura.CuraApplication import CuraApplication

from .SmartSliceCloudProxy import SmartSliceCloudStatus
from .SmartSliceProperty import SmartSlicePropertyEnum, SmartSliceContainerProperties
from .select_tool.SmartSliceSelectHandle import SelectionMode
from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements
from .utils import getModifierMeshes

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
    def __init__(self, connector):
        super().__init__()

        #  Callback
        self.connector = connector
        self.proxy = connector._proxy

        #  General Purpose Cache Space
        self._propertiesChanged  = []
        self._changedValues      = []
        self._global_cache = {}
        self._extruder_cache = {}
        #  General Purpose properties which affect Smart Slice
        self._container_properties = SmartSliceContainerProperties()

        controller = Application.getInstance().getController()

        self._global_properties = SmartSliceProperty.GlobalProperty.CreateAll()
        self._extruder_properties = SmartSliceProperty.ExtruderProperty.CreateAll()
        self._selected_material = SmartSliceProperty.SelectedMaterial()
        self._scene = SmartSliceProperty.Scene()
        self._modifier_mesh = SmartSliceProperty.ModifierMesh()

        req_tool = SmartSliceRequirements.getInstance()

        self._tool_properties = [
            SmartSliceProperty.ToolProperty(req_tool, "TargetSafetyFactor"),
            SmartSliceProperty.ToolProperty(req_tool, "MaxDisplacement")
        ]

        self._properties = \
            self._global_properties + \
            self._extruder_properties + \
            self._tool_properties + \
            [
                self._selected_material,
                self._scene,
                self._modifier_mesh
            ]

        req_tool.toolPropertyChanged.connect(self._onRequirementToolPropertyChanged)

        #  Mesh Properties
        self.meshScale = None
        self.meshRotation = None
        #  Scene (for mesh/transform signals)
        self._sceneNode = None
        self._sceneRoot = controller.getScene().getRoot()

        #  Selection Proeprties
        self._selection_mode = 1 # Default to AnchorMode
        self._anchoredID = None
        self._anchoredNode = None
        self._anchoredTris = None
        self._loadedID = None
        self._loadedNode = None
        self._loadedTris = None

        #  Cura Setup
        self._activeMachineManager = CuraApplication.getInstance().getMachineManager()
        self._globalStack = self._activeMachineManager.activeMachine

        self._globalStack.propertyChanged.connect(self._onGlobalPropertyChanged)
        self._activeMachineManager.activeMaterialChanged.connect(self._onMaterialChanged)
        self._sceneRoot.childrenChanged.connect(self._onSceneChanged)

        #  Check that a printer has been set-up by the wizard.
        #  TODO:  Add a signal listener for when Machine is added
        if self._globalStack is not None:
            self._onMachineChanged()

        #  Cancellation Variable
        self._cancelChanges = False

        #  Temporary Cache
        self._cachedModMesh = None
        self._positionModMesh = None
        self._addProperties = True

        self._confirmDialog = None

        #  Attune to Scale/Rotate Operations
        controller.getTool("ScaleTool").operationStopped.connect(self._onMeshScaleChanged)
        controller.getTool("RotateTool").operationStopped.connect(self._onMeshRotationChanged)

    def hasModMesh(self) -> bool:
        return self._modifier_mesh.value() is not None

    def cacheChanges(self):
        #self.cacheSmartSlice()
        for p in self._properties:
            p.cache()

    """
      cacheSmartSlice()
        Caches properties that are only used in SmartSlice Environment
    """
    def cacheSmartSlice(self):
        i = 0
        for prop in self._propertiesChanged:
            if prop is SmartSlicePropertyEnum.MaxDisplacement:
                self.proxy.reqsMaxDeflect = self.proxy._bufferDeflect
                self.proxy.setMaximalDisplacement()
            elif prop is SmartSlicePropertyEnum.FactorOfSafety:
                self.proxy.reqsSafetyFactor = self.proxy._bufferSafety
                self.proxy.setFactorOfSafety()
            elif prop is SmartSlicePropertyEnum.LoadDirection:
                self.proxy.reqsLoadDirection = self._changedValues[i]
                self.proxy.setLoadDirection()
            elif prop is SmartSlicePropertyEnum.LoadMagnitude:
                self.proxy.reqsLoadMagnitude = self.proxy._bufferMagnitude
                self.proxy.setLoadMagnitude()

          #  Face Selection
            elif prop is SmartSlicePropertyEnum.SelectedFace:
                #  ANCHOR MODE
                if self._selection_mode == SelectionMode.AnchorMode:
                    self._anchoredID = self._changedValues[i]
                    self._anchoredNode = self._changedValues[i+1]
                    self._anchoredTris = self._changedValues[i+2]
                    self.applyAnchor()
                #  LOAD MODE
                elif self._selection_mode == SelectionMode.LoadMode:
                    self._loadedID = self._changedValues[i]
                    self._loadedNode = self._changedValues[i+1]
                    self._loadedTris = self._changedValues[i+2]
                    self.applyLoad()

                self._changedValues.pop(i+2)    # Adjust for Tris
                self._changedValues.pop(i+1)    # Adjust for Node

                self.selectedFacesChanged.emit()

            i += 0
        self.prepareCache()

    """
      restoreCache()
        Restores all cached values for properties upon user cancellation
    """
    def restoreCache(self):
        for p in self._properties:
            p.restore()

        self._addProperties = False
        self._activeMachineManager.forceUpdateAllSettings()
        self._addProperties = True

        return

        #  Restore/Clear SmartSlice Property Changes
        _props = 0
        for prop in self._propertiesChanged:
            Logger.log ("d", "Property Found: " + str(prop))
            _props += 1
            if prop is SmartSlicePropertyEnum.MaxDisplacement:
                self.proxy.setMaximalDisplacement()
            elif prop is SmartSlicePropertyEnum.FactorOfSafety:
                self.proxy.setFactorOfSafety()
            elif prop is SmartSlicePropertyEnum.LoadDirection:
                self.proxy.setLoadDirection()
            elif prop is SmartSlicePropertyEnum.LoadMagnitude:
                self.proxy.setLoadMagnitude()

            #  Face Selection
            elif prop is SmartSlicePropertyEnum.SelectedFace:
                self.selectedFacesChanged.emit()

            #  Material
            elif prop is SmartSlicePropertyEnum.Material:
                self._activeExtruder.material = self._material

            #  Mesh Properties
            elif prop is SmartSlicePropertyEnum.MeshScale:
                self.setMeshScale()
            elif prop is SmartSlicePropertyEnum.MeshRotation:
                self.setMeshRotation()
            elif prop is SmartSlicePropertyEnum.ModifierMesh:
                self._cachedModMesh.setPosition(self._positionModMesh, SceneNode.TransformSpace.World)
                self._sceneRoot.addChild(self._cachedModMesh)
                self._changedValues.pop(_props)

                Application.getInstance().getController().getScene().sceneChanged.emit(self._cachedModMesh)


    def getGlobalProperty(self, key):
        for p in self._global_properties:
            if p.name == key:
                return p.value()

    def getExtruderProperty(self, key):
        for p in self._extruder_properties:
            if p.name == key:
                return p.value()

    def askToRemoveModMesh(self):
        msg = Message(
            title="",
            text="Modifier meshes will be removed for the validation.\nDo you want to Continue?",
            lifetime=0
        )
        msg.addAction(
            "cancel",
            i18n_catalog.i18nc("@action", "Cancel"),
            "", "",
            button_style=Message.ActionButtonStyle.SECONDARY
        )
        msg.addAction(
            "continue",
            i18n_catalog.i18nc("@action", "Continue"),
            "", ""
        )
        msg.actionTriggered.connect(self.removeModMeshes)
        msg.show()

    def removeModMeshes(self, msg, action):
        """ Associated Action for askToRemoveModMesh() """
        msg.hide()
        if action == "continue":
            op = GroupedOperation()
            for node in getModifierMeshes():
                op.addOperation(RemoveSceneNodeOperation(node))
            op.push()
            if self.connector.status is SmartSliceCloudStatus.ReadyToVerify:
                self.connector.doVerfication()
            else:
                self.connector.prepareValidation()
        else:
            pass
            # TODO - I don't think this function exists. Anything to do here?
            #self.connector.onConfirmationCancelClicked()

    def _onMeshScaleChanged(self, unused):
        self.confirmPendingChanges(self._scene)

    def _onMeshRotationChanged(self, unused):
        self.confirmPendingChanges(self._scene)

    def _onRequirementToolPropertyChanged(self, property_name):
        # We handle changes in the requirements tool differently, depending on the current
        # status. We only need to ask for confirmation if the model has been optimized
        if self.connector.status in { SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.Underdimensioned, SmartSliceCloudStatus.Overdimensioned }:
            self.connector.prepareOptimization()
        else:
            self.confirmPendingChanges(
                list(filter(lambda p: p.name == property_name, self._tool_properties)),
                revalidationRequired=False
            )

        self.connector._proxy.targetSafetyFactorChanged.emit()
        self.connector._proxy.targetMaximalDisplacementChanged.emit()

    #  Signal for Interfacing with Face Selection
    selectedFacesChanged = Signal()

    """
      onSelectedFaceChanged(node, id)
        node:   The scene node for which the face belongs to
        id:     Currently selected triangle's face ID
    """
    def onSelectedFaceChanged(self, scene_node, face_id):
        Logger.log("w", "TODO")#; return

        select_tool = Application.getInstance().getController().getTool("SmartSlicePlugin_SelectTool")

        selection_mode = select_tool.getSelectionMode()

        #  Throw out "fake" selection changes
        if Selection.getSelectedFace() is None:
            return
        if selection_mode is SelectionMode.AnchorMode:
            if Selection.getSelectedFace()[1] == self._anchoredID:
                return
        elif selection_mode is SelectionMode.LoadMode:
            if Selection.getSelectedFace()[1] == self._loadedID:
                return

        selected_triangles = list(select_tool._interactive_mesh.select_planar_face(face_id))

        #  If busy, add it to 'pending changes' and ask user to confirm
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            #self._propertiesChanged.append(SmartSlicePropertyEnum.SelectedFace)
            #self._changedValues.append(face_id)
            #self._changedValues.append(scene_node)
            #self._changedValues.append(selected_triangles)
            #self.confirmPendingChanges()
            pass
        else:
            if selection_mode is SelectionMode.AnchorMode:
                self._anchoredID = face_id
                self._anchoredNode = scene_node
                self._anchoredTris = selected_triangles
                self.proxy._anchorsApplied = 1   #  TODO:  Change this when > 1 anchors in Use Case
                self.applyAnchor()
            elif selection_mode is SelectionMode.LoadMode:
                self._loadedID = face_id
                self._loadedNode = scene_node
                self._loadedTris = selected_triangles
                self.proxy._loadsApplied = 1     #  TODO:  Change this when > 1 loads in Use Case
                self.applyLoad()
            self.connector.prepareValidation()

    """
      applyAnchor()
        * Sets the anchor data for the pending job
        * Sets the face id/node for drawing face selection
    """
    def applyAnchor(self):
        if self._anchoredTris is None:
            return

        #  Set Anchor in Job
        self.connector.resetAnchor0FacesPoc()
        self.connector.appendAnchor0FacesPoc(self._anchoredTris)

        self._drawAnchor()
        Logger.log ("d", "PropertyHandler Anchored Face ID:  " + str(self._anchoredID))

    """
      applyLoad()
        * Sets the load data for hte pending job
          * Sets Load Vector
          * Sets Load Force
        * Sets the face id/node for drawing face selection
    """
    def applyLoad(self):
        if self._loadedTris is None:
            return

        load_vector = self._loadedTris[0].normal

        #  Set Load Normal Vector in Job
        self.connector.resetForce0VectorPoc()
        self.connector.updateForce0Vector(
            Vector(load_vector.r, load_vector.s, load_vector.t)
        )

        #  Set Load Force in Job
        self.connector.resetForce0FacesPoc()
        self.connector.appendForce0FacesPoc(self._loadedTris)

        self._drawLoad()
        Logger.log ("d", "PropertyHandler Loaded Face ID:  " + str(self._loadedID))

    def _drawLoad(self):
        select_tool = Application.getInstance().getController().getTool("SmartSlicePlugin_SelectTool")
        select_tool._handle.setFace(self._loadedTris)
        select_tool._handle.drawSelection()

    def _drawAnchor(self):
        select_tool = Application.getInstance().getController().getTool("SmartSlicePlugin_SelectTool")
        select_tool._handle.setFace(self._anchoredTris)
        select_tool._handle.drawSelection()

    def continueChanges(self):
        self.cacheChanges()

    def cancelChanges(self):
        Logger.log ("d", "Cancelling Change in Smart Slice Environment")
        self._cancelChanges = True
        self.restoreCache()
        self._cancelChanges = False
        Logger.log ("d", "Cancelled Change in Smart Slice Environment")

        if self._confirmDialog:
            self._confirmDialog.hide()

    def _onGlobalPropertyChanged(self, key: str, property_name: str):
        self.confirmPendingChanges(
            list(filter(lambda p: p.name == key, self._global_properties))
        )

    def _onExtruderPropertyChanged(self, key: str, property_name: str):
        self.confirmPendingChanges(
            list(filter(lambda p: p.name == key, self._extruder_properties))
        )


    #  Configure Extruder/Machine Settings for Smart Slice
    def _onMachineChanged(self):
        self._activeExtruder = self._globalStack.extruderList[0]

        self._material = self._activeMachineManager._global_container_stack.extruderList[0].material

        self._activeExtruder.propertyChanged.connect(self._onExtruderPropertyChanged)

    def _onMaterialChanged(self):
        self.confirmPendingChanges(self._selected_material)

    def _onSceneChanged(self, changed_node):
        self.confirmPendingChanges( [self._scene, self._modifier_mesh] )

    def confirmPendingChanges(self, props, revalidationRequired=True):
        if not props:
            return

        if isinstance(props, SmartSliceProperty.TrackedProperty):
            props = [props]

        if all(not p.changed() for p in props):
            return

        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            if self._addProperties and not self._cancelChanges:
                self.showConfirmDialog(revalidationRequired)
        else:
            self.connector.prepareValidation()
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
                title="Lose Optimization Results?",
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
            self.connector.cancelCurrentJob()
            self.connector.prepareValidation() # TODO Added this - is it okay here?
            self.continueChanges()

        msg.hide()

    def onConfirmActionReoptimize(self, msg, action):
        if action == "cancel":
            self.cancelChanges()
        elif action == "continue":
            self.connector.cancelCurrentJob()
            self.connector.prepareOptimization()
            self.continueChanges()
        msg.hide()
