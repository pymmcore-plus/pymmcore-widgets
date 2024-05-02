from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

import pygfx
import pygfx.geometries
import pygfx.materials
from wgpu.gui.qt import QWgpuCanvas

if TYPE_CHECKING:
    import cmap
    import numpy as np
    from qtpy.QtWidgets import QWidget


class PyGFXImageHandle:
    def __init__(self, image: pygfx.Image) -> None:
        self._image = image
        self._geom = cast("pygfx.geometries.Geometry", image.geometry.grid)
        self._material = cast("pygfx.materials.ImageBasicMaterial", image.material)

    @property
    def data(self) -> np.ndarray:
        return self._geom._data  # type: ignore

    @data.setter
    def data(self, data: np.ndarray) -> None:
        self._geom.grid = pygfx.Texture(data, dim=2)

    @property
    def visible(self) -> bool:
        return bool(self._image.visible)

    @visible.setter
    def visible(self, visible: bool) -> None:
        self._image.visible = visible

    @property
    def clim(self) -> Any:
        return self._material.clim

    @clim.setter
    def clim(self, clims: tuple[float, float]) -> None:
        self._material.clim = clims

    @property
    def cmap(self) -> cmap.Colormap:
        return self._cmap

    @cmap.setter
    def cmap(self, cmap: cmap.Colormap) -> None:
        self._cmap = cmap
        self._material.map = cmap.to_pygfx()

    def remove(self) -> None:
        if (par := self._image.parent) is not None:
            par.remove(self._image)


class PyGFXViewerCanvas:
    """Vispy-based viewer for data.

    All vispy-specific code is encapsulated in this class (and non-vispy canvases
    could be swapped in if needed as long as they implement the same interface).
    """

    def __init__(self, set_info: Callable[[str], None]) -> None:
        self._set_info = set_info

        self._canvas = QWgpuCanvas(size=(512, 512))
        self._renderer = pygfx.renderers.WgpuRenderer(self._canvas)
        self._scene = pygfx.Scene()
        self._camera = cam = pygfx.OrthographicCamera(512, 512)

        cam.local.position = (256, 256, 0)
        cam.local.scale_y = -1
        controller = pygfx.PanZoomController(cam, register_events=self._renderer)
        # increase zoom wheel gain
        controller.controls.update({"wheel": ("zoom_to_point", "push", -0.005)})

    def qwidget(self) -> QWidget:
        return self._canvas

    def refresh(self) -> None:
        self._canvas.update()
        self._canvas.request_draw(self._animate)

    def _animate(self) -> None:
        print("animate")
        self._renderer.render(self._scene, self._camera)

    def add_image(
        self, data: np.ndarray | None = None, cmap: cmap.Colormap | None = None
    ) -> PyGFXImageHandle:
        """Add a new Image node to the scene."""
        image = pygfx.Image(
            pygfx.Geometry(grid=pygfx.Texture(data, dim=2)),
            pygfx.ImageBasicMaterial(),
        )
        self._scene.add(image)
        handle = PyGFXImageHandle(image)
        if cmap is not None:
            handle.cmap = cmap
        return handle

    def set_range(
        self,
        x: tuple[float, float] | None = None,
        y: tuple[float, float] | None = None,
        margin: float | None = 0.05,
    ) -> None:
        """Update the range of the PanZoomCamera.

        When called with no arguments, the range is set to the full extent of the data.
        """
        # self._camera.set_range(x=x, y=y, margin=margin)

    # def _on_mouse_move(self, event: SceneMouseEvent) -> None:
    #     """Mouse moved on the canvas, display the pixel value and position."""
    #     images = []
    #     # Get the images the mouse is over
    #     seen = set()
    #     while visual := self._canvas.visual_at(event.pos):
    #         if isinstance(visual, scene.visuals.Image):
    #             images.append(visual)
    #         visual.interactive = False
    #         seen.add(visual)
    #     for visual in seen:
    #         visual.interactive = True
    #     if not images:
    #         return

    #     tform = images[0].get_transform("canvas", "visual")
    #     px, py, *_ = (int(x) for x in tform.map(event.pos))
    #     text = f"[{py}, {px}]"
    #     for c, img in enumerate(images):
    #         with suppress(IndexError):
    #             text += f" c{c}: {img._data[py, px]}"
    #     self._set_info(text)
