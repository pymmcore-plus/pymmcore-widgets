from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import numpy as np
from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter

# from ._pygfx_canvas import PyGFXViewerCanvas

if TYPE_CHECKING:
    import xarray as xr  # noqa

    from ._dims_slider import Indices


def isel(store: Any, indexers: Indices) -> np.ndarray:
    """Select a slice from a data store."""
    if isinstance(store, (OMEZarrWriter, OMETiffWriter)):
        return isel_mmcore_5dbase(store, indexers)
    if isinstance(store, np.ndarray):
        return isel_np_array(store, indexers)
    if not TYPE_CHECKING:
        xr = sys.modules.get("xarray")
    if xr and isinstance(store, xr.DataArray):
        return store.isel(indexers).to_numpy()
    raise NotImplementedError(f"Unknown datastore type {type(store)}")


def isel_np_array(data: np.ndarray, indexers: Indices) -> np.ndarray:
    idx = tuple(indexers.get(k, slice(None)) for k in range(data.ndim))
    return data[idx]


def isel_mmcore_5dbase(
    writer: OMEZarrWriter | OMETiffWriter, indexers: Indices
) -> np.ndarray:
    p_index = indexers.get("p", 0)
    if isinstance(p_index, slice):
        raise NotImplementedError("Cannot slice over position index")  # TODO

    try:
        sizes = [*list(writer.position_sizes[p_index]), "y", "x"]
    except IndexError as e:
        raise IndexError(
            f"Position index {p_index} out of range for {len(writer.position_sizes)}"
        ) from e

    data = writer.position_arrays[writer.get_position_key(p_index)]
    full = slice(None, None)
    index = tuple(indexers.get(k, full) for k in sizes)
    return data[index]  # type: ignore
