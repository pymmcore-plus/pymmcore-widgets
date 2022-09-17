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

        self._magnification: List[List[str, float]] = []  # type: ignore
        self._camera_pixel_size: float = 0.0

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeDefined.connect(self._on_px_defined)
        self._mmc.events.pixelSizeSet.connect(self._on_px_set)
        self._mmc.events.pixelSizeDeleted.connect(self._on_px_deleted)

        self.cellChanged.connect(self._on_cell_changed)

        self._objective_device = (
            objective_device or ObjectivesWidget()._guess_objective_device()
        )

        self._set_table_property()

        self._on_sys_cfg_loaded()

    def _set_table_property(self) -> None:
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

    def _get_px_info(self) -> List[Tuple[str, str, float]]:
        obj_cfg_px = []
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            obj = list(self._mmc.getPixelSizeConfigData(cfg))[0][2]
            px_value = self._mmc.getPixelSizeUmByID(cfg)
            obj_cfg_px.append((obj, cfg, px_value))
        return obj_cfg_px

    def _on_sys_cfg_loaded(self) -> None:

        if not self._objective_device:
            self._objective_device = ObjectivesWidget()._guess_objective_device()
        if not self._objective_device:
            return

        self._magnification.clear()

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

                mag_value = (
                    int(match.groups()[0])
                    if (match := re.search(r"(\d{1,3})[xX]", objective))
                    else 0.0
                )
                total_mag = mag_value * self._mmc.getMagnificationFactor()

                self._set_item_in_table(idx, 2, total_mag)
                self._magnification.append([objective, total_mag])

                if (
                    self._camera_pixel_size == 0.0
                    and total_mag != 0.0
                    and px_value != 0.0
                    and cfg_name
                ):
                    self._camera_pixel_size = total_mag * px_value

                self._set_item_in_table(idx, 3, self._camera_pixel_size)

    def _on_px_defined(
        self, resolutionID: str, deviceLabel: str, propName: str, objective: str
    ) -> None:

        match = self.findItems(objective, Qt.MatchExactly)
        row = match[0].row()

        # if there is a resolutionID with the same objective, do nothing.
        resID_objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        if objective == resID_objective and self.item(row, 1).text() != "None":
            return

        with signals_blocked(self):
            self._set_item_in_table(row, 1, resolutionID)

    def _on_px_set(self, resolutionID: str, pixSize: float) -> None:
        objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        match = self.findItems(objective, Qt.MatchExactly)
        row = match[0].row()
        with signals_blocked(self):
            self._set_item_in_table(row, 1, resolutionID)
            self._set_item_in_table(row, 4, pixSize)

    def _on_px_deleted(self, resolutionID: str) -> None:
        match = self.findItems(resolutionID, Qt.MatchExactly)
        if not match:
            return
        row = match[0].row()
        with signals_blocked(self):
            self._set_item_in_table(row, 1, "None")
            self._set_item_in_table(row, 4, "0.0")

    def _on_cell_changed(self, row: int, col: int) -> None:

        mag = self.item(row, 2).text()
        camera_px_size = self.item(row, 3).text()
        image_px_size = self.item(row, 4).text()

        with signals_blocked(self):

            if col == 2:  # mag
                if float(camera_px_size) != 0.0:
                    image_px_size = float(camera_px_size) / float(mag)
                    self._set_item_in_table(row, 4, image_px_size)

            elif col == 3:  # cam px size

                for r in range(self.rowCount()):
                    self._set_item_in_table(r, col, camera_px_size)

                    mag = self.item(r, 2).text()

                    image_px_size = (
                        0.0
                        if float(mag) == 0.0 or float(camera_px_size) == 0.0
                        else float(camera_px_size) / float(mag)
                    )

                    self._set_item_in_table(r, 4, image_px_size)

                if float(mag) != 0.0 and float(camera_px_size) != 0.0:

                    image_px_size = float(camera_px_size) / float(mag)
                    self._set_item_in_table(row, 4, image_px_size)

            elif col == 4:  # img px size
                mag = (
                    0.0
                    if float(image_px_size) == 0.0 or float(camera_px_size) == 0.0
                    else float(camera_px_size) / float(image_px_size)
                )

                self._set_item_in_table(row, 2, mag)

        self._apply_changes(row)

    def _set_item_in_table(self, row: int, col: int, value: Any) -> None:
        item = QtW.QTableWidgetItem(str(value))
        item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
        self.setItem(row, col, item)

    def _apply_changes(self, row: int) -> None:

        obj_label = self.item(row, 0).text()
        resolutionID = self.item(row, 1).text()
        mag = float(self.item(row, 2).text())
        self._camera_pixel_size = float(self.item(row, 3).text())
        px_size_um = float(self.item(row, 4).text())

        if resolutionID == "None":
            resolutionID = f"{RESOLUTION_ID_PREFIX}{mag}x"
            with signals_blocked(self):
                self._set_item_in_table(row, 1, resolutionID)

        self._update_magnification_list(obj_label, mag)
        self._delete_if_exist(resolutionID, obj_label)
        self._define_and_set_px(resolutionID, obj_label, px_size_um)

    def _update_magnification_list(
        self, oblective_label: str, magnification: float
    ) -> None:

        if self._magnification:
            for obj_mag in self._magnification:
                o, _ = obj_mag
                if o == oblective_label:
                    obj_mag[1] = magnification
                    break
        else:
            self._magnification.append([oblective_label, magnification])

    def _delete_if_exist(self, resolutionID: str, objective_label: str) -> None:
        # remove resolutionID if contains obj_label in ConfigData
        if self._mmc.getAvailablePixelSizeConfigs():
            for cfg in self._mmc.getAvailablePixelSizeConfigs():
                cfg_data = list(itertools.chain(*self._mmc.getPixelSizeConfigData(cfg)))
                if objective_label in cfg_data:
                    self._mmc.deletePixelSizeConfig(cfg)
                    break

        if resolutionID in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(resolutionID)

    def _define_and_set_px(
        self, resolutionID: str, objective_label: str, px_size_um: float
    ) -> None:
        self._mmc.definePixelSizeConfig(
            resolutionID, self._objective_device, "Label", objective_label  # type: ignore # noqa: E501
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

        self._delete_btn = QtW.QPushButton(text="Delete Selected Configuration")
        self._delete_btn.clicked.connect(self._delete_cfg)

        layout.addItem(spacer)
        layout.addWidget(self._delete_btn)

        return wdg

    def _delete_cfg(self) -> None:
        rows = {r.row() for r in self.table.selectedIndexes()}
        for row in rows:
            resolutionID = self.table.item(row, 1).text()
            if resolutionID not in self._mmc.getAvailablePixelSizeConfigs():
                continue
            self._mmc.deletePixelSizeConfig(resolutionID)
