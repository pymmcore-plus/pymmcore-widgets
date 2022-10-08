# These are methods that can be added in napari-micromanager 'main_window.py'
# to pair this widget with the napari viewer.


# new methods to add

# def _interpret_hcs_positions(
#         self, sequence: MDASequence
#     ) -> Tuple[List[int], List[str], List[str]]:
#         """Get positions, labels and shape for the zarr array."""
#         labels, shape = self._get_shape_and_labels(sequence)

#         positions = []
#         first_pos_name = sequence.stage_positions[0].name.split("_")[0]
#         self.multi_pos = 0
#         for p in sequence.stage_positions:
#             p_name = p.name.split("_")[0]
#             if f"{p_name}_" not in positions:
#                 positions.append(f"{p_name}_")
#             elif p.name.split("_")[0] == first_pos_name:
#                 self.multi_pos += 1

#         p_idx = labels.index("p")
#         if self.multi_pos == 0:
#             shape.pop(p_idx)
#             labels.pop(p_idx)
#         else:
#             shape[p_idx] = self.multi_pos + 1

#         return shape, positions, labels

# def _add_hcs_positions_layers(
#         self, shape: Tuple[int, ...], positions: List[str], sequence: MDASequence
#     ):
#         dtype = f"uint{self._mmc.getImageBitDepth()}"

#         # create a zarr store for each channel (or all channels when not splitting)
#         # to store the images to display so we don't overflow memory.
#         for pos in positions:

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
#             fname = self._mda_meta.file_name if self._mda_meta.should_save else "HCS"

#             layer = self.viewer.add_image(z, name=f"{fname}_{id_}")

#             # add metadata to layer
#             # storing event.index in addition to channel.config because it's
#             # possible to have two of the same channel in one sequence.
#             layer.metadata["useq_sequence"] = sequence
#             layer.metadata["uid"] = sequence.uid
#             layer.metadata["well"] = pos


# to add in "_on_mda_started()"

# elif self._mda_meta.mode == "hcs":

#     shape, positions, labels = self._interpret_hcs_positions(sequence)

#     self._add_hcs_positions_layers(tuple(shape), positions, sequence)


# to add in "_on_mda_frame"

# elif meta.mode == "hcs":

#     if self.multi_pos == 0:
#         axis_order.remove("p")

#     # get the actual index of this image into the array
#     # add it to the zarr store
#     im_idx = ()
#     for k in axis_order:
#         if k == "p" and self.multi_pos > 0:
#             im_idx = im_idx + (int(event.pos_name[-3:]),)
#         else:
#             im_idx = im_idx + (event.index[k],)

#     pos_name = event.pos_name.split("_")[0]
#     layer_name = f"{pos_name}_{event.sequence.uid}"
#     self._mda_temp_arrays[layer_name][im_idx] = image

#     # translate only once
#     fname = self._mda_meta.file_name if self._mda_meta.should_save else "HCS"
#     layer = self.viewer.layers[f"{fname}_{layer_name}"]

#     # move the viewer step to the most recently added image
#     for a, v in enumerate(im_idx):
#         self.viewer.dims.set_point(a, v)

#     layer.reset_contrast_limits()

#     # zoom_out_factor = (
#     #     self.explorer.scan_size_r
#     #     if self.explorer.scan_size_r >= self.explorer.scan_size_c
#     #     else self.explorer.scan_size_c
#     # )
#     # self.viewer.camera.zoom = 1 / zoom_out_factor
#     self.viewer.reset_view()
