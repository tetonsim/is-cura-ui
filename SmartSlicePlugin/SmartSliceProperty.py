from typing import List, Optional

import copy
from enum import Enum

from UM.Settings.SettingInstance import InstanceState

from cura.CuraApplication import CuraApplication

from . utils import getPrintableNodes
from .stage.SmartSliceScene import HighlightFace, LoadFace, Root

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
    EXTRUDER_KEYS = [
        "wall_extruder_nr",                 # Both wall extruder drop down
        "wall_0_extruder_nr",               # Outer wall extruder
        "wall_x_extruder_nr",               # Inner wall extruder
        "infill_extruder_nr"                # Infill extruder
    ]

    NAMES = EXTRUDER_KEYS + [
        "line_width",                       # Line Width
        "wall_line_width",                  # Wall Line Width
        "wall_line_width_x",                # Outer Wall Line Width
        "wall_line_width_0",                # Inner Wall Line Width
        "wall_line_count",                  # Wall Line Count
        "wall_thickness",                   # Wall Thickness
        "skin_angles",                      # Skin (Top/Bottom) Angles
        "top_layers",                       # Top Layers
        "bottom_layers",                    # Bottom Layers
        "infill_pattern",                   # Infill Pattern
        "infill_sparse_density",            # Infill Density
        "infill_angles",                    # Infill Angles
        "infill_line_distance",             # Infill Line Distance
        "infill_sparse_thickness",          # Infill Line Width
        "infill_line_width",                # Infill Line Width
        "alternate_extra_perimeter",        # Alternate Extra Walls
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
    def __init__(self, node=None, name=None):
        self.parent_changed = False
        self.mesh_name = name
        self._node = node
        self._properties = None
        self._prop_changed = None
        self._names = [
            "line_width",                       #  Line Width
            "wall_line_width",                  #  Wall Line Width
            "wall_line_width_x",                #  Outer Wall Line Width
            "wall_line_width_0",                #  Inner Wall Line Width
            "wall_line_count",                  #  Wall Line Count
            "wall_thickness",                   #  Wall Thickness
            "top_layers",                       #  Top Layers
            "bottom_layers",                    #  Bottom Layers
            "infill_pattern",                   #  Infill Pattern
            "infill_sparse_density",            #  Infill Density
            "infill_sparse_thickness",          #  Infill Line Width
            "infill_line_width",                #  Infill Line Width
            "top_bottom_pattern",               # Top / Bottom pattern
        ]

    def value(self):
        if self._node:
            stack = self._node.callDecoration("getStack").getTop()
            properties = tuple([stack.getProperty(property, "value") for property in self._names])
            return properties
        return None

    def cache(self):
        self._properties = self.value()

    def changed(self):
        if self._node:
            properties = self.value()
            prop_changed = [[name, prop] for name, prop in zip(self._names, self._properties) if prop not in properties]
            if prop_changed:
                self._prop_changed = prop_changed[0]
                return True

    def restore(self):
        if self._node and self._prop_changed:
            node = self._node.callDecoration("getStack").getTop()
            node.setProperty(self._prop_changed[0], "value", self._prop_changed[1])
            self._prop_changed = None

    def parentChanged(self, parent):
        self.parent_changed = True


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


class SmartSliceFace(TrackedProperty):

    class Properties:

        def __init__(self):
            self.surface_type = None
            self.tri_face = None
            self.axis = None
            self.selection = None

    def __init__(self, face: HighlightFace):
        self.highlight_face = face
        self._properties = SmartSliceFace.Properties()

    def value(self):
        return self.highlight_face

    def cache(self):
        highlight_face = self.value()
        self._properties.tri_face = highlight_face.face
        self._properties.surface_type = highlight_face.surface_type
        self._properties.axis = highlight_face.axis
        self._properties.selection = highlight_face.selection

    def changed(self) -> bool:
        highlight_face = self.value()

        return highlight_face.getTriangles() != self._properties.tri_face.triangles or \
            highlight_face.axis != self._properties.axis or \
            highlight_face.surface_type != self._properties.surface_type or \
            highlight_face.selection != self._properties.selection

    def restore(self):
        self.highlight_face.surface_type = self._properties.surface_type
        self.highlight_face.setMeshDataFromPywimTriangles(self._properties.tri_face, self._properties.axis)
        self.highlight_face.selection = self._properties.selection

class SmartSliceLoadFace(SmartSliceFace):

    class LoadFaceProperties(SmartSliceFace.Properties):

        def __init__(self):
            super().__init__()
            self.direction = None
            self.pull = None
            self.direction_type = None
            self.magnitude = None

    def __init__(self, face: LoadFace):
        self.highlight_face = face
        self._properties = SmartSliceLoadFace.LoadFaceProperties()

    def cache(self):
        highlight_face = self.value()
        super().cache()

        self._properties.direction = highlight_face.activeArrow.direction
        self._properties.direction_type = highlight_face.force.direction_type
        self._properties.pull = highlight_face.force.pull
        self._properties.magnitude = highlight_face.force.magnitude

    def changed(self) -> bool:
        highlight_face = self.value()

        return super().changed() or \
            highlight_face.force.magnitude != self._properties.magnitude or \
            highlight_face.force.direction_type != self._properties.direction_type or \
            highlight_face.force.pull != self._properties.pull or \
            highlight_face.activeArrow.direction != self._properties.direction

    def restore(self):
        self.highlight_face.force.magnitude = self._properties.magnitude
        self.highlight_face.force.pull = self._properties.pull
        self.highlight_face.force.direction_type = self._properties.direction_type

        super().restore()

        self.highlight_face.setArrow(self._properties.direction)

class SmartSliceSceneRoot(TrackedProperty):
    def __init__(self, root: Root = None):
        self._root = root
        self._faces = [] # HighlightFaces

    def value(self):
        faces = []
        if self._root:
            for child in self._root.getAllChildren():
                if isinstance(child, HighlightFace):
                    faces.append(child)
        return faces

    def cache(self):
        self._faces = self.value()

    def changed(self) -> bool:
        faces = self.value()
        if len(self._faces) != len(faces):
            return True

        return False

    def restore(self):
        if self._root is None:
            return

        faces = self.value()

        # Remove any faces which were added
        for f in faces:
            if f not in self._faces:
                self._root.removeChild(f)

        # Add any faces which were removed
        for f in self._faces:
            if f not in faces:
                self._root.addChild(f)
