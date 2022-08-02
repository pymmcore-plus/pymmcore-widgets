# These are methods that can be added in napari-micromanager 'main_window.py'
# to pair this widget with the napari viewer.


# new methods to add

# def _interpret_split_channels(
#         self, sequence: MDASequence
#     ) -> Tuple[List[int], List[str], List[str]]:
#         """Determine the shape of layers and the dimension labels.

#         ...based on whether we are splitting on channels
#         """
#         img_shape = self._mmc.getImageHeight(), self._mmc.getImageWidth()
#         # dimensions labels
#         axis_order = event_indices(next(sequence.iter_events()))
#         labels = []
#         shape = []
#         for i, a in enumerate(axis_order):
#             dim = sequence.shape[i]
#             labels.append(a)
#             shape.append(dim)
#         labels.extend(["y", "x"])
#         shape.extend(img_shape)
#         if self._mda_meta.split_channels:
#             channels = [f"_{c.config}" for c in sequence.channels]
#             with contextlib.suppress(ValueError):
#                 c_idx = labels.index("c")
#                 labels.pop(c_idx)
#                 shape.pop(c_idx)
#         else:
#             channels = [""]

#         return shape, channels, labels

# def _add_mda_channel_layers(
#         self, shape: Tuple[int, ...], channels: List[str], sequence: MDASequence
#     ):
#         """Create Zarr stores to back MDA and display as new viewer layer(s).

#         If splitting on Channels then channels will look like ["BF", "GFP",...]
#         and if we do not split on channels it will look like [""] and only one
#         layer/zarr store will be created.
#         """
#         dtype = f"uint{self._mmc.getImageBitDepth()}"

#         # create a zarr store for each channel (or all channels when not splitting)
#         # to store the images to display so we don't overflow memory.
#         for i, channel in enumerate(channels):
#             id_ = str(sequence.uid) + channel
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
#            layer = self.viewer.add_image(
#                z, name=f"{fname}_{id_}", blending="additive"
#            )

#             # add metadata to layer
#             # storing event.index in addition to channel.config because it's
#             # possible to have two of the same channel in one sequence.
#             layer.metadata["useq_sequence"] = sequence
#             layer.metadata["uid"] = sequence.uid
#             layer.metadata["ch_id"] = f"{channel}_idx{i}"


# to add in "_on_mda_started"

# if self._mda_meta.mode == "":
#     # originated from user script - assume it's an mda
#     self._mda_meta.mode = "mda"

# # work out what the shapes of the layers will be
# # this depends on whether the user selected Split Channels or not
# shape, channels, labels = self._interpret_split_channels(sequence)

# # acutally create the viewer layers backed by zarr stores
# self._add_mda_channel_layers(tuple(shape), channels, sequence)

# # set axis_labels after adding the images to ensure that the dims exist
# self.viewer.dims.axis_labels = labels


# to add in "_on_mda_frame"

# if meta.mode == "mda":
#     axis_order = list(event_indices(event))

#     # Remove 'c' from idxs if we are splitting channels
#     # also prepare the channel suffix that we use for keeping track of arrays
#     channel = ""
#     if meta.split_channels:
#         channel = f"_{event.channel.config}"
#         # split channels checked but no channels added
#         with contextlib.suppress(ValueError):
#             axis_order.remove("c")

#     # get the actual index of this image into the array and
#     # add it to the zarr store
#     im_idx = tuple(event.index[k] for k in axis_order)
#     self._mda_temp_arrays[str(event.sequence.uid) + channel][im_idx] = image

#     # move the viewer step to the most recently added image
#     for a, v in enumerate(im_idx):
#         self.viewer.dims.set_point(a, v)
