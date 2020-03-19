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
from .SmartSliceProperty import SmartSliceProperty, SmartSliceContainerProperties
from .select_tool.SmartSliceSelectHandle import SelectionMode

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
        self._initialized = False

        #  General Purpose Cache Space
        self._propertiesChanged  = []
        self._changedValues      = []
        self._global_cache = {}
        self._extruder_cache = {}
        #  General Purpose properties which affect Smart Slice
        self._container_properties = SmartSliceContainerProperties()

        #  Mesh Properties
        self.meshScale = None
        self.meshRotation = None
        #  Scene (for mesh/transform signals)
        self._sceneNode = None
        self._sceneRoot = Application.getInstance().getController().getScene().getRoot()

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

        #  Check that a printer has been set-up by the wizard.
        #  TODO:  Add a signal listener for when Machine is added
        if self._globalStack is not None:
            self._onMachineChanged()

        #  Cancellation Variable
        self._cancelChanges = False

        #  Temporary Cache
        self._cachedModMesh = None
        self.hasModMesh = False
        self._positionModMesh = None
        self._addProperties = True

        #  Attune to Scale/Rotate Operations
        Application.getInstance().getController().getTool("ScaleTool").operationStopped.connect(self.onMeshScaleChanged)
        Application.getInstance().getController().getTool("RotateTool").operationStopped.connect(self.onMeshRotationChanged)


    #
    #   CACHE HANDLING
    #

    """
      prepareCache()
        Clears any pending changes to cache and silences confirmation prompt
    """
    def prepareCache(self):
        self._propertiesChanged = []
        self._changedValues = []

    #  Cache Changes
    """
      cacheChanges()
        Stores all current values in Cura environment to SmartSlice cache
    """
    def cacheChanges(self):
        self.cacheGlobal()
        self.cacheExtruder()
        self.cacheSmartSlice()

    """
      cacheGlobal()
        Caches properties that are used throughout Cura's Global Environment
    """
    def cacheGlobal(self):
        self._global_cache = {}

        for key in self._container_properties.global_keys:
            if key not in self._global_cache.keys():
                self._global_cache[key] = self._globalStack.getProperty(key, "value")
            if self._global_cache[key] != self._globalStack.getProperty(key, "value"):
                self._global_cache[key] = self._globalStack.getProperty(key, "value")

        #  Clear Properties Changed of Global Settings
        self._propertiesChanged = [
            p for p in self._propertiesChanged if p != SmartSliceProperty.GlobalProperty
        ]

    """
      cacheExtruder()
        Caches properties that are used for the active extruder
    """
    def cacheExtruder(self):
        self._extruder_cache = {}

        for key in self._container_properties.extruder_keys:
            if key not in self._extruder_cache.keys():
                self._extruder_cache[key] = self._activeExtruder.getProperty(key, "value")
            if self._extruder_cache[key] != self._activeExtruder.getProperty(key, "value"):
                self._extruder_cache[key] = self._activeExtruder.getProperty(key, "value")

        #  Clear Properties Changed of Extruder Settings
        self._propertiesChanged = [
            p for p in self._propertiesChanged if p != SmartSliceProperty.ExtruderProperty
        ]

    """
      cacheSmartSlice()
        Caches properties that are only used in SmartSlice Environment
    """
    def cacheSmartSlice(self):
        i = 0
        for prop in self._propertiesChanged:
            if prop is SmartSliceProperty.MaxDisplacement:
                self.proxy.reqsMaxDeflect = self.proxy._bufferDeflect
                self.proxy.setMaximalDisplacement()
            elif prop is SmartSliceProperty.FactorOfSafety:
                self.proxy.reqsSafetyFactor = self.proxy._bufferSafety
                self.proxy.setFactorOfSafety()
            elif prop is SmartSliceProperty.LoadDirection:
                self.proxy.reqsLoadDirection = self._changedValues[i]
                self.proxy.setLoadDirection()
            elif prop is SmartSliceProperty.LoadMagnitude:
                self.proxy.reqsLoadMagnitude = self.proxy._bufferMagnitude
                self.proxy.setLoadMagnitude()

          #  Face Selection
            elif prop is SmartSliceProperty.SelectedFace:
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

          #  Material
            elif prop is SmartSliceProperty.Material:
                self._material = self._changedValues[i]

          #  Mesh Properties
            elif prop is SmartSliceProperty.MeshScale:
                self.meshScale = self._changedValues[i]
            elif prop is SmartSliceProperty.MeshRotation:
                self.meshRotation = self._changedValues[i]
            elif prop is SmartSliceProperty.ModifierMesh:
                self._changedValues.pop(i+1)

            i += 0
        self.prepareCache()

        #  Refresh Buffered Property Values
        self.proxy.setLoadMagnitude()
        self.proxy.setLoadDirection()
        self.proxy.setFactorOfSafety()
        self.proxy.setMaximalDisplacement()

    """
      restoreCache()
        Restores all cached values for properties upon user cancellation
    """
    def restoreCache(self):
        # Restore/Clear Global Property Changes
        for property in self._container_properties.global_keys:
            if self._global_cache[property] != self._globalStack.getProperty(property, "value"):
                self._globalStack.setProperty(property, "value", self._global_cache[property], set_from_cache=True)
        for property in self._container_properties.global_keys:
            self._globalStack.setProperty(property, "state", InstanceState.Default, set_from_cache=True)

        self._propertiesChanged = [
            p for p in self._propertiesChanged if p != SmartSliceProperty.GlobalProperty
        ]

        #  Restore/Clear Extruder Property Changes
        for property in self._container_properties.extruder_keys:
            if self._extruder_cache[property] != self._activeExtruder.getProperty(property, "value"):
                self._activeExtruder.setProperty(property, "value", self._extruder_cache[property], set_from_cache=True)
        for property in self._container_properties.extruder_keys:
            self._activeExtruder.setProperty(property, "state", InstanceState.Default, set_from_cache=True)

        self._propertiesChanged = [
            p for p in self._propertiesChanged if p != SmartSliceProperty.ExtruderProperty
        ]

        self._addProperties = False
        self._activeMachineManager.forceUpdateAllSettings()
        self._addProperties = True

        #  Restore/Clear SmartSlice Property Changes
        _props = 0
        for prop in self._propertiesChanged:
            Logger.log ("d", "Property Found: " + str(prop))
            _props += 1
            if prop is SmartSliceProperty.MaxDisplacement:
                self.proxy.setMaximalDisplacement()
            elif prop is SmartSliceProperty.FactorOfSafety:
                self.proxy.setFactorOfSafety()
            elif prop is SmartSliceProperty.LoadDirection:
                self.proxy.setLoadDirection()
            elif prop is SmartSliceProperty.LoadMagnitude:
                self.proxy.setLoadMagnitude()

            #  Face Selection
            elif prop is SmartSliceProperty.SelectedFace:
                self.selectedFacesChanged.emit()

            #  Material
            elif prop is SmartSliceProperty.Material:
                self.setMaterial()

            #  Mesh Properties
            elif prop is SmartSliceProperty.MeshScale:
                self.setMeshScale()
            elif prop is SmartSliceProperty.MeshRotation:
                self.setMeshRotation()
            elif prop is SmartSliceProperty.ModifierMesh:
                self._cachedModMesh.setPosition(self._positionModMesh, SceneNode.TransformSpace.World)
                self._sceneRoot.addChild(self._cachedModMesh)
                self._changedValues.pop(_props)

                Application.getInstance().getController().getScene().sceneChanged.emit(self._cachedModMesh)


    #
    #   CURA PROPERTY ACCESSORS
    #

    """
      getGlobalProperty(key)
        key: String 'key' value for referencing global property value
    """
    def getGlobalProperty(self, key):
        return self._global_cache[key]

    """
      getExtruderProperty(key)
        key: String 'key' value for referencing active extruder property value
    """
    def getExtruderProperty(self, key):
        return self._extruder_cache[key]


    """
      confirmOptimizeModMesh()
        This raises a prompt which tells the user that their modifier mesh will be removed
         for Smart Slice part optimization.

        * On Cancel: Cancels the user's most recent action and leaves Modifier Mesh in scene
        * On Confirm: Removes the modifier mesh and proceeds with Optimization run (NOTE: CURRENTLY VALIDATION)

        NOTE:  This currently raises on Validation, but when modifier meshes are validated,
                the commented 'text=' should be used instead of the current 'text='
    """
    def confirmOptimizeModMesh(self):
        msg = Message(title="",
                      text="Modifier meshes will be removed for the validation.\nDo you want to Continue?",
                      #text="Modifier meshes will be removed for the optimization.\nDo you want to Continue?",
                      lifetime=0
                      )
        msg.addAction("cancelModMesh",
                      i18n_catalog.i18nc("@action",
                                         "Cancel"
                                         ),
                      "",   # Icon
                      "",   # Description
                      button_style=Message.ActionButtonStyle.SECONDARY
                      )
        msg.addAction("continueModMesh",
                      i18n_catalog.i18nc("@action",
                                         "Continue"
                                         ),
                      "",   # Icon
                      ""    # Description
                      )
        msg.actionTriggered.connect(self.removeModMeshes)
        msg.show()

    """
      confirmRemoveModMesh()
        This raises a prompt which tells the user that the current modifier mesh will
         be removed if they would like to proceed with their most recent action.

        * On Cancel: Cancels their most recent action and reverts any affected settings
        * On Confirm: Removes the Modifier Mesh and proceeds with the desired action
    """
    def confirmRemoveModMesh(self):
        self.connector.hideMessage()
        index = len(self.connector._confirmDialog)
        self.connector._confirmDialog.append(Message(title="",
                                                     text="Continue and remove Smart Slice Modifier Mesh?",
                                                     lifetime=0
                                                     )
                                            )
        dialog = self.connector._confirmDialog[index]
        dialog.addAction("cancelModMesh",       #  action_id
                         i18n_catalog.i18nc("@action",
                                             "Cancel"
                                            ),
                         "",
                         "",
                         button_style=Message.ActionButtonStyle.SECONDARY
                         )
        dialog.addAction("continueModMesh",       #  action_id
                         i18n_catalog.i18nc("@action",
                                            "Continue"
                                            ),
                         "",
                         ""
                         )
        dialog.actionTriggered.connect(self.removeModMeshes)
        if index == 0:
            dialog.show()

    """
      removeModMeshes(msg, action)
        Associated Action for 'confirmOptimizeModMesh()' and 'confirmRemoveModMesh()'
    """
    def removeModMeshes(self, msg, action):
        msg.hide()
        if action == "continueModMesh":
            self._cachedModMesh = None
            self.hasModMesh = False
            for node in self._sceneRoot.getAllChildren():
                stack = node.callDecoration("getStack")
                if stack is None:
                    continue
                if stack.getProperty("infill_mesh", "value"):
                    op = GroupedOperation()
                    op.addOperation(RemoveSceneNodeOperation(node))
                    op.push()
            #if self.connector.status is SmartSliceCloudStatus.Optimizable:
            #    self.connector.doOptimization()
            if self.connector.status is SmartSliceCloudStatus.ReadyToVerify:
                self.connector.doVerfication()
            else:
                self.connector.prepareValidation()
        else:
            self.connector.onConfirmationCancelClicked()


    #
    #  LOCAL TRANSFORMATION
    #

    def setMeshScale(self):
        self._sceneNode.setScale(self.meshScale)
        self._sceneNode.transformationChanged.emit(self._sceneNode)

    def onMeshScaleChanged(self, unused):
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            self._propertiesChanged.append(SmartSliceProperty.MeshScale)
            self._changedValues.append(self._sceneNode.getScale())
            self.connector.confirmPendingChanges()
        else:
            self.meshScale = self._sceneNode.getScale()
            self.connector.prepareValidation()

    def setMeshRotation(self):
        self._sceneNode.setOrientation(self.meshRotation)
        self._sceneNode.transformationChanged.emit(self._sceneNode)

    def onMeshRotationChanged(self, unused):
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            self._propertiesChanged.append(SmartSliceProperty.MeshRotation)
            self._changedValues.append(self._sceneNode.getOrientation())
            self.connector.confirmPendingChanges()
        else:
            self.meshRotation = self._sceneNode.getOrientation()
            self.applyLoad()
            self.applyAnchor()
            self.connector.prepareValidation()


    #
    #   FACE SELECTION
    #

    #  Signal for Interfacing with Face Selection
    selectedFacesChanged = Signal()

    """
      onSelectedFaceChanged(node, id)
        node:   The scene node for which the face belongs to
        id:     Currently selected triangle's face ID
    """
    def onSelectedFaceChanged(self, scene_node, face_id):
        #  Throw out "fake" selection changes
        if Selection.getSelectedFace() is None:
            return
        if self._selection_mode is SelectionMode.AnchorMode:
            if Selection.getSelectedFace()[1] == self._anchoredID:
                return
        elif self._selection_mode is SelectionMode.LoadMode:
            if Selection.getSelectedFace()[1] == self._loadedID:
                return

        select_tool = Application.getInstance().getController().getTool("SmartSlicePlugin_SelectTool")
        selected_triangles = list(select_tool._interactive_mesh.select_planar_face(face_id))

        #  If busy, add it to 'pending changes' and ask user to confirm
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            self._propertiesChanged.append(SmartSliceProperty.SelectedFace)
            self._changedValues.append(face_id)
            self._changedValues.append(scene_node)
            self._changedValues.append(selected_triangles)
            self.connector.confirmPendingChanges()
        else:
            if self._selection_mode is SelectionMode.AnchorMode:
                self._anchoredID = face_id
                self._anchoredNode = scene_node
                self._anchoredTris = selected_triangles
                self.proxy._anchorsApplied = 1   #  TODO:  Change this when > 1 anchors in Use Case
                self.applyAnchor()
            elif self._selection_mode is SelectionMode.LoadMode:
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


    #
    #   CONFIRM/CANCEL PROPERTY CHANGE HANDLERS
    #

    """
      _onContinueChanges()
        Handles all actions that are associated with continuing with a property change
         during a timing-sensitive action, e.g. Validation/Optimization
    """
    def _onContinueChanges(self):
        self.cacheChanges()
        self.prepareCache()

    """
      _onCancelChanges()
    """
    def _onCancelChanges(self):
        Logger.log ("d", "Cancelling Change in Smart Slice Environment")
        self._cancelChanges = True
        #t = threading.Thread(target=self._resetCancelCheck)
        #t.start()
        self.restoreCache()
        self.prepareCache()
        self._cancelChanges = False
        Logger.log ("d", "Cancelled Change in Smart Slice Environment")

    """
      _resetCancelCheck()
        Silences second 'Confirm Changes' prompt after a user cancels
    """
    def _resetCancelCheck(self):
        #  NOTE: Increase delay if a setting change
        #         erroneously raises a second confirmation prompt
        time.sleep(0.35)
        self._cancelChanges = False
        self._addProperties = True
        self.connector.hideMessage()

    #
    #   CURA PROPERTY SIGNAL LISTENERS
    #

    # On GLOBAL Property Changed
    def _onGlobalPropertyChanged(self, key: str, property_name: str):
        if key not in self._container_properties.global_keys:
            return
        if self._globalStack.getProperty(key, property_name) == self._global_cache[key]:
            return

        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            if self._addProperties:
                self._propertiesChanged.append(SmartSliceProperty.GlobalProperty)
                self._changedValues.append(self._activeExtruder.getProperty(key, "value"))
                self.connector.confirmPendingChanges()
        else:
            self.connector.prepareValidation()
            self._global_cache[key] = self._globalStack.getProperty(key, "value")

    # On EXTRUDER Property Changed
    def _onExtruderPropertyChanged(self, key: str, property_name: str):
        if key not in self._container_properties.extruder_keys:
            return
        elif self._activeExtruder.getProperty(key, property_name) == self._extruder_cache[key]:
            return

        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            if self._addProperties:
                #  Confirm Settings Changes
                self._propertiesChanged.append(SmartSliceProperty.ExtruderProperty)
                self._changedValues.append(self._activeExtruder.getProperty(key, "value"))
                self.connector.confirmPendingChanges()
        else:
            self.connector.prepareValidation()
            self._extruder_cache[key] = self._activeExtruder.getProperty(key, "value")


    #  Configure Extruder/Machine Settings for Smart Slice
    def _onMachineChanged(self):
        self._activeExtruder = self._globalStack.extruderList[0]

        self._material = self._activeMachineManager._global_container_stack.extruderList[0].material #  Cura Material Node

        #  Connect Signals
        self._globalStack.propertyChanged.connect(self._onGlobalPropertyChanged)            #  Global
        self._activeExtruder.propertyChanged.connect(self._onExtruderPropertyChanged)       #  Extruder
        self._activeMachineManager.activeMaterialChanged.connect(self._onMaterialChanged)   #  Material
        self._sceneRoot.childrenChanged.connect(self._onSceneChanged)                       #  Mesh Data

    #   On MATERIAL Property Changed
    activeMaterialChanged = Signal()

    def setMaterial(self):
       self._activeExtruder.material = self._material

    def _onMaterialChanged(self):
        if self.connector.status in {SmartSliceCloudStatus.BusyValidating, SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.Optimized}:
            if self._material is not self._activeExtruder.material:
                self._propertiesChanged.append(SmartSliceProperty.Material)
                self._changedValues.append(self._activeExtruder.material)
                self.connector.confirmPendingChanges()
        else:
            self._material = self._activeExtruder.material
            self.connector.prepareValidation()

    """
      _onSceneChanged()
        When the root scene is changed, this signal is used to ensure that all
         settings regarding the model are cached and correct.

        Affected Settings:
          * Scale
          * Rotation
          * Modifier Meshes
    """
    def _onSceneChanged(self, changed_node):
        i = 0
        _root = self._sceneRoot
        self.hasModMesh = False

        #  Loaded Model immediately follows the node named "3d" in Root Scene
        for node in _root.getAllChildren():
            if node.getName() == "3d":
                if (self._sceneNode is None) or (self._sceneNode.getName() != _root.getAllChildren()[i+1].getName()):
                    self._sceneNode = _root.getAllChildren()[i+1]
                    Logger.log ("d", "Model File Found:  " + self._sceneNode.getName())

                    #  Set Initial Scale/Rotation
                    self.meshScale    = self._sceneNode.getScale()
                    self.meshRotation = self._sceneNode.getOrientation()
                    i += 1
            if node.getName() == "SmartSliceMeshModifier":
                self._cachedModMesh = node
                self._positionModMesh = self._cachedModMesh.getWorldPosition()
                self.hasModMesh = True
            i += 1

        #  Check if Modifier Mesh has been Removed
        if self._cachedModMesh:
            if not self.hasModMesh:
                self._propertiesChanged.append(SmartSliceProperty.ModifierMesh)
                self._changedValues.append(self._cachedModMesh)
                self._changedValues.append(self._positionModMesh)
                self.confirmRemoveModMesh()