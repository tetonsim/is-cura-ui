from UM.Math.Vector import Vector
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Scene.ToolHandle import ToolHandle

from .LoadToolHandle import LoadToolHandle

class LoadRotator(LoadToolHandle):
    """Provides the circular toolhandle and arrow for the load direction"""

    def __init__(self, parent = None):
        super().__init__(parent)

        self._name = "LoadRotator"

        self.rotation_axis = Vector.Unit_Z

    @property
    def center(self) -> Vector:
        return self.getPosition()

    def buildMesh(self):
        super().buildMesh()

        mb = MeshBuilder()

        #SOLIDMESH
        mb.addDonut(
            inner_radius = LoadToolHandle.INNER_RADIUS,
            outer_radius = LoadToolHandle.OUTER_RADIUS,
            width = LoadToolHandle.LINE_WIDTH,
            axis = self.rotation_axis,
            color = self._y_axis_color
        )

        self.setSolidMesh(mb.build())

        mb = MeshBuilder()

        #SELECTIONMESH
        mb.addDonut(
            inner_radius = LoadToolHandle.ACTIVE_INNER_RADIUS,
            outer_radius = LoadToolHandle.ACTIVE_OUTER_RADIUS,
            width = LoadToolHandle.ACTIVE_LINE_WIDTH,
            axis = self.rotation_axis,
            color = ToolHandle.YAxisSelectionColor
        )

        self.setSelectionMesh(mb.build())

