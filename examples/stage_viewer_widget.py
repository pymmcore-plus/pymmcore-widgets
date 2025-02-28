import numpy as np
from vispy import scene

from pymmcore_widgets.control._stage_explorer._stage_viewer import StageViewer

img = np.random.randint(0, 255, (256, 256))

class SV(StageViewer):
    def __init__(self):
        super().__init__()

        self.canvas.events.mouse_press.connect(self._on_mouse_press)

    def _on_mouse_press(self, event) -> None:
        """Handle the mouse press event."""
        canvas_pos = (event.pos[0], event.pos[1])
        world_pos = self._tform().map(canvas_pos)[:2]
        print()
        print(world_pos)

    def _tform(self) -> scene.transforms.BaseTransform:
        """Return the transform from canvas to scene."""
        return list(self._get_images())[-1].transforms.get_transform("canvas", "scene")

wdg = SV()
wdg.show()
