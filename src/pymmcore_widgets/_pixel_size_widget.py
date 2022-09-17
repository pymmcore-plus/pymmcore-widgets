import itertools
import re
from typing import Any, List, Optional, Tuple

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from superqt.utils import signals_blocked

from ._objective_widget import ObjectivesWidget

RESOLUTION_ID_PREFIX = "px_size_"


class PixelSizeTable(QtW.QTableWidget):
    """Create a Table to set pixel size configurations.

    Parameters
    ----------
    objective_device: str
        A device label for which to create a widget.
    parent : Optional[QWidget]
        Optional parent widget.
    """

    def __init__(
        self,
        objective_device: str = "",
        parent: Optional[QtW.QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._magnification: List[Tuple[str, float]] = []
        self._camera_pixel_size: float = 0.0

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeDefined.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeSet.connect(self._on_px_set)
        self._mmc.events.pixelSizeDeleted.connect(self._on_px_deleted)

        self.cellChanged.connect(self._on_cell_changed)

        self._objective_device = (
            objective_device or ObjectivesWidget()._guess_objective_device()
        )

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        hdr.setDefaultAlignment(Qt.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        self.setSelectionBehavior(QtW.QAbstractItemView.SelectItems)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(
            [
                "Objective",
                "Configuration Name",
                "Magnification",
                "Camera Pixel Size (µm)",
                "Image Pixel Size (µm)",
            ]
        )

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:

        if not self._objective_device:
            self._objective_device = ObjectivesWidget()._guess_objective_device()
        if not self._objective_device:
            return

        obj_list = self._mmc.getStateLabels(self._objective_device)
        self.setRowCount(len(obj_list))

        obj_cfg_px = self._get_px_info()

        with signals_blocked(self):
            for idx, objective in enumerate(obj_list):
                objective_item = QtW.QTableWidgetItem(objective)
                objective_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.setItem(idx, 0, objective_item)

                cfg_name = "None"
                px_value = 0.0
                total_mag = 0.0

                for obj, cfg, px in obj_cfg_px:
                    if objective == obj:
                        cfg_name = cfg
                        px_value = px
                        break

                self._set_item_in_table(idx, 1, cfg_name)
                self._set_item_in_table(idx, 4, px_value)

                if self._magnification:
                    for m in self._magnification:
                        obj, mag = m
                        if objective == obj:
                            total_mag = mag
                            break
                else:
                    mag_value = (
                        int(match.groups()[0])
                        if (match := re.search(r"(\d{1,3})[xX]", objective))
                        else 0.0
                    )
                    total_mag = mag_value * self._mmc.getMagnificationFactor()

                self._set_item_in_table(idx, 2, total_mag)

                if (
                    self._camera_pixel_size == 0.0
                    and total_mag != 0.0
                    and px_value != 0.0
                    and cfg_name
                ):
                    self._camera_pixel_size = total_mag * px_value

                self._set_item_in_table(idx, 3, self._camera_pixel_size)

    def _get_px_info(self) -> List[Tuple[str, str, float]]:
        obj_cfg_px = []
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            obj = list(self._mmc.getPixelSizeConfigData(cfg))[0][2]
            px_value = self._mmc.getPixelSizeUmByID(cfg)
            obj_cfg_px.append((obj, cfg, px_value))
        return obj_cfg_px

    def _on_px_set(self, resolutionID: str, pixSize: float) -> None:
        match = self.findItems(resolutionID, Qt.MatchExactly)
        if not match:
            return
        row = match[0].row()
        self._set_item_in_table(row, 4, pixSize)

    def _on_px_deleted(self, resulutionID: str) -> None:
        match = self.findItems(resulutionID, Qt.MatchExactly)
        if not match:
            return
        row = match[0].row()
        self._set_item_in_table(row, 1, "None")
        self._set_item_in_table(row, 4, "0.0")

    def _on_cell_changed(self, row: int, col: int) -> None:

        mag = self.item(row, 2).text()
        camera_px_size = self.item(row, 3).text()
        image_px_size = self.item(row, 4).text()

        with signals_blocked(self):

            if col == 2:
                if float(camera_px_size) == 0.0:
                    return
                image_px_size = float(mag) / float(camera_px_size)
                self._set_item_in_table(row, 4, image_px_size)

            elif col == 3:

                for r in range(self.rowCount()):
                    self._set_item_in_table(r, col, camera_px_size)

                    mag = self.item(r, 2).text()

                    image_px_size = (
                        0.0
                        if float(mag) == 0.0 or float(camera_px_size) == 0.0
                        else float(mag) / float(camera_px_size)
                    )

                    self._set_item_in_table(r, 4, image_px_size)

                if float(mag) == 0.0 or float(camera_px_size) == 0.0:
                    return

                image_px_size = float(mag) / float(camera_px_size)
                self._set_item_in_table(row, 4, image_px_size)

            elif col == 4:
                mag = (
                    0.0
                    if float(image_px_size) == 0.0 or float(camera_px_size) == 0.0
                    else float(camera_px_size) / float(image_px_size)
                )

                self._set_item_in_table(row, 2, mag)

    def _set_item_in_table(self, row: int, col: int, value: Any) -> None:
        item = QtW.QTableWidgetItem(str(value))
        item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
        self.setItem(row, col, item)

    def _set_mm_pixel_size(self) -> None:

        self._magnification.clear()

        for r in range(self.rowCount()):
            obj_label = self.item(r, 0).text()
            px_size_um = float(self.item(r, 4).text())
            mag = float(self.item(r, 2).text())

            if px_size_um == 0.0 or mag == 0.0:
                continue

            self._camera_pixel_size = float(self.item(r, 3).text())

            self._magnification.append((obj_label, mag))

            resolutionID = self.item(r, 1).text()
            if resolutionID == "None":
                resolutionID = f"{RESOLUTION_ID_PREFIX}{mag}x"
                self._set_item_in_table(r, 1, resolutionID)

            if self._mmc.getAvailablePixelSizeConfigs():
                # remove resolutionID if contains obj_label in ConfigData
                for cfg in self._mmc.getAvailablePixelSizeConfigs():
                    cfg_data = list(
                        itertools.chain(*self._mmc.getPixelSizeConfigData(cfg))
                    )
                    if obj_label in cfg_data:
                        self._mmc.deletePixelSizeConfig(cfg)
                        break

            if resolutionID in self._mmc.getAvailablePixelSizeConfigs():
                self._mmc.deletePixelSizeConfig(resolutionID)

            self._mmc.definePixelSizeConfig(
                resolutionID, self._objective_device, "Label", obj_label  # type: ignore # noqa: E501
            )
            self._mmc.setPixelSizeUm(resolutionID, px_size_um)


class PixelSizeWidget(QtW.QDialog):
    """Make a widget to set the pixel size configuration."""

    def __init__(
        self,
        parent: Optional[QtW.QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Set Image Pixel Size")

        self._mmc = mmcore or CMMCorePlus.instance()

        main_layout = QtW.QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        self._create_wdg()

        self.setMinimumSize(750, 300)

    def _create_wdg(self) -> None:

        self.table = PixelSizeTable(mmcore=self._mmc)
        self.layout().addWidget(self.table)

        btns = self._create_btn_wdg()
        self.layout().addWidget(btns)

    def _create_btn_wdg(self) -> QtW.QWidget:
        wdg = QtW.QWidget()
        layout = QtW.QHBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(0, 10, 0, 10)
        wdg.setLayout(layout)

        spacer = QtW.QSpacerItem(
            10, 10, QtW.QSizePolicy.Expanding, QtW.QSizePolicy.Minimum
        )

        self._set_btn = QtW.QPushButton(text="Set Image Pixel Sizes")
        self._set_btn.clicked.connect(self._on_set_clicked)

        layout.addItem(spacer)
        layout.addWidget(self._set_btn)

        return wdg

    def _on_set_clicked(self) -> None:
        self.table._set_mm_pixel_size()
        self.close()
