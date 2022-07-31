# These are methods that can be added in napari-micromanager 'main_window.py'
# to pair the camera roi functions with a napari layer.
# In these example, the 'CameraRoiWidget' is stored under the variable 'cam_wdg'.


# connect events (in __init__())
# self.viewer.mouse_drag_callbacks.append(self._update_cam_roi_layer)
# self.tab_wdg.cam_wdg.roiInfo.connect(self._on_roi_info)
# self.tab_wdg.cam_wdg.crop_btn.clicked.connect(self._on_crop_btn)

# for napari layers
# def _get_roi_layer(self) -> napari.layers.shapes.shapes.Shapes:
#         for layer in self.viewer.layers:
#             if layer.metadata.get("layer_id"):
#                 return layer

# def _on_roi_info(
#         self, start_x: int, start_y: int, width: int, height: int, mode: str = ""
#     ) -> None:

#         if mode == "Full":
#             self._on_crop_btn()
#             return

#         try:
#             cam_roi_layer = self._get_roi_layer()
#             cam_roi_layer.data = self._set_cam_roi_shape(
#                 start_x, start_y, width, height
#             )
#         except AttributeError:
#             cam_roi_layer = self.viewer.add_shapes(name="set_cam_ROI")
#             cam_roi_layer.metadata["layer_id"] = "set_cam_ROI"
#             cam_roi_layer.data = self._set_cam_roi_shape(
#                 start_x, start_y, width, height
#             )

#         cam_roi_layer.mode = "select"
#         self.viewer.reset_view()

#     def _set_cam_roi_shape(
#         self, start_x: int, start_y: int, width: int, height: int
#     ) -> List[list]:
#         return [
#             [start_y, start_x],
#             [start_y, width + start_x],
#             [height + start_y, width + start_x],
#             [height + start_y, start_x],
#         ]

#     def _on_crop_btn(self):
#         with contextlib.suppress(Exception):
#             cam_roi_layer = self._get_roi_layer()
#             self.viewer.layers.remove(cam_roi_layer)
#         self.viewer.reset_view()

#     def _update_cam_roi_layer(self, layer, event) -> None:  # type: ignore

#         active_layer = self.viewer.layers.selection.active
#         if not isinstance(active_layer, napari.layers.shapes.shapes.Shapes):
#             return

#         if active_layer.metadata.get("layer_id") != "set_cam_ROI":
#             return

#         # on mouse pressed
#         dragged = False
#         yield
#         # on mouse move
#         while event.type == "mouse_move":
#             dragged = True
#             yield
#         # on mouse release
#         if dragged:
#             if not active_layer.data:
#                 return
#             data = active_layer.data[-1]

#             x_max = self.tab_wdg.cam_wdg.chip_size_x
#             y_max = self.tab_wdg.cam_wdg.chip_size_y

#             x = round(data[0][1])
#             y = round(data[0][0])
#             width = round(data[1][1] - x)
#             height = round(data[2][0] - y)

#             # change shape if out of cam area
#             if x + width >= x_max:
#                 x = x - ((x + width) - x_max)
#             if y + height >= y_max:
#                 y = y - ((y + height) - y_max)

#             cam = self._mmc.getCameraDevice()
#             self._mmc.events.camRoiSet.emit(cam, x, y, width, height)
