from __future__ import annotations

import warnings
from contextlib import suppress
from typing import TYPE_CHECKING, cast

from ndv import DataWrapper
from pymmcore_plus.mda.handlers import TensorStoreHandler

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping
    from pathlib import Path
    from typing import Any, TypeGuard

    import numpy as np
    from ndv import Indices
    from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase


class MMTensorStoreWrapper(DataWrapper["TensorStoreHandler"]):
    def sizes(self) -> Mapping[Hashable, int]:
        with suppress(Exception):
            return self._data.current_sequence.sizes  # type: ignore [return-value]
        return {}

    def guess_channel_axis(self) -> Hashable | None:
        return "c"

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[TensorStoreHandler]:
        return isinstance(obj, TensorStoreHandler)

    def isel(self, indexers: Indices) -> np.ndarray:
        return self._data.isel({str(k): v for k, v in indexers.items()})

    def save_as_zarr(self, save_loc: str | Path) -> None:
        if (store := self._data.store) is None:
            return
        import tensorstore as ts

        new_spec = store.spec().to_json()
        new_spec["kvstore"] = {"driver": "file", "path": str(save_loc)}
        new_ts = ts.open(new_spec, create=True).result()
        new_ts[:] = store.read().result()


class MM5DWriter(DataWrapper["_5DWriterBase"]):
    def guess_channel_axis(self) -> Hashable | None:
        return "c"

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[_5DWriterBase]:
        try:
            from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase
        except ImportError:
            from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter

            _5DWriterBase = (OMETiffWriter, OMEZarrWriter)
        if isinstance(obj, _5DWriterBase):
            return True
        return False

    def save_as_zarr(self, save_loc: str | Path) -> None:
        import zarr
        from pymmcore_plus.mda.handlers import OMEZarrWriter

        if isinstance(self._data, OMEZarrWriter):
            zarr.copy_store(self._data.group.store, zarr.DirectoryStore(save_loc))
        raise NotImplementedError(f"Cannot save {type(self._data)} data to Zarr.")

    def isel(self, indexers: Indices) -> np.ndarray:
        p_index = indexers.get("p", 0)
        if isinstance(p_index, slice):
            warnings.warn("Cannot slice over position index", stacklevel=2)  # TODO
            p_index = p_index.start
        p_index = cast(int, p_index)

        try:
            sizes = [*list(self._data.position_sizes[p_index]), "y", "x"]
        except IndexError as e:
            raise IndexError(
                f"Position index {p_index} out of range for "
                f"{len(self._data.position_sizes)}"
            ) from e

        data = self._data.position_arrays[self._data.get_position_key(p_index)]
        full = slice(None, None)
        index = tuple(indexers.get(k, full) for k in sizes)
        return data[index]  # type: ignore [no-any-return]
