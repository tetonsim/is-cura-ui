
from UM.Mesh.MeshData import MeshData
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from cura.CuraApplication import CuraApplication
from cura.Settings.ExtruderStack import ExtruderStack
from UM.Scene.SceneNode import SceneNode

def makeInteractiveMesh(mesh_data : MeshData) -> 'pywim.geom.tri.Mesh':
    import pywim

    int_mesh = pywim.geom.tri.Mesh()

    verts = mesh_data.getVertices()

    for i in range(mesh_data.getVertexCount()):
        int_mesh.add_vertex(i, verts[i][0], verts[i][1], verts[i][2])

    faces = mesh_data.getIndices()

    if faces is not None:
        for i in range(mesh_data.getFaceCount()):
            v1 = int_mesh.vertices[faces[i][0]]
            v2 = int_mesh.vertices[faces[i][1]]
            v3 = int_mesh.vertices[faces[i][2]]

            int_mesh.add_triangle(i, v1, v2, v3)
    else:
        for i in range(0, len(int_mesh.vertices), 3):
            v1 = int_mesh.vertices[i]
            v2 = int_mesh.vertices[i+1]
            v3 = int_mesh.vertices[i+2]

            int_mesh.add_triangle(i // 3, v1, v2, v3)

    # Cura keeps around degenerate triangles, so we need to as well
    # so we don't end up with a mismatch in triangle ids
    int_mesh.analyze_mesh(remove_degenerate_triangles=False)

    return int_mesh

def getNodes(func):
    scene = CuraApplication.getInstance().getController().getScene()
    root = scene.getRoot()

    nodes = []

    for node in DepthFirstIterator(root):
        isSliceable = node.callDecoration("isSliceable")
        isPrinting = not node.callDecoration("isNonPrintingMesh")
        isSupport = False
        isInfillMesh = False

        stack = node.callDecoration("getStack")

        if stack:
            isSupport = stack.getProperty("support_mesh", "value")
            isInfillMesh = stack.getProperty("infill_mesh", "value")

        if func(isSliceable, isPrinting, isSupport, isInfillMesh):
            nodes.append(node)

    return nodes

def getPrintableNodes():
    return getNodes(
        lambda isSliceable, isPrinting, isSupport, isInfillMesh: \
            isSliceable and isPrinting and not isSupport and not isInfillMesh
    )

def getModifierMeshes():
    return getNodes(
        lambda isSliceable, isPrinting, isSupport, isInfillMesh: \
            isSliceable and not isPrinting and not isSupport and isInfillMesh
    )

def getNodeActiveExtruder(node : SceneNode) -> ExtruderStack:
    active_extruder_position = node.callDecoration("getActiveExtruderPosition")
    if active_extruder_position is None:
        active_extruder_position = 0
    else:
        active_extruder_position = int(active_extruder_position)

    # Only use the extruder that is active on our mesh_node
    # The back end only supports a single extruder, currently.
    # Ignore any extruder that is not the active extruder.
    machine_extruders = list(filter(
        lambda extruder: extruder.position == active_extruder_position,
        CuraApplication.getInstance().getMachineManager().activeMachine.extruderList
    ))

    if len(machine_extruders) > 0:
        return machine_extruders[0]

    return None
