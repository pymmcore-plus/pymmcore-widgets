from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, Callable, cast

import numpy as np
from superqt.utils import qthrottled
from vispy import scene

if TYPE_CHECKING:
    import cmap
    from qtpy.QtWidgets import QWidget
    from vispy.scene.events import SceneMouseEvent


class VispyImageHandle:
    def __init__(self, image: scene.visuals.Image) -> None:
        self._image = image

    @property
    def data(self) -> np.ndarray:
        return self._image._data  # type: ignore

    @data.setter
    def data(self, data: np.ndarray) -> None:
        self._image.set_data(data)

    @property
    def visible(self) -> bool:
        return bool(self._image.visible)

    @visible.setter
    def visible(self, visible: bool) -> None:
        self._image.visible = visible

    @property
    def clim(self) -> Any:
        return self._image.clim

    @clim.setter
    def clim(self, clims: tuple[float, float]) -> None:
        with suppress(ZeroDivisionError):
            self._image.clim = clims

    @property
    def cmap(self) -> cmap.Colormap:
        return self._cmap

    @cmap.setter
    def cmap(self, cmap: cmap.Colormap) -> None:
        self._cmap = cmap
        self._image.cmap = cmap.to_vispy()

    @property
    def transform(self) -> np.ndarray:
        raise NotImplementedError

    @transform.setter
    def transform(self, transform: np.ndarray) -> None:
        raise NotImplementedError

    def remove(self) -> None:
        self._image.parent = None


class VispyViewerCanvas:
    """Vispy-based viewer for data.

    All vispy-specific code is encapsulated in this class (and non-vispy canvases
    could be swapped in if needed as long as they implement the same interface).
    """

    def __init__(self, set_info: Callable[[str], None]) -> None:
        self._set_info = set_info
        self._canvas = scene.SceneCanvas()
        self._canvas.events.mouse_move.connect(qthrottled(self._on_mouse_move, 60))
        self._camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))
        self._has_set_range = False

        central_wdg: scene.Widget = self._canvas.central_widget
        self._view: scene.ViewBox = central_wdg.add_view(camera=self._camera)

    def qwidget(self) -> QWidget:
        return cast("QWidget", self._canvas.native)

    def refresh(self) -> None:
        self._canvas.update()

    def add_image(
        self, data: np.ndarray | None = None, cmap: cmap.Colormap | None = None
    ) -> VispyImageHandle:
        """Add a new Image node to the scene."""
        img = scene.visuals.Image(data, parent=self._view.scene)
        img.set_gl_state("additive", depth_test=False)
        img.interactive = True
        if not self._has_set_range:
            self.set_range()
            self._has_set_range = True
        handle = VispyImageHandle(img)
        if cmap is not None:
            handle.cmap = cmap
        return handle

    def set_range(
        self,
        x: tuple[float, float] | None = None,
        y: tuple[float, float] | None = None,
        margin: float = 0.01,
    ) -> None:
        """Update the range of the PanZoomCamera.

        When called with no arguments, the range is set to the full extent of the data.
        """
        self._camera.set_range(x=x, y=y, margin=margin)

    def _on_mouse_move(self, event: SceneMouseEvent) -> None:
        """Mouse moved on the canvas, display the pixel value and position."""
        images = []
        # Get the images the mouse is over
        # FIXME: must be a better way to do this
        seen = set()
        try:
            while visual := self._canvas.visual_at(event.pos):
                if isinstance(visual, scene.visuals.Image):
                    images.append(visual)
                visual.interactive = False
                seen.add(visual)
        except Exception:
            return
        for visual in seen:
            visual.interactive = True
        if not images:
            return

        tform = images[0].get_transform("canvas", "visual")
        px, py, *_ = (int(x) for x in tform.map(event.pos))
        text = f"[{py}, {px}]"
        for c, img in enumerate(reversed(images)):
            with suppress(IndexError):
                value = img._data[py, px]
                if isinstance(value, (np.floating, float)):
                    value = f"{value:.2f}"
                text += f" {c}: {value}"
        self._set_info(text)
