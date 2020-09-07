from typing import Optional, Dict

from UM.Scene.SceneNodeDecorator import SceneNodeDecorator

class SmartSliceAddedDecorator(SceneNodeDecorator):
    def __init__(self, node: Optional["SceneNode"] = None):
        super().__init__(node)

    def __deepcopy__(self, memo: Dict[int, object]) -> "SmartSliceAddedDecorator":
        return SmartSliceAddedDecorator()

class SmartSliceRemovedDecorator(SceneNodeDecorator):
    def __init__(self, node: Optional["SceneNode"] = None):
        super().__init__(node)

    def __deepcopy__(self, memo: Dict[int, object]) -> "SmartSliceRemovedDecorator":
        return SmartSliceRemovedDecorator()