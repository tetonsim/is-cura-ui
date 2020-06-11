from typing import List, Optional

import copy
from enum import Enum

from UM.Settings.SettingInstance import InstanceState

from cura.CuraApplication import CuraApplication
from cura.Scene.CuraSceneNode import CuraSceneNode

from . utils import getPrintableNodes, getModifierMeshes

class SmartSlicePropertyEnum(Enum):
    # Mesh Properties
    MeshScale       =  1
    MeshRotation    =  2
    ModifierMesh    =  3
    # Requirements
    FactorOfSafety  =  11
    MaxDisplacement =  12
    # Loads/Anchors
    SelectedFace    =  20
    LoadMagnitude   =  21
    LoadDirection   =  22

    # Material
    Material        =  170

    # Global Props
    GlobalProperty   = 1000
    ExtruderProperty = 1001

class SmartSliceLoadDirection(Enum):
    Pull = 1
    Push = 2

class SmartSlicePropertyColor():
    SubheaderColor = "#A9A9A9"
    WarningColor = "#F3BA1A"
    ErrorColor = "#F15F63"
    SuccessColor = "#5DBA47"

class TrackedProperty:
    def value(self):
        raise NotImplementedError()

    def cache(self):
        raise NotImplementedError()

    def restore(self):
        raise NotImplementedError()

    def changed(self) -> bool:
        raise NotImplementedError()

    def _getMachineAndExtruder(self):
        machine = CuraApplication.getInstance().getMachineManager().activeMachine
        extruder = None
        if machine and len(machine.extruderList) > 0:
            extruder = machine.extruderList[0]
        return machine, extruder

class ContainerProperty(TrackedProperty):
    NAMES = []
    def __init__(self, name):
        self.name = name
        self._cached_value = None

    @classmethod
    def CreateAll(cls) -> List['ContainerProperty']:
        return list(
            map( lambda n: cls(n), cls.NAMES )
        )

    def cache(self):
        self._cached_value = self.value()

    def changed(self) -> bool:
        return self._cached_value != self.value()

class GlobalProperty(ContainerProperty):
    NAMES = [
      "layer_height",                       #   Layer Height
      "layer_height_0",                     #   Initial Layer Height
      "quality",
      "magic_spiralize",
      "wireframe_enabled",
      "adaptive_layer_height_enabled"
    ]

    def value(self):
        machine, extruder = self._getMachineAndExtruder()
        if machine:
            return machine.getProperty(self.name, "value")
        return None

    def restore(self):
        machine, extruder = self._getMachineAndExtruder()
        if machine and self._cached_value and self._cached_value != self.value():
            machine.setProperty(self.name, "value", self._cached_value, set_from_cache=True)
            machine.setProperty(self.name, "state", InstanceState.Default, set_from_cache=True)

class ExtruderProperty(ContainerProperty):
    NAMES = [
        "line_width",                       #  Line Width
        "wall_line_width",                  #  Wall Line Width
        "wall_line_width_x",                #  Outer Wall Line Width
        "wall_line_width_0",                #  Inner Wall Line Width
        "wall_line_count",                  #  Wall Line Count
        "wall_thickness",                   #  Wall Thickness
        "skin_angles",                      #  Skin (Top/Bottom) Angles
        "top_layers",                       #  Top Layers
        "bottom_layers",                    #  Bottom Layers
        "infill_pattern",                   #  Infill Pattern
        "infill_sparse_density",            #  Infill Density
        "infill_angles",                    #  Infill Angles
        "infill_line_distance",             #  Infill Line Distance
        "infill_sparse_thickness",          #  Infill Line Width
        "infill_line_width",                #  Infill Line Width
        "alternate_extra_perimeter",        #  Alternate Extra Walls
        "initial_layer_line_width_factor",  # % Scale for the initial layer line width
        "top_bottom_pattern",               # Top / Bottom pattern
        "top_bottom_pattern_0",             # Initial top / bottom pattern
        "gradual_infill_steps",             
        "mold_enabled",
        "magic_mesh_surface_mode",
        "spaghetti_infill_enabled",
        "magic_fuzzy_skin_enabled",
        "skin_line_width"
    ]

    def value(self):
        machine, extruder = self._getMachineAndExtruder()
        if extruder:
            return extruder.getProperty(self.name, "value")
        return None

    def restore(self):
        machine, extruder = self._getMachineAndExtruder()
        if extruder and self._cached_value and self._cached_value != self.value():
            extruder.setProperty(self.name, "value", self._cached_value, set_from_cache=True)
            extruder.setProperty(self.name, "state", InstanceState.Default, set_from_cache=True)

class SelectedMaterial(TrackedProperty):
    def __init__(self):
        self._cached_material = None

    def value(self):
        machine, extruder = self._getMachineAndExtruder()
        if extruder:
            return extruder.material

    def cache(self):
        self._cached_material = self.value()

    def restore(self):
        machine, extruder = self._getMachineAndExtruder()
        if extruder and self._cached_material:
            extruder.material = self._cached_material

    def changed(self) -> bool:
        return not (self._cached_material is self.value())

class Scene(TrackedProperty):
    def __init__(self):
        self._print_node = None
        self._print_node_scale = None
        self._print_node_ori = None

    def value(self):
        nodes = getPrintableNodes()
        if nodes:
            n = nodes[0]
            return (n, n.getScale(), n.getOrientation())
        return None, None, None

    def cache(self):
        self._print_node, self._print_node_scale, self._print_node_ori = self.value()

    def restore(self):
        self._print_node.setScale(self._print_node_scale)
        self._print_node.setOrientation(self._print_node_ori)
        self._print_node.transformationChanged.emit(self._print_node)

    def changed(self) -> bool:
        node, scale, ori = self.value()

        if self._print_node is not node:
            # What should we do here? The entire model was swapped out
            self.cache()
            return False

        return \
            scale != self._print_node_scale or \
            ori != self._print_node_ori

class ModifierMesh(TrackedProperty):
    def __init__(self):
        self._node = None

    def value(self):
        nodes = getModifierMeshes()
        for n in nodes:
            if n.getName() == "SmartSliceMeshModifier.stl":
                return n
        return None

    def cache(self):
        self._node = self.value()

    def restore(self):
        if self._node:
            #self._node.setPosition(position, SceneNode.TransformSpace.World)
            scene_root = CuraApplication.getInstance().getController().getScene().getRoot()
            scene_root.addChild(self._node)

    def changed(self) -> bool:
        return not (self._node is self.value())

    def getNode(self) -> Optional[CuraSceneNode]:
        return self._node

class ToolProperty(TrackedProperty):
    def __init__(self, tool, property):
        self._tool = tool
        self._property = property
        self._cached_value = None

    @property
    def name(self):
        return self._property

    def value(self):
        return getattr(self._tool, 'get' + self._property)()

    def cache(self):
        self._cached_value = self.value()

    def restore(self):
        getattr(self._tool, 'set' + self._property)(self._cached_value)

    def changed(self) -> bool:
        return self._cached_value != self.value()

class FaceSelectionProperty(TrackedProperty):
    def __init__(self, selector):
        self._selector = selector
        self._cached_triangles = None

    def value(self):
        return self._selector.triangles

    def cache(self):
        self._cached_triangles = copy.copy(self.value())

    def restore(self):
        self._selector.triangles.clear()
        self._selector.triangles.extend(self._cached_triangles)

    def changed(self) -> bool:
        return set(self._cached_triangles) != set(self.value())
