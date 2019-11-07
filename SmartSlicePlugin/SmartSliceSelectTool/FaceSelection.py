# Facet.py
# Teton Simulation
# Authored on   November 1, 2019
# Last Modified November 1, 2019

#
# Contains definitions for Cura Smart Slice Selectable Faces
#


#  STANDARD IMPORTS
import sys
sys.path.append('/usr/lib/python3/CGAL') # Temporary

#  CGAL Imports
import CGAL
from CGAL.CGAL_Kernel import Point_3, Vector_3

#  Ultimaker/Cura Imports
from UM.Math import NumPyUtil



''' 
  SelectableFace(points, normals)
    'points' is a list of Point_3(x, y, z)
    'normals' is an 'immutableNDArray' containing (x, y, z) components for point normal vectors

    Contains definition for a selectable face with normal vector
    
    NOTE:  'normals' is passed through for Cura  (UNUSED)
           'normals' will likely be used by CGAL (NOT DEPRECATED!!)
'''
class SelectableFace:
#  CONSTRUCTOR
    def __init__(self, points, normals):
        self._points = points
        self._edges = self.generateEdges()
        self._normal = self.generateNormalVector()

        self._vert_normals = normals
        self._selected = False


#  ACCESSORS

    '''
      points()
        Returns list of Selectable Points
    '''
    @property
    def points(self):
        return self._points

    '''
      edges()
        Returns list of Selectable Edges
    '''
    @property
    def edges(self):
        return self._edges

    '''
      normal()
        Returns the FaceWithNormal's Normal Vector_3
    '''
    @property
    def normal(self):
        return self._normal

    '''  selected()
        Returns true if face is selected
                false otherwise
    '''
    @property
    def selected(self):
        return self._selected

    '''
      getPoint(i)
        Returns the PointWithNormal at index: i
    '''
    def getPoint(self, i):
        return self._points[i]

    ''' 
      printDetails()
        Gives a printout of meaningful properties regarding SelectableFace
    '''
    def printDetails(self):
        print ("# of Points:  " + str(len(self._points)))
        for p in self._points:
            print ("Point: (" + str(p.x()) + ", " + str(p.y()) + ", " + str(p.z()) + ")")
        print ("\n")


#  MUTATORS

    '''
      addPoint()
        If there is no conflict, adds PointWithNormal to FaceWithNormal
    '''
    def addPoint(self, point):
        self._points.append(point)

    '''
      select()
        Sets SelectableFace Selection status to True
    '''
    def select(self):
        self._selected = True

    '''
      deselect()
        Sets SelectableFace Selection status to False
    '''
    def deselect(self):
        self._selected = False

    '''
      addTri()
        Adds triangle to SelectableFace
    '''
    def addTri(self, tri):
        #  Add Points to Face if Necessary
        for p in tri.points:
            _add = True
            for q in self._points:
                #  If Vertex is already in face...
                if ((p.x() == q.x()) and (p.y() == q.y()) and (p.z() == q.z())):
                    _add = False
            if (_add):
                #  Add Point and Associated Edges to Face
                self.addPoint(p)
                for p2 in tri.points:
                    if (p != p2):
                        self.addEdge(p, p2)
        
  

    '''
      generatedEdges()
        Sets Facet edges to be the outline of the shape
    '''
    def generateEdges(self):
        #  ASSUMES STARTING FACET IS TRIANGLE FOR NOW
        edges = [SelectableEdge(self._points[0], self._points[1])]
        edges.append(SelectableEdge(self._points[1], self._points[2]))
        edges.append(SelectableEdge(self._points[2], self._points[0]))
        return edges

    def addEdge(self, p1, p2):
        self._edges.append(SelectableEdge(p1, p2))

    '''
      removeEdge(edge)
        If 'edge' is in the SelectableFace, remove it
    '''
    def removeEdge(self, edge):
        for e in self._edges:
            if ((edge.p1 == e.p1 and edge.p2 == e.p2) or (edge.p1 == e.p2 and edge.p2 == e.p1)):
                self._edges.remove(e)

    '''
      generateNormalVector()
        Returns the cross product of the first three points within the Face

        This makes the assumption that all other points beyond p3 are COPLANAR
    '''
    def generateNormalVector(self):
        vec1 = Vector_3(self._points[1].x() - self._points[0].x(), self._points[1].y() - self._points[0].y(), self._points[1].z() - self._points[0].z())
        vec2 = Vector_3(self._points[2].x() - self._points[0].x(), self._points[2].y() - self._points[0].y(), self._points[2].z() - self._points[0].z())
        cross_x = vec1.y()*vec2.z() - vec1.z()*vec2.y()
        cross_y = vec1.z()*vec2.x() - vec1.x()*vec2.z()
        cross_z = vec1.x()*vec2.y() - vec1.y()*vec2.x()
        cross   = (cross_x*cross_x) + (cross_y*cross_y) + (cross_z*cross_z)
        self._normal = Vector_3(cross_x/cross, cross_y/cross, cross_z/cross)



'''
  SelectableEdge(p1, p2)
    'p1' and 'p2' are 'SelectablePoint'

    Edges denote lines between two vertices in 3D space
'''
class SelectableEdge:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        
        self._selected = False


'''
  SelectablePoint(x, y, z, normals)
    'x', 'y', and 'z' are floating point coordinates
    'normals' is an immutableNDArray containing normal vectors for each vertex

    NOTE:  'normals' is passed through for Cura  (UNUSED)
           'normals' will likely be used by CGAL (NOT DEPRECATED!!)
'''
class SelectablePoint:
#  CONSTRUCTORS
    def __init__(self, x, y, z, normals):
        self._p = Point_3(x, y, z)
        self._normals = normals

        self._selected = False
        

#  ACCESSORS

    '''
      x()
        Returns value of SelectablePoint x coordinate component
    '''
    @property
    def x(self):
        return self._p.x()

    '''
      y()
        Returns value of SelectablePoint y coordinate component
    '''
    @property
    def y(self):
        return self._p.y()

    '''
      z()
        Returns value of SelectablePoint z coordinate component
    '''
    @property
    def z(self):
        return self._p.z()


#  MUTATORS 

    '''
      x(new_x)
        'new_x' is a floating point value

        Sets SelectablePoint x coordinate component to 'new_x'
    '''
    @x.setter
    def x(self, new_x):
        self._p.x(new_x)

    '''
      y(new_y)
        'new_y' is a floating point value

        Sets SelectablePoint x coordinate component to 'new_y'
    '''
    @y.setter
    def y(self, new_y):
        self._p.y(new_y)

    '''
      z(new_z)
        'new_z' is a floating point value

        Sets SelectablePoint x coordinate component to 'new_z'
    '''
    @z.setter
    def z(self, new_z):
        self._p.z(new_z)



