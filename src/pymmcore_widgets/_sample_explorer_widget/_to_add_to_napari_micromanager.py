# These are methods that can be added in napari-micromanager 'main_window.py'
# to pair this widget with the napari viewer.
# In these example, the 'SampleExplorer' is stored under the variable 'explorer'.


# connect mouse click callback (in __init__()) #

# self.viewer.mouse_drag_callbacks.append(self._get_event_explorer)


# new methods to add

# def _interpret_explorer_positions(
#         self, sequence: MDASequence
#     ) -> Tuple[List[int], List[str], List[str]]:
#         """Remove positions index and set layer names."""
#         labels, shape = self._get_shape_and_labels(sequence)
#         positions = [f"{p.name}_" for p in sequence.stage_positions]
#         with contextlib.suppress(ValueError):
#             p_idx = labels.index("p")
#             labels.pop(p_idx)
#             shape.pop(p_idx)

#         return shape, positions, labels

# def _add_explorer_positions_layers(
#         self, shape: Tuple[int, ...], positions: List[str], sequence: MDASequence
#     ):
#         dtype = f"uint{self._mmc.getImageBitDepth()}"

#         # create a zarr store for each channel (or all channels when not splitting)
#         # to store the images to display so we don't overflow memory.
#         for pos in positions:
#             # TODO: modify id_ to try and divede the grids when saving
#             # see also line 378 (layer.metadata["grid"])
#             id_ = pos + str(sequence.uid)

#             tmp = tempfile.TemporaryDirectory()

#             # keep track of temp files so we can clean them up when we quit
#             # we can't have them auto clean up because then the zarr wouldn't last
#             # till the end
#             # TODO: when the layer is deleted we should release the zarr store.
#             self._mda_temp_files[id_] = tmp
#             self._mda_temp_arrays[id_] = z = zarr.open(
#                 str(tmp.name), shape=shape, dtype=dtype
#             )
#             fname = self._mda_meta.file_name if self._mda_meta.should_save else "Exp"

# layer = self.viewer.add_image(
#     z, name=f"{fname}_{id_}", blending="additive"
# )

#             # add metadata to layer
#             # storing event.index in addition to channel.config because it's
#             # possible to have two of the same channel in one sequence.
#             layer.metadata["useq_sequence"] = sequence
#             layer.metadata["uid"] = sequence.uid
#             layer.metadata["grid"] = pos.split("_")[-3]
#             layer.metadata["grid_pos"] = pos.split("_")[-2]

# def _get_defaultdict_layers(self, event):
#         layergroups = defaultdict(set)
#         for lay in self.viewer.layers:
#             if lay.metadata.get("uid") == event.sequence.uid:
#                 key = lay.metadata.get("grid")[:8]
#                 layergroups[key].add(lay)
#         return layergroups

# def _get_event_explorer(self, viewer, event):

#     if not self.explorer.isVisible():
#         return

#     if layer := self.viewer.layers.selection.active:
#         if not layer.metadata.get("translate"):
#             self.explorer.x_lineEdit.setText("None")
#             self.explorer.y_lineEdit.setText("None")
#             return
#     else:
#         self.explorer.x_lineEdit.setText("None")
#         self.explorer.y_lineEdit.setText("None")
#         return

#     if self._mmc.getPixelSizeUm() > 0:
#         width = self._mmc.getROI(self._mmc.getCameraDevice())[2]
#         height = self._mmc.getROI(self._mmc.getCameraDevice())[3]

#         x = viewer.cursor.position[-1] * self._mmc.getPixelSizeUm()
#         y = viewer.cursor.position[-2] * self._mmc.getPixelSizeUm() * (-1)

#         # to match position coordinates with center of the image
#         x = f"{x - ((width / 2) * self._mmc.getPixelSizeUm()):.1f}"
#         y = f"{y - ((height / 2) * self._mmc.getPixelSizeUm() * (-1)):.1f}"

#     else:
#         x, y = "None", "None"

#     self.explorer.x_lineEdit.setText(x)
#     self.explorer.y_lineEdit.setText(y)


# to add in "_on_mda_started()"

# elif self._mda_meta.mode == "explorer":

#     if self._mda_meta.translate_explorer:

#         shape, positions, labels = self._interpret_explorer_positions(sequence)

#         self._add_explorer_positions_layers(tuple(shape), positions, sequence)

#     else:

#         shape, channels, labels = self._interpret_split_channels(sequence)

#         self._add_mda_channel_layers(tuple(shape), channels, sequence)


# to add in "_on_mda_frame"

# elif meta.mode == "explorer":

#     if meta.translate_explorer:

#         with contextlib.suppress(ValueError):
#             axis_order.remove("p")

#         # get the actual index of this image into the array
#         # add it to the zarr store
#         im_idx = tuple(event.index[k] for k in axis_order)
#         pos_name = event.pos_name
#         layer_name = f"{pos_name}_{event.sequence.uid}"
#         self._mda_temp_arrays[layer_name][im_idx] = image

#         # translate layer depending on stage position
#         if meta.translate_explorer_real_coords:
#             x = event.x_pos / self.explorer.pixel_size
#             y = event.y_pos / self.explorer.pixel_size * (-1)
#         else:
#             x = meta.explorer_translation_points[event.index["p"]][0]
#             y = -meta.explorer_translation_points[event.index["p"]][1]

#         layergroups = self._get_defaultdict_layers(event)
#         # unlink layers to translate
#         for group in layergroups.values():
#             unlink_layers(group)

#         # translate only once
#         fname = (
#             self._mda_meta.file_name if self._mda_meta.should_save else "Exp"
#         )
#         layer = self.viewer.layers[f"{fname}_{layer_name}"]
#         if (layer.translate[-2], layer.translate[-1]) != (y, x):
#             layer.translate = (y, x)
#         layer.metadata["translate"] = True

#         # link layers after translation
#         for group in layergroups.values():
#             link_layers(group)

#         # move the viewer step to the most recently added image
#         for a, v in enumerate(im_idx):
#             self.viewer.dims.set_point(a, v)

#         layer.reset_contrast_limits()

#         # TODO: fix zoom and reset view. on s15 it doesnt work
#         # when dysplay with stage coords
#         zoom_out_factor = (
#             self.explorer.scan_size_r
#             if self.explorer.scan_size_r >= self.explorer.scan_size_c
#             else self.explorer.scan_size_c
#         )
#         self.viewer.camera.zoom = 1 / zoom_out_factor
#         self.viewer.reset_view()


# to add in "_on_mda_finished" before pop meta

# seq_uid = sequence.uid
# if meta.mode == "explorer":
#     layergroups = defaultdict(set)
#     for lay in self.viewer.layers:
#         if lay.metadata.get("uid") == seq_uid:
#             key = f"{lay.metadata['ch_name']}_idx{lay.metadata['ch_id']}"
#             layergroups[key].add(lay)
#     for group in layergroups.values():
#         link_layers(group)
