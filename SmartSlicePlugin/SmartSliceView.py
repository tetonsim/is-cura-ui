from UM.View.View import View
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Resources import Resources
from UM.Math.Color import Color
from UM.View.GL.OpenGL import OpenGL
from UM.Scene.Platform import Platform

from cura.BuildVolume import BuildVolume
from cura.Scene.ConvexHullNode import ConvexHullNode

import math

class SmartSliceView(View):
    def __init__(self):
        super().__init__()
        self._shader = None

    def _checkSetup(self):
        if not self._shader:
            self._shader = OpenGL.getInstance().createShaderProgram(Resources.getPath(Resources.Shaders, "overhang.shader"))
            #self._shader.setUniformValue("u_ambientColor", Color(69, 129, 209, 1))
            self._shader.setUniformValue("u_overhangAngle", math.cos(math.radians(0)))
            self._shader.setUniformValue("u_faceId", -1)
            self._shader.setUniformValue("u_renderError", 0)

    def beginRendering(self):
        scene = self.getController().getScene()
        renderer = self.getRenderer()

        self._checkSetup()

        for node in DepthFirstIterator(scene.getRoot()):
            if isinstance(node, (BuildVolume, ConvexHullNode, Platform)):
                continue

            if not node.render(renderer):
                if node.getMeshData() and node.isVisible() and not node.callDecoration("getLayerData"):
                    uniforms = {}

                    per_mesh_stack = node.callDecoration("getStack")

                    if node.callDecoration("isNonPrintingMesh"):
                        pass
                    #elif getattr(node, "_outside_buildarea", False):
                    #    pass
                    elif per_mesh_stack and per_mesh_stack.getProperty("support_mesh", "value"):
                        pass
                    else:
                        renderer.queueNode(node, shader = self._shader, uniforms = uniforms)

                #if node.callDecoration("isGroup") and Selection.isSelected(node):
                #    renderer.queueNode(scene.getRoot(), mesh = node.getBoundingBoxMesh(), mode = RenderBatch.RenderMode.LineLoop)

    def endRendering(self):
        pass
