from typing import List, Optional

import copy
from enum import Enum

from UM.Settings.SettingInstance import InstanceState

from cura.CuraApplication import CuraApplication

from . utils import getPrintableNodes, getNodeActiveExtruder
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

    NAMES = [
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

class ActiveExtruder(TrackedProperty):
    def __init__(self):
        self._active_extruder_index = None

    def value(self):
        return CuraApplication.getInstance().getExtruderManager().activeExtruderIndex

    def cache(self):
        self._active_extruder_index = self.value()

    def restore(self):
        CuraApplication.getInstance().getExtruderManager().setActiveExtruderIndex(self._active_extruder_index)

    def changed(self):
        return self.value() != self._active_extruder_index

class SceneNodeExtruder(TrackedProperty):
    def __init__(self, node=None):
        self._node = node
        self._active_extruder_index = None
        self._specific_extruders = {}

    def value(self):
        if self._node:
            active_extruder = getNodeActiveExtruder(self._node)

            active_extruder_index = int(active_extruder.getMetaDataEntry("position"))

            specific_indices = {}
            for key in ExtruderProperty.EXTRUDER_KEYS:
                specific_indices[key] = int(active_extruder.getProperty(key, "value"))

            return active_extruder_index, specific_indices

        return None, None

    def cache(self):
        self._active_extruder_index, self._specific_extruders = self.value()

    def restore(self):
        if self._node:
            extruder_list = CuraApplication.getInstance().getGlobalContainerStack().extruderList
            machine, extruder = self._getMachineAndExtruder()
            extruder = getNodeActiveExtruder(self._node)

            self._node.callDecoration("setActiveExtruder", extruder_list[self._active_extruder_index].id)

            for key in ExtruderProperty.EXTRUDER_KEYS:
                machine.setProperty(key, "value", self._specific_extruders[key])

    def changed(self):
        active_extruder_index, specific_indices = self.value()

        for key, value in self._specific_extruders.items():
            if value != specific_indices[key]:
                return True

        return active_extruder_index != self._active_extruder_index

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
        return self._cached_material != self.value()

class Transform(TrackedProperty):
    def __init__(self, node=None):
        self._node = node
        self._scale = None
        self._orientation = None

    def value(self):
        if self._node:
            return self._node.getScale(), self._node.getOrientation()
        return None, None

    def cache(self):
        self._scale, self._orientation = self.value()

    def restore(self):
        if self._node:
            self._node.setScale(self._scale)
            self._node.setOrientation(self._orientation)
            self._node.transformationChanged.emit(self._node)

    def changed(self) -> bool:
        scale, orientation = self.value()
        return scale != self._scale or orientation != self._orientation

class SceneNode(TrackedProperty):
    def __init__(self, node=None, name=None):
        self.parent_changed = False
        self.mesh_name = name
        self._node = node
        self._properties = {}
        self._transform = Transform(node)
        self._extruder = SceneNodeExtruder(node)
        self._names = ExtruderProperty.NAMES

    def value(self):
        if self._node:
            stack = self._node.callDecoration("getStack").getTop()
            properties = {}
            for prop in self._names:
                properties[prop] = stack.getProperty(prop, "value")
            return properties, self._extruder.value(), self._transform.value()
        return None

    def cache(self):
        self._extruder.cache()
        self._transform.cache()
        self._properties, extruder, transform = self.value()

    def changed(self):
        if self._node:
            properties, extruder, transform = self.value()
            for key, value in self._properties.items():
                if value != properties[key]:
                    return True

            return self._extruder.changed() or self._transform.changed()

    def restore(self):
        if self._node:
            stack = self._node.callDecoration("getStack").getTop()
            for key, value in self._properties.items():
                stack.setProperty(key, "value", value)

            self._extruder.restore()
            self._transform.restore()

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
        if not self.highlight_face.isVisible():
            self.highlight_face.disableTools()

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
