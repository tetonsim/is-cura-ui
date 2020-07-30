from typing import Tuple, List

import numpy

import pywim

from PyQt5.QtCore import pyqtProperty

from UM.i18n import i18nCatalog

from UM.Application import Application
from UM.Logger import Logger
from UM.Math.Matrix import Matrix
from UM.Signal import Signal
from UM.Tool import Tool
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Selection import Selection
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator

from ..stage import SmartSliceScene
from ..stage import SmartSliceStage
from ..utils import getPrintableNodes
from ..utils import findChildSceneNode
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
            if not self.getEnabled():
                return

            if self._bc_list is None:
                return

            bc_node = self._bc_list.getActiveNode()

            if bc_node is None:
                return

            selected_triangles, axis = self._getSelectedTriangles(current_surface, bc_node.surface_type)

            if selected_triangles is not None:
                bc_node.setMeshDataFromPywimTriangles(selected_triangles)

            self._connector.updateStatus()

            self.selectedFaceChanged.emit()

    def _getSelectedTriangles(
        self,
        current_surface : Tuple[SceneNode, int],
        surface_type : SmartSliceScene.SurfaceType
    ) -> Tuple[List[pywim.geom.tri.Triangle], pywim.geom.Vector]:

        if current_surface is None:
            current_surface = Selection.getSelectedFace()

        if current_surface is None:
            return None, None

        node, face_id = current_surface

        smart_slice_node = findChildSceneNode(node, SmartSliceScene.Root)

        if surface_type == SmartSliceScene.SurfaceType.Flat:
            selected_triangles = smart_slice_node._interactive_mesh.select_planar_face(face_id)
        elif surface_type == SmartSliceScene.SurfaceType.Concave:
            selected_triangles = smart_slice_node._interactive_mesh.select_concave_face(face_id)
        elif surface_type == SmartSliceScene.SurfaceType.Convex:
            selected_triangles = smart_slice_node._interactive_mesh.select_convex_face(face_id)

        selected_triangles = list(selected_triangles)
        axis = None

        if len(selected_triangles) > 0:
            if surface_type == SmartSliceScene.SurfaceType.Flat:
                # If the surface type is flat then the axis we care about for
                # applying the load is just the surface normal
                axis = selected_triangles[0].normal
            elif len(selected_triangles) >= 2:
                # For curved surfaces we want to find a constant axis of rotation.
                # We start by computing a vector perpendicular to any two triangle
                # normals.
                normals = [t.normal for t in selected_triangles]

                n0 = normals[0]
                for n1 in normals[1:]:
                    possible_cyl_axis = n0.cross(n1)

                    # If the magnitude of the axis is very small then the two
                    # triangles are likely co-planar so let's continue and try
                    # a different combination.
                    if possible_cyl_axis.magnitude() < 1.0E-4:
                        continue

                    # We now construct a Plane, that the computed axis is normal
                    # to. We'll use this to compute an angle from the plane to each
                    # triangle normal. If any triangle normal deviates from the plane
                    # by more than our tolerance for a co-planar triangle then we'll
                    # assume the selected curved surface does NOT have a constant axis
                    # of rotation.

                    plane = pywim.geom.Plane(possible_cyl_axis)

                    max_angle = max([plane.vector_angle(n) for n in normals])

                    if max_angle < pywim.geom.tri.Mesh._COPLANAR_ANGLE:
                        axis = possible_cyl_axis.unit()

                    break

            if axis:
                # Compute the origin of the axis from an average
                # of the coordinates of all selected vertices.
                verts = set()
                for t in selected_triangles:
                    verts.update(set([t.v1, t.v2, t.v3 ]))
                axis.origin.x = sum([v.x for v in verts]) / len(verts)
                axis.origin.y = sum([v.y for v in verts]) / len(verts)
                axis.origin.z = sum([v.z for v in verts]) / len(verts)

        return selected_triangles, axis

    def redraw(self):
        if not self.getEnabled():
            return

    def _onActiveStateChanged(self):
        if not self.getEnabled():
            return

        controller = Application.getInstance().getController()
        stage = controller.getActiveStage()

        if stage.getPluginId() == self.getPluginId():
            controller.setFallbackTool(stage._our_toolset[0])
        else:
            return

        if Selection.hasSelection():
            Selection.setFaceSelectMode(True)
            Logger.log("d", "Enabled faceSelectMode!")
        else:
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

        return SmartSliceScene.SurfaceType.Flat

    def setSurfaceType(self, surface_type : SmartSliceScene.SurfaceType):
        if self._bc_list:
            bc_node = self._bc_list.getActiveNode()
            if bc_node:
                bc_node.surface_type = surface_type

    def setSurfaceTypeFlat(self):
        self.setSurfaceType(SmartSliceScene.SurfaceType.Flat)

    def setSurfaceTypeConcave(self):
        self.setSurfaceType(SmartSliceScene.SurfaceType.Concave)

    def setSurfaceTypeConvex(self):
        self.setSurfaceType(SmartSliceScene.SurfaceType.Convex)
