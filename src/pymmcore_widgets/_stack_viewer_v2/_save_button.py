from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from qtpy.QtWidgets import QFileDialog, QPushButton, QWidget
from superqt.iconify import QIconifyIcon

from ._indexing import is_xarray_dataarray


class SaveButton(QPushButton):
    def __init__(
        self,
        datastore: Any,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.setIcon(QIconifyIcon("mdi:content-save"))
        self.clicked.connect(self._on_click)

        self._data = datastore
        self._last_loc = str(Path.home())

    def _on_click(self) -> None:
        self._last_loc, _ = QFileDialog.getSaveFileName(
            self, "Choose destination", str(self._last_loc), ""
        )
        suffix = Path(self._last_loc).suffix
        if suffix in (".zarr", ".ome.zarr", ""):
            _save_as_zarr(self._last_loc, self._data)
        else:
            raise ValueError(f"Unsupported file format: {self._last_loc}")


def _save_as_zarr(save_loc: str | Path, data: Any) -> None:
    import zarr
    from pymmcore_plus.mda.handlers import OMEZarrWriter

    if isinstance(data, OMEZarrWriter):
        zarr.copy_store(data.group.store, zarr.DirectoryStore(save_loc))
    elif isinstance(data, zarr.Array):
        data.store = zarr.DirectoryStore(save_loc)
    elif isinstance(data, np.ndarray):
        zarr.save(str(save_loc), data)
    elif is_xarray_dataarray(data):
        data.to_zarr(save_loc)
    else:
        raise ValueError(f"Cannot save data of type {type(data)} to Zarr format.")
