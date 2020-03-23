import numpy

#  UM/Cura Imports
from UM.Logger import Logger
from UM.Scene.ToolHandle import ToolHandle
from UM.Scene.Selection import Selection
from UM.Mesh.MeshBuilder import MeshBuilder

from UM.Math.Color import Color
from UM.Math.Vector import Vector

# Provides enums
class SelectionMode:
    AnchorMode = 1
    LoadMode = 2

class SmartSliceSelectHandle(ToolHandle):
    def __init__(self, extension, tool):
        super().__init__(parent=None)

        self._name = "SmartSliceSelectHandle"
        self._tool = tool
        self._connector = extension.cloud # SmartSliceCloudConnector
        self._selected_color = Color(0, 0, 255, 255)

        #  Selected Face Properties
        self._tri = None

        #   Arrow Mesh
        self._arrow = False
        self._arrow_head_length = 8
        self._arrow_tail_length = 22
        self._arrow_total_length = self._arrow_head_length + self._arrow_tail_length
        self._arrow_head_width = 2.8
        self._arrow_tail_width = 0.8

        #  Disable auto scale (see ToolHandle for details)
        self._auto_scale = False

    # Override ToolHandle._onSelectionCenterChanged so that we can set the full transformation
    def _onSelectionCenterChanged(self) -> None:
        if self._enabled:
            obj = Selection.getSelectedObject(0) # which index to use?
            if obj:
                self.setTransformation(obj.getLocalTransformation())

    @property
    def face(self):
        return self._tri

    def setFace(self, f):
        self._tri = f

    def drawSelection(self, mode, tri=None):
        """
        Use UM's MeshBuilder to construct 3D Arrow mesh and translates/rotates as to be normal to the selected face
        """
        # If a tri was supplied reset the stored tri
        if tri:
            self._tri = tri

        if self._tri is None:
            return

        #  Construct Edges using MeshBuilder Cubes
        mb = MeshBuilder()

        for tri in self._tri:
            mb.addFace(tri.v1, tri.v2, tri.v3, color=self._selected_color)

        if mode == SelectionMode.LoadMode:
            self.paintArrow(self._tri, mb)

        #  Add to Cura Scene
        self.setSolidMesh(mb.build())


    def paintArrow(self, face_list, mb):
        """
        Draw an arrow to the normal of the given face mesh using MeshBuilder.addFace().
        Inputs:
            face_list (list of faces or triangles) Only one face will be used to begin arrow.
            mb (MeshBuilder) which is drawn onto.
        """
        if len(face_list) <= 0: # input list is empty
            return
        index = len(face_list) // 2
        tri = face_list[index]
        #p = tri.points
        #tri.generateNormalVector()
        n = tri.normal
        n = Vector(n.r, n.s, n.t) # pywim Vector to UM Vector
        invert_arrow = self._tool.force.pull
        center = self.findFaceCenter(face_list)

        p_base0 = Vector(center.x + n.x * self._arrow_head_length,
                         center.y + n.y * self._arrow_head_length,
                         center.z + n.z * self._arrow_head_length)
        p_tail0 = Vector(center.x + n.x * self._arrow_total_length,
                         center.y + n.y * self._arrow_total_length,
                         center.z + n.z * self._arrow_total_length)

        if invert_arrow:
            p_base0 = Vector(center.x + n.x * self._arrow_tail_length,
                             center.y + n.y * self._arrow_tail_length,
                             center.z + n.z * self._arrow_tail_length)
            p_head = p_tail0
            p_tail0 = center
        else:   # regular
            p_head = center

        p_base1 = Vector(p_base0.x, p_base0.y + self._arrow_head_width, p_base0.z)
        p_base2 = Vector(p_base0.x, p_base0.y - self._arrow_head_width, p_base0.z)
        p_base3 = Vector(p_base0.x + self._arrow_head_width, p_base0.y, p_base0.z)
        p_base4 = Vector(p_base0.x - self._arrow_head_width, p_base0.y, p_base0.z)
        p_base5 = Vector(p_base0.x, p_base0.y, p_base0.z + self._arrow_head_width)
        p_base6 = Vector(p_base0.x, p_base0.y, p_base0.z - self._arrow_head_width)

        mb.addFace(p_base1, p_head, p_base3, color=self.YAxisSelectionColor)
        mb.addFace(p_base3, p_head, p_base2, color=self.YAxisSelectionColor)
        mb.addFace(p_base2, p_head, p_base4, color=self.YAxisSelectionColor)
        mb.addFace(p_base4, p_head, p_base1, color=self.YAxisSelectionColor)
        mb.addFace(p_base5, p_head, p_base1, color=self.YAxisSelectionColor)
        mb.addFace(p_base6, p_head, p_base1, color=self.YAxisSelectionColor)
        mb.addFace(p_base6, p_head, p_base2, color=self.YAxisSelectionColor)
        mb.addFace(p_base2, p_head, p_base5, color=self.YAxisSelectionColor)
        mb.addFace(p_base3, p_head, p_base5, color=self.YAxisSelectionColor)
        mb.addFace(p_base5, p_head, p_base4, color=self.YAxisSelectionColor)
        mb.addFace(p_base4, p_head, p_base6, color=self.YAxisSelectionColor)
        mb.addFace(p_base6, p_head, p_base3, color=self.YAxisSelectionColor)

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

        mb.addFace(p_tail1, p_tail_base1, p_tail3, color=self.YAxisSelectionColor)
        mb.addFace(p_tail3, p_tail_base3, p_tail2, color=self.YAxisSelectionColor)
        mb.addFace(p_tail2, p_tail_base2, p_tail4, color=self.YAxisSelectionColor)
        mb.addFace(p_tail4, p_tail_base4, p_tail1, color=self.YAxisSelectionColor)
        mb.addFace(p_tail5, p_tail_base5, p_tail1, color=self.YAxisSelectionColor)
        mb.addFace(p_tail6, p_tail_base6, p_tail1, color=self.YAxisSelectionColor)
        mb.addFace(p_tail6, p_tail_base6, p_tail2, color=self.YAxisSelectionColor)
        mb.addFace(p_tail2, p_tail_base2, p_tail5, color=self.YAxisSelectionColor)
        mb.addFace(p_tail3, p_tail_base3, p_tail5, color=self.YAxisSelectionColor)
        mb.addFace(p_tail5, p_tail_base5, p_tail4, color=self.YAxisSelectionColor)
        mb.addFace(p_tail4, p_tail_base4, p_tail6, color=self.YAxisSelectionColor)
        mb.addFace(p_tail6, p_tail_base6, p_tail3, color=self.YAxisSelectionColor)

        mb.addFace(p_tail_base1, p_tail_base3, p_tail3, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base3, p_tail_base2, p_tail2, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base2, p_tail_base4, p_tail4, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base4, p_tail_base1, p_tail1, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base5, p_tail_base1, p_tail1, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base6, p_tail_base1, p_tail1, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base6, p_tail_base2, p_tail2, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base2, p_tail_base5, p_tail5, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base3, p_tail_base5, p_tail5, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base5, p_tail_base4, p_tail4, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base4, p_tail_base6, p_tail6, color=self.YAxisSelectionColor)
        mb.addFace(p_tail_base6, p_tail_base3, p_tail3, color=self.YAxisSelectionColor)

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
        c_point = self.findPointsCenter([point for tri in triangles for point in tri.points]) # List comprehension creates list of points.
        for tri in triangles:
            if SmartSliceSelectHandle._triangleContainsPoint(tri, c_point):
                return c_point

        # When center point is not on face, choose instead center point of middle triangle.
        index = len(triangles) // 2
        tri = triangles[index]
        return self.findPointsCenter(tri.points)

    def clearSelection(self):
        self.setSolidMesh(MeshBuilder().build())

    @staticmethod
    def _triangleContainsPoint(triangle, point):
        v1 = triangle.v1
        v2 = triangle.v2
        v3 = triangle.v3

        area_2 = SmartSliceSelectHandle._threePointArea2(v1, v2, v3)
        alpha = SmartSliceSelectHandle._threePointArea2(point, v2, v3) / area_2
        beta = SmartSliceSelectHandle._threePointArea2(point, v3, v1) / area_2
        gamma = SmartSliceSelectHandle._threePointArea2(point, v1, v2) / area_2

        total = alpha + beta + gamma

        return total > 0.99 and total < 1.01

    @staticmethod
    def _threePointArea2(p, q, r):
        pq = (q.x - p.x, q.y - p.y, q.z - p.z)
        pr = (r.x - p.x, r.y - p.y, r.z - p.z)

        vect = numpy.cross(pq, pr)

        # Return area X 2
        return numpy.sqrt(vect[0]**2 + vect[1]**2 + vect[2]**2)
