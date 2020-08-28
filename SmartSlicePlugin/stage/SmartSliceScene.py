from typing import List, Any, Union
from enum import Enum

import math

from UM.Logger import Logger
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Math.Color import Color
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Math.Quaternion import Quaternion
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Selection import Selection
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Signal import Signal
from UM.Application import Application

from ..utils import makeInteractiveMesh, getPrintableNodes, angleBetweenVectors
from ..select_tool.LoadArrow import LoadArrow
from .. select_tool.LoadRotator import LoadRotator
from .. select_tool.LoadToolHandle import LoadToolHandle

import pywim
import numpy

class Force:

    loadChanged = Signal()

    class DirectionType(Enum):
        Normal = 1
        Parallel = 2

    def __init__(self, direction_type: DirectionType = DirectionType.Normal, magnitude: float = 10.0, pull: bool = False):

        self._direction_type = direction_type
        self._magnitude = magnitude
        self._pull = pull

    @property
    def direction_type(self):
        return self._direction_type

    @direction_type.setter
    def direction_type(self, value: DirectionType):
        if self._direction_type != value:
            self._direction_type = value
            self.loadChanged.emit()

    @property
    def magnitude(self):
        return self._magnitude

    @magnitude.setter
    def magnitude(self, value: float):
        if self._magnitude != value:
            self._magnitude = value
            self.loadChanged.emit()

    @property
    def pull(self):
        return self._pull

    @pull.setter
    def pull(self, value: bool):
        if self._pull != value:
            self._pull = value
            self.loadChanged.emit()

    def setFromVectorAndAxis(self, load_vector: pywim.geom.Vector, axis: pywim.geom.Vector):
        self.magnitude = round(load_vector.magnitude(), 2)

        if not axis:
            return

        if load_vector.origin.close(axis.origin, 1.e-3):
            self.pull = True
        else:
            self.pull = False

        angle = load_vector.angle(axis)
        if abs(abs(angle) - math.pi * 0.5) < 1.e-3:
            self.direction_type = Force.DirectionType.Parallel
        else:
            self.direction_type = Force.DirectionType.Normal

class HighlightFace(SceneNode):

    facePropertyChanged = Signal()
    surfaceTypeChanged = Signal()

    class SurfaceType(Enum):
        Unknown = 0
        Flat = 1
        Concave = 2
        Convex = 3

    def __init__(self, name: str):
        super().__init__(name=name, visible=True)

        self.face = pywim.geom.tri.Face()
        self._surface_type = self.SurfaceType.Flat
        self.axis = None #pywim.geom.vector
        self.selection = None

    @property
    def surface_type(self):
        return self._surface_type

    @surface_type.setter
    def surface_type(self, value: SurfaceType):
        if self._surface_type != value:
            self._surface_type = value
            self.surfaceTypeChanged.emit()

    def setVisible(self, visible):
        super().setVisible(visible)
        if visible:
            self.enableTools()
        else:
            self.disableTools()

    def _setupTools(self):
        pass

    def getTriangleIndices(self) -> List[int]:
        return [t.id for t in self.face.triangles]

    def getTriangles(self):
        return self.face.triangles

    def clearSelection(self):
        self.face = pywim.geom.tri.Face()
        self.axis = None
        super().setMeshData(None)

    def setMeshDataFromPywimTriangles(
        self, face: pywim.geom.tri.Face,
        axis: pywim.geom.Vector = None
    ):

        if len(face.triangles) == 0:
            return

        self.face = face
        self.axis = axis

        mb = MeshBuilder()

        for tri in self.face.triangles:
            mb.addFace(tri.v1, tri.v2, tri.v3)

        mb.calculateNormals()

        self.setMeshData(mb.build())

        self._setupTools()

    def pywimBoundaryCondition(self, step: pywim.chop.model.Step, mesh_rotation: Matrix):
        raise NotImplementedError()

    def enableTools(self):
        pass

    def disableTools(self):
        pass

class AnchorFace(HighlightFace):
    color = Color(1., 0.4, 0.4, 1.)

    def pywimBoundaryCondition(self, step: pywim.chop.model.Step, mesh_rotation: Matrix):
        # Create the fixed boundary conditions (anchor points)
        anchor = pywim.chop.model.FixedBoundaryCondition(name=self.getName())

        # Add the face Ids from the STL mesh that the user selected for this anchor
        a = self.face.triangles
        b = self.getTriangleIndices()
        anchor.face.extend(self.getTriangleIndices())

        Logger.log("d", "Smart Slice {} Triangles: {}".format(self.getName(), anchor.face))

        step.boundary_conditions.append(anchor)

        return anchor

    def setMeshDataFromPywimTriangles(
        self, tris: List[pywim.geom.tri.Triangle],
        axis: pywim.geom.Vector = None
    ):
        axis = None

        super().setMeshDataFromPywimTriangles(tris, axis)


class LoadFace(HighlightFace):
    color = Color(0.4, 0.4, 1., 1.)

    def __init__(self, name: str):
        super().__init__(name)

        self.force = Force()
        self._axis = None

        self._arrows = {
            True: LoadArrow(self),
            False: LoadArrow(self)
        }
        self._rotator = LoadRotator(self)
        self._rotator.buildMesh()
        for key, arrow in self._arrows.items():
            arrow.buildMesh(pull = key)

        self.disableTools()

    @property
    def activeArrow(self):
        return self._arrows[self.force.pull]

    @property
    def inactiveArrow(self):
        return self._arrows[not self.force.pull]

    def getRotator(self):
        return self._rotator

    def setVisible(self, visible):
        super().setVisible(visible)

        if visible:
            self.enableRotatorIfNeeded()

    def setMeshDataFromPywimTriangles(
        self, tris: List[pywim.geom.tri.Triangle],
        axis: pywim.geom.Vector = None
    ):

        # If there is no axis, we don't know where to put the arrow, so we don't do anything
        if axis is None:
            self.clearSelection()
            self.disableTools()
            return

        super().setMeshDataFromPywimTriangles(tris, axis)

    def pywimBoundaryCondition(self, step: pywim.chop.model.Step, mesh_rotation: Matrix):

        force = pywim.chop.model.Force(name=self.getName())

        load_vec = self.activeArrow.direction.normalized() * self.force.magnitude
        rotated_load_vec = numpy.dot(mesh_rotation.getData(), load_vec.getData())

        Logger.log("d", "Smart Slice {} Vector: {}".format(self.getName(), rotated_load_vec))

        force.force.set(
            [float(rotated_load_vec[0]), float(rotated_load_vec[1]), float(rotated_load_vec[2])]
        )

        if self.force.pull:
            arrow_start = self._rotator.center
        else:
            arrow_start = self.activeArrow.tailPosition
        rotated_start = numpy.dot(mesh_rotation.getData(), arrow_start.getData())

        if self.axis:
            force.origin.set([
                float(rotated_start[0]),
                float(rotated_start[1]),
                float(rotated_start[2]),
            ])

        # Add the face Ids from the STL mesh that the user selected for this force
        force.face.extend(self.getTriangleIndices())

        Logger.log("d", "Smart Slice {} Triangles: {}".format(self.getName(), force.face))

        step.loads.append(force)

        return force

    def _setupTools(self):
        self.enableTools()

        if self.axis is None:
            self.disableTools()
            return

        center = Vector(
            self.axis.origin.x,
            self.axis.origin.y,
            self.axis.origin.z,
        )

        rotation_axis = Vector(
            self.axis.r,
            self.axis.s,
            self.axis.t
        )

        if self.surface_type == HighlightFace.SurfaceType.Flat and self.force.direction_type is Force.DirectionType.Parallel:
            self.setToolPerpendicularToAxis(center, rotation_axis)

        elif self.surface_type != HighlightFace.SurfaceType.Flat and self.force.direction_type is Force.DirectionType.Normal:
            self.setToolPerpendicularToAxis(center, rotation_axis)

        else:
            self.setToolParallelToAxis(center, rotation_axis)

    def enableTools(self):
        if len(self.face.triangles) == 0:
            self.disableTools()
            return

        self._arrows[self.force.pull].setEnabled(True)
        self._arrows[not self.force.pull].setEnabled(False)

        self._rotator.setEnabled(True)

    def disableTools(self):
        self._arrows[True].setEnabled(False)
        self._arrows[False].setEnabled(False)

        self._rotator.setEnabled(False)

    def setToolPerpendicularToAxis(self, center: Vector, normal: Vector):
        axis = self._rotator.rotation_axis.cross(normal)
        angle = angleBetweenVectors(normal, self._rotator.rotation_axis)

        if axis.length() < 1.e-3:
            axis = normal

        self._alignToolsToCenterAxis(center, axis, angle)

    def setToolParallelToAxis(self, center: Vector, normal: Vector):

        normal_reverse = -1 * normal

        axis = self._arrows[False].direction.cross(normal_reverse)
        angle = angleBetweenVectors(normal_reverse, self._arrows[False].direction)

        if axis.length() < 1.e-3:
            axis = self._rotator.rotation_axis

        self._alignToolsToCenterAxis(center, axis, angle)

        self._rotator.setEnabled(False)

    def flipArrow(self):
        if len(self.face.triangles) == 0:
            return

        self._arrows[self.force.pull].setEnabled(True)

        self._arrows[not self.force.pull].setEnabled(False)

        self.meshDataChanged.emit(self)

    def rotateArrow(self, angle: float):
        matrix = Quaternion.fromAngleAxis(angle, self._rotator.rotation_axis)

        self.inactiveArrow.setEnabled(True)

        self.activeArrow.setPosition(-self._rotator.center)
        self.inactiveArrow.setPosition(-self._rotator.center)

        self.activeArrow.rotate(matrix, SceneNode.TransformSpace.World)
        self.inactiveArrow.rotate(matrix, SceneNode.TransformSpace.World)

        self.activeArrow.setPosition(self._rotator.center)
        self.inactiveArrow.setPosition(self._rotator.center)

        self.inactiveArrow.setEnabled(False)

        self.activeArrow.direction = matrix.rotate(self.activeArrow.direction)
        self.inactiveArrow.direction = matrix.rotate(self.inactiveArrow.direction)

    def setArrow(self, direction: Vector):
        self.flipArrow()

        # No need to rotate an arrow if the rotator is disabled
        if not self._rotator.isEnabled():
            return

        # Rotate the arrow to the desired direction
        angle = angleBetweenVectors(self.activeArrow.direction, direction)

        # Check to make sure we will rotate the arrow corectly
        axes_angle = angleBetweenVectors(self._rotator.rotation_axis, direction.cross(self.activeArrow.direction))
        angle = -angle if abs(axes_angle) < 1.e-3 else angle

        self.rotateArrow(angle)

    def _alignToolsToCenterAxis(self, position: Vector, axis: Vector, angle: float):
        matrix = Quaternion.fromAngleAxis(angle, axis)

        self.inactiveArrow.setEnabled(True)
        self.activeArrow.rotate(matrix, SceneNode.TransformSpace.World)
        self.inactiveArrow.rotate(matrix, SceneNode.TransformSpace.World)
        self._rotator.rotate(matrix, SceneNode.TransformSpace.World)

        self.activeArrow.direction = matrix.rotate(self.activeArrow.direction)
        self.inactiveArrow.direction = matrix.rotate(self.inactiveArrow.direction)
        if axis.cross(self._rotator.rotation_axis).length() > 1.e-3:
            self._rotator.rotation_axis = matrix.rotate(self._rotator.rotation_axis)
        else:
            self._rotator.rotation_axis = axis

        self.activeArrow.setPosition(position)
        self.inactiveArrow.setPosition(position)
        self._rotator.setPosition(position)

        self.inactiveArrow.setEnabled(False)

    def enableRotatorIfNeeded(self):
        if len(self.face.triangles) > 0:
            if self.surface_type == HighlightFace.SurfaceType.Flat and self.force.direction_type is Force.DirectionType.Parallel:
                self._rotator.setEnabled(True)

            elif self.surface_type != HighlightFace.SurfaceType.Flat and self.force.direction_type is Force.DirectionType.Normal:
                self._rotator.setEnabled(True)

            else:
                self._rotator.setEnabled(False)

        else:
            self._rotator.setEnabled(False)

class Root(SceneNode):
    faceAdded = Signal()
    faceRemoved = Signal()
    rootChanged = Signal()

    def __init__(self):
        super().__init__(name='_SmartSlice', visible=True)

    def initialize(self, parent: SceneNode):
        parent.addChild(self)

        mesh_data = parent.getMeshData()

        if mesh_data:
            Logger.log('d', 'Compute interactive mesh from SceneNode {}'.format(parent.getName()))

            self._interactive_mesh = makeInteractiveMesh(mesh_data)

        self.rootChanged.emit(self)

    def getInteractiveMesh(self) -> pywim.geom.tri.Mesh:
        return self._interactive_mesh

    def addFace(self, bc):
        self.addChild(bc)
        self.faceAdded.emit(bc)

    def removeFace(self, bc):
        self.removeChild(bc)
        self.faceRemoved.emit(bc)

    def loadStep(self, step):
        selected_node = Selection.getSelectedObject(0)

        for bc in step.boundary_conditions:
            selected_face = self._interactive_mesh.face_from_ids(bc.face)
            face = AnchorFace(str(bc.name))
            face.selection = (selected_node, bc.face[0])

            if len(selected_face.triangles) > 0:
                face.surface_type = self._guessSurfaceTypeFromTriangles(selected_face)

                axis = None
                if face.surface_type == HighlightFace.SurfaceType.Flat:
                    axis = selected_face.planar_axis()
                elif face.surface_type != face.SurfaceType.Unknown:
                    axis = selected_face.rotation_axis()

            face.setMeshDataFromPywimTriangles(selected_face, axis)
            face.disableTools()

            self.addFace(face)

        for bc in step.loads:
            selected_face = self._interactive_mesh.face_from_ids(bc.face)
            face = LoadFace(str(bc.name))
            face.selection = (selected_node, bc.face[0])

            load_prime = Vector(
                bc.force[0],
                bc.force[1],
                bc.force[2]
            )

            origin_prime = Vector(
                bc.origin[0],
                bc.origin[1],
                bc.origin[2]
            )

            print_to_cura = Matrix()
            print_to_cura._data[1, 1] = 0
            print_to_cura._data[1, 2] = 1
            print_to_cura._data[2, 1] = -1
            print_to_cura._data[2, 2] = 0

            _, rotation, _, _ = print_to_cura.decompose()

            load = numpy.dot(rotation.getData(), load_prime.getData())
            origin = numpy.dot(rotation.getData(), origin_prime.getData())

            rotated_load = pywim.geom.Vector(
                load[0],
                load[1],
                load[2]
            )

            rotated_load.origin = pywim.geom.Vertex(
                origin[0],
                origin[1],
                origin[2]
            )

            if len(selected_face.triangles) > 0:
                face.surface_type = self._guessSurfaceTypeFromTriangles(selected_face)

                axis = None
                if face.surface_type == HighlightFace.SurfaceType.Flat:
                    axis = selected_face.planar_axis()
                elif face.surface_type != face.SurfaceType.Unknown:
                    axis =selected_face.rotation_axis()

                face.force.setFromVectorAndAxis(rotated_load, axis)

                # Need to reverse the load direction for concave / convex surface
                if face.surface_type == HighlightFace.SurfaceType.Concave or face.surface_type == HighlightFace.SurfaceType.Convex:
                    if face.force.direction_type == Force.DirectionType.Normal:
                        face.force.direction_type = Force.DirectionType.Parallel
                    else:
                        face.force.direction_type = Force.DirectionType.Normal

            face.setMeshDataFromPywimTriangles(selected_face, axis)

            face.setArrow(Vector(
                load[0],
                load[1],
                load[2]
            ))

            self.addFace(face)
            face.disableTools()

    def createSteps(self) -> pywim.WimList:
        steps = pywim.WimList(pywim.chop.model.Step)

        step = pywim.chop.model.Step(name='step-1')

        normal_mesh = getPrintableNodes()[0]

        cura_to_print = Matrix()
        cura_to_print._data[1, 1] = 0
        cura_to_print._data[1, 2] = -1
        cura_to_print._data[2, 1] = 1
        cura_to_print._data[2, 2] = 0

        mesh_transformation = normal_mesh.getLocalTransformation()
        mesh_transformation.preMultiply(cura_to_print)

        _, mesh_rotation, _, _ = mesh_transformation.decompose()

        # Add boundary conditions from the selected faces in the Smart Slice node
        for bc_node in DepthFirstIterator(self):
            if hasattr(bc_node, 'pywimBoundaryCondition'):
                bc = bc_node.pywimBoundaryCondition(step, mesh_rotation)

        steps.add(step)

        return steps

    def setOrigin(self):
        controller = Application.getInstance().getController()
        camTool = controller.getCameraTool()
        camTool.setOrigin(self.getParent().getBoundingBox().center)

    def _guessSurfaceTypeFromTriangles(self, face: pywim.geom.tri.Face) -> HighlightFace.SurfaceType:
        """
            Attempts to determine the face type from a pywim face
            Will return Unknown if it cannot determine the type
        """
        triangle_list = list(face.triangles)
        if not face.triangles:
            return HighlightFace.SurfaceType.Unknown
        elif len(self._interactive_mesh.select_planar_face(triangle_list[0]).triangles) == len(face.triangles):
            return HighlightFace.SurfaceType.Flat
        elif len(self._interactive_mesh.select_concave_face(triangle_list[0]).triangles) == len(face.triangles):
            return HighlightFace.SurfaceType.Concave
        elif len(self._interactive_mesh.select_convex_face(triangle_list[0]).triangles) == len(face.triangles):
            return HighlightFace.SurfaceType.Convex

        return HighlightFace.SurfaceType.Unknown
