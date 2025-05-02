# NOTE: run in ipython with `%run examples/stage_viewer_widget.py`

import numpy as np
from qtpy.QtGui import QMouseEvent

from pymmcore_widgets.control._stage_explorer._stage_viewer import StageViewer

img = np.random.randint(0, 255, (256, 256), dtype=np.uint8)

stage_viewer = StageViewer()
stage_viewer.show()
stage_viewer.add_image(img)
T = np.eye(4)
T[3, :3] = 400, 250, 0  # x, y, z shift
stage_viewer.add_image(img, T.T)
stage_viewer.zoom_to_fit()


@stage_viewer.canvas.events.mouse_press.connect
def _on_mouse_press(event: QMouseEvent) -> None:
    """Handle the mouse press event."""
    canvas_pos = (event.pos[0], event.pos[1])
    last_image = list(stage_viewer._get_images())[-1]
    tform = last_image.transforms.get_transform("canvas", "scene")
    world_pos = tform.map(canvas_pos)[:2]
    print()
    print(world_pos)
