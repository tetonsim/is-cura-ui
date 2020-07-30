from typing import List, Any

import enum

from UM.Logger import Logger
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Math.Color import Color
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Signal import Signal
from UM.Application import Application

from ..utils import makeInteractiveMesh, getPrintableNodes

import pywim
import numpy


class Force:
    def __init__(self, normal: Vector = None, magnitude: float = 0.0, pull: bool = False):
        self.normal = normal if normal else Vector(1.0, 0.0, 0.0)
        self.magnitude = magnitude
        self.pull = pull

    def loadVector(self, rotation: Matrix = None) -> Vector:
        scale = self.magnitude if self.pull else -self.magnitude

        v = Vector(
            self.normal.x * scale,
            self.normal.y * scale,
            self.normal.z * scale,
        )

        if rotation:
            vT = numpy.dot(rotation.getData(), v.getData())
            return Vector(vT[0], vT[1], vT[2])

        return v


class Root(SceneNode):
    faceAdded = Signal()
    faceRemoved = Signal()
    loadPropertyChanged = Signal()
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

    def magnitudeChanged(self):
        self.loadPropertyChanged.emit()

    def loadStep(self, step):
        for bc in step.boundary_conditions:
            face = AnchorFace(str(bc.name))
            face.setMeshDataFromPywimTriangles(self._interactive_mesh.triangles_from_ids(bc.face))
            self.addFace(face)

        for bc in step.loads:
            face = LoadFace(str(bc.name))
            face.setMeshDataFromPywimTriangles(self._interactive_mesh.triangles_from_ids(bc.face))
            face.force.magnitude = abs(sum(bc.force))

            load_tuple = bc.force
            load_vector = Vector(
                load_tuple[0],
                load_tuple[1],
                load_tuple[2]
            )

            __, rotation = self.rotation()
            rotated_load_vector = numpy.dot(rotation.getData(), load_vector.getData())
            rotated_vector = Vector(rotated_load_vector[0], rotated_load_vector[1], rotated_load_vector[2])

            rotated_load = pywim.geom.Vector(
                rotated_vector.x,
                rotated_vector.y,
                rotated_vector.z
            )

            if len(face.getTriangles()) > 0:
                face_normal = face.getTriangles()[0].normal
                face.force.normal = Vector(
                    face_normal.r,
                    face_normal.s,
                    face_normal.t
                )

                if face_normal.angle(rotated_load) < self._interactive_mesh._COPLANAR_ANGLE:
                    face.setArrowDirection(True)
                else:
                    face.setArrowDirection(False)

            self.addFace(face)

    def createSteps(self) -> pywim.WimList:
        steps = pywim.WimList(pywim.chop.model.Step)

        step = pywim.chop.model.Step(name='step-1')

        normal_mesh = getPrintableNodes()[0]

        transformation, __ = self.rotation()

        mesh_transformation = normal_mesh.getLocalTransformation()
        mesh_transformation.preMultiply(transformation)

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

    @staticmethod
    def rotation():
        transformation = Matrix()
        transformation.setRow(1, [0, 0, 1, 0])
        transformation.setRow(2, [0, -1, 0, 0])
        _, rotation, _, _ = transformation.decompose()
        return transformation, rotation


class SurfaceType(enum.Enum):
    Flat = 1
    Concave = 2
    Convex = 3

class HighlightFace(SceneNode):

    def __init__(self, name: str):
        super().__init__(name=name, visible=True)

        self._triangles = []

        self.surface_type = SurfaceType.Flat

    def _annotatedMeshData(self, mb: MeshBuilder):
        pass

    def getTriangleIndices(self) -> List[int]:
        return [t.id for t in self._triangles]

    def getTriangles(self):
        return self._triangles

    def setMeshDataFromPywimTriangles(self, tris: List[pywim.geom.tri.Triangle]):
        self._triangles = tris

        mb = MeshBuilder()

        for tri in self._triangles:
            mb.addFace(tri.v1, tri.v2, tri.v3)

        self._annotatedMeshData(mb)

        mb.calculateNormals()

        self.setMeshData(mb.build())

    def pywimBoundaryCondition(self, step: pywim.chop.model.Step, mesh_rotation: Matrix):
        raise NotImplementedError()


class AnchorFace(HighlightFace):
    color = [1., 0.4, 0.4, 1.]

    def pywimBoundaryCondition(self, step: pywim.chop.model.Step, mesh_rotation: Matrix):
        # Create the fixed boundary conditions (anchor points)
        anchor = pywim.chop.model.FixedBoundaryCondition(name=self.getName())

        # Add the face Ids from the STL mesh that the user selected for this anchor
        a = self._triangles
        b = self.getTriangleIndices()
        anchor.face.extend(self.getTriangleIndices())

        Logger.log("d", "Smart Slice {} Triangles: {}".format(self.getName(), anchor.face))

        step.boundary_conditions.append(anchor)

        return anchor


class LoadFace(HighlightFace):
    color = [0.4, 0.4, 1., 1.]

    def __init__(self, name: str):
        super().__init__(name)

        self.force = Force()

        self._arrow_head_length = 8
        self._arrow_tail_length = 22
        self._arrow_total_length = self._arrow_head_length + self._arrow_tail_length
        self._arrow_head_width = 2.8
        self._arrow_tail_width = 0.8

    def setMeshDataFromPywimTriangles(self, tris: List[pywim.geom.tri.Triangle]):
        super().setMeshDataFromPywimTriangles(tris)

        if len(tris) > 0:
            n = tris[0].normal
            self.force.normal = Vector(n.r, n.s, n.t)

    def setArrowDirection(self, checked):
        self.force.pull = checked  # Check box checked indicates pulling force
        self.setMeshDataFromPywimTriangles(self._triangles)

    def pywimBoundaryCondition(self, step: pywim.chop.model.Step, mesh_rotation: Matrix):
        force = pywim.chop.model.Force(name=self.getName())

        load_vec = self.force.loadVector(mesh_rotation)

        Logger.log("d", "Smart Slice {} Vector: {}".format(self.getName(), load_vec))

        force.force.set(
            [float(load_vec.x), float(load_vec.y), float(load_vec.z)]
        )

        # Add the face Ids from the STL mesh that the user selected for this force
        force.face.extend(self.getTriangleIndices())

        Logger.log("d", "Smart Slice {} Triangles: {}".format(self.getName(), force.face))

        step.loads.append(force)

        return force

    def _annotatedMeshData(self, mb: MeshBuilder):
        """
        Draw an arrow to the normal of the given face mesh using MeshBuilder.addFace().
        Inputs:
            tris (list of faces or triangles) Only one face will be used to begin arrow.
            mb (MeshBuilder) which is drawn onto.
        """
        if len(self._triangles) <= 0:  # input list is empty
            return

        index = len(self._triangles) // 2
        tri = self._triangles[index]
        # p = tri.points
        # tri.generateNormalVector()
        n = tri.normal
        n = Vector(n.r, n.s, n.t)  # pywim Vector to UM Vector
        # invert_arrow = self._connector._proxy.loadDirection
        center = self.findFaceCenter(self._triangles)

        p_base0 = Vector(center.x + n.x * self._arrow_head_length,
                         center.y + n.y * self._arrow_head_length,
                         center.z + n.z * self._arrow_head_length)
        p_tail0 = Vector(center.x + n.x * self._arrow_total_length,
                         center.y + n.y * self._arrow_total_length,
                         center.z + n.z * self._arrow_total_length)

        if self.force.pull:
            p_base0 = Vector(center.x + n.x * self._arrow_tail_length,
                             center.y + n.y * self._arrow_tail_length,
                             center.z + n.z * self._arrow_tail_length)
            p_head = p_tail0
            p_tail0 = center
        else:  # regular
            p_head = center

        p_base1 = Vector(p_base0.x, p_base0.y + self._arrow_head_width, p_base0.z)
        p_base2 = Vector(p_base0.x, p_base0.y - self._arrow_head_width, p_base0.z)
        p_base3 = Vector(p_base0.x + self._arrow_head_width, p_base0.y, p_base0.z)
        p_base4 = Vector(p_base0.x - self._arrow_head_width, p_base0.y, p_base0.z)
        p_base5 = Vector(p_base0.x, p_base0.y, p_base0.z + self._arrow_head_width)
        p_base6 = Vector(p_base0.x, p_base0.y, p_base0.z - self._arrow_head_width)

        mb.addFace(p_base1, p_head, p_base3)
        mb.addFace(p_base3, p_head, p_base2)
        mb.addFace(p_base2, p_head, p_base4)
        mb.addFace(p_base4, p_head, p_base1)
        mb.addFace(p_base5, p_head, p_base1)
        mb.addFace(p_base6, p_head, p_base1)
        mb.addFace(p_base6, p_head, p_base2)
        mb.addFace(p_base2, p_head, p_base5)
        mb.addFace(p_base3, p_head, p_base5)
        mb.addFace(p_base5, p_head, p_base4)
        mb.addFace(p_base4, p_head, p_base6)
        mb.addFace(p_base6, p_head, p_base3)

        p_tail1 = Vector(p_tail0.x, p_tail0.y + self._arrow_tail_width, p_tail0.z)
        p_tail2 = Vector(p_tail0.x, p_tail0.y - self._arrow_tail_width, p_tail0.z)
        p_tail3 = Vector(p_tail0.x + self._arrow_tail_width, p_tail0.y, p_tail0.z)
        p_tail4 = Vector(p_tail0.x - self._arrow_tail_width, p_tail0.y, p_tail0.z)
        p_tail5 = Vector(p_tail0.x, p_tail0.y, p_tail0.z + self._arrow_tail_width)
        p_tail6 = Vector(p_tail0.x, p_tail0.y, p_tail0.z - self._arrow_tail_width)

        p_tail_base1 = Vector(p_base0.x, p_base0.y + self._arrow_tail_width, p_base0.z)
        p_tail_base2 = Vector(p_base0.x, p_base0.y - self._arrow_tail_width, p_base0.z)
        p_tail_base3 = Vector(p_base0.x + self._arrow_tail_width, p_base0.y, p_base0.z)
        p_tail_base4 = Vector(p_base0.x - self._arrow_tail_width, p_base0.y, p_base0.z)
        p_tail_base5 = Vector(p_base0.x, p_base0.y, p_base0.z + self._arrow_tail_width)
        p_tail_base6 = Vector(p_base0.x, p_base0.y, p_base0.z - self._arrow_tail_width)

        mb.addFace(p_tail1, p_tail_base1, p_tail3)
        mb.addFace(p_tail3, p_tail_base3, p_tail2)
        mb.addFace(p_tail2, p_tail_base2, p_tail4)
        mb.addFace(p_tail4, p_tail_base4, p_tail1)
        mb.addFace(p_tail5, p_tail_base5, p_tail1)
        mb.addFace(p_tail6, p_tail_base6, p_tail1)
        mb.addFace(p_tail6, p_tail_base6, p_tail2)
        mb.addFace(p_tail2, p_tail_base2, p_tail5)
        mb.addFace(p_tail3, p_tail_base3, p_tail5)
        mb.addFace(p_tail5, p_tail_base5, p_tail4)
        mb.addFace(p_tail4, p_tail_base4, p_tail6)
        mb.addFace(p_tail6, p_tail_base6, p_tail3)

        mb.addFace(p_tail_base1, p_tail_base3, p_tail3)
        mb.addFace(p_tail_base3, p_tail_base2, p_tail2)
        mb.addFace(p_tail_base2, p_tail_base4, p_tail4)
        mb.addFace(p_tail_base4, p_tail_base1, p_tail1)
        mb.addFace(p_tail_base5, p_tail_base1, p_tail1)
        mb.addFace(p_tail_base6, p_tail_base1, p_tail1)
        mb.addFace(p_tail_base6, p_tail_base2, p_tail2)
        mb.addFace(p_tail_base2, p_tail_base5, p_tail5)
        mb.addFace(p_tail_base3, p_tail_base5, p_tail5)
        mb.addFace(p_tail_base5, p_tail_base4, p_tail4)
        mb.addFace(p_tail_base4, p_tail_base6, p_tail6)
        mb.addFace(p_tail_base6, p_tail_base3, p_tail3)

    def findPointsCenter(self, points):
        """
            Find center point among all input points.
            Input:
                points   (list) a list of one or more pywim.geom.Vertex points.
            Output: (Vector) A single vector averaging the input points.
        """
        xs = 0
        ys = 0
        zs = 0
        for p in points:
            xs += p.x
            ys += p.y
            zs += p.z
        num_p = len(points)
        return Vector(xs / num_p, ys / num_p, zs / num_p)

    def findFaceCenter(self, triangles):
        """
            Find center of face.  Return point is guaranteed to be on face.
            Inputs:
                triangles: (list) Triangles. All triangles assumed to be in same plane.
        """
        c_point = self.findPointsCenter(
            [point for tri in triangles for point in tri.points])  # List comprehension creates list of points.
        for tri in triangles:
            if LoadFace._triangleContainsPoint(tri, c_point):
                return c_point

        # When center point is not on face, choose instead center point of middle triangle.
        index = len(triangles) // 2
        tri = triangles[index]
        return self.findPointsCenter(tri.points)

    @staticmethod
    def _triangleContainsPoint(triangle, point):
        v1 = triangle.v1
        v2 = triangle.v2
        v3 = triangle.v3

        area_2 = LoadFace._threePointArea2(v1, v2, v3)
        alpha = LoadFace._threePointArea2(point, v2, v3) / area_2
        beta = LoadFace._threePointArea2(point, v3, v1) / area_2
        gamma = LoadFace._threePointArea2(point, v1, v2) / area_2

        total = alpha + beta + gamma

        return total > 0.99 and total < 1.01

    @staticmethod
    def _threePointArea2(p, q, r):
        pq = (q.x - p.x, q.y - p.y, q.z - p.z)
        pr = (r.x - p.x, r.y - p.y, r.z - p.z)

        vect = numpy.cross(pq, pr)

        # Return area X 2
        return numpy.sqrt(vect[0] ** 2 + vect[1] ** 2 + vect[2] ** 2)
