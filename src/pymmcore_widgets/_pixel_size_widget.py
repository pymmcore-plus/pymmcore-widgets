import itertools
import re
from typing import Any, List, Optional, Tuple

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._objective_widget import ObjectivesWidget

RESOLUTION_ID_PREFIX = "px_size_"


class PixelSizeTable(QtW.QTableWidget):
    """Create a Table to set pixel size configurations."""

    def __init__(self, parent: Optional[QtW.QWidget] = None) -> None:
        super().__init__(parent)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        hdr.setDefaultAlignment(Qt.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        self.setSelectionBehavior(QtW.QAbstractItemView.SelectItems)
        self.setDragDropMode(QtW.QAbstractItemView.NoDragDrop)
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


class PixelSizeWidget(QtW.QDialog):
    """Make a widget to set the pixel size configuration.

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

        self.setWindowTitle("Set Image Pixel Size")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._magnification: List[List[str, float]] = []  # type: ignore
        self._camera_pixel_size: float = 0.0

        self._objective_device = (
            objective_device or ObjectivesWidget()._guess_objective_device()
        )

        main_layout = QtW.QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        self._create_wdg()

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeDefined.connect(self._on_px_defined)
        self._mmc.events.pixelSizeSet.connect(self._on_px_set)
        self._mmc.events.pixelSizeDeleted.connect(self._on_px_deleted)

        self.table.cellChanged.connect(self._on_cell_changed)

        self._on_sys_cfg_loaded()

    def _create_wdg(self) -> None:

        btns = self._create_radiobtn_wdg()
        self.layout().addWidget(btns)

        self.table = PixelSizeTable()
        self.layout().addWidget(self.table)

        self.setMinimumSize(750, 300)

    def _create_radiobtn_wdg(self) -> QtW.QGroupBox:
        wdg = QtW.QGroupBox()
        layout = QtW.QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(layout)

        lbl = QtW.QLabel(text="Select what to calculate from the table:")
        self.mag_radiobtn = QtW.QRadioButton(text="magnifiction")
        self.cam_px_radiobtn = QtW.QRadioButton(text="camera pixel size")
        self.img_px_radiobtn = QtW.QRadioButton(text="image pixel size")
        self.img_px_radiobtn.setChecked(True)

        self.mag_radiobtn.toggled.connect(self._on_mag_toggle)
        self.cam_px_radiobtn.toggled.connect(self._on_cam_toggle)
        self.img_px_radiobtn.toggled.connect(self._on_img_toggle)

        self._delete_btn = QtW.QPushButton()
        self._delete_btn.setIcon(icon(MDI6.close_thick, color="magenta"))
        self._delete_btn.setIconSize(QSize(20, 20))
        self._delete_btn.setSizePolicy(QtW.QSizePolicy.Fixed, QtW.QSizePolicy.Fixed)
        self._delete_btn.setToolTip("Delete selected configurations.")

        self._delete_btn.clicked.connect(self._delete_cfg)

        layout.addWidget(lbl)
        layout.addWidget(self.mag_radiobtn)
        layout.addWidget(self.cam_px_radiobtn)
        layout.addWidget(self.img_px_radiobtn)

        spacer = QtW.QSpacerItem(
            10, 10, QtW.QSizePolicy.Expanding, QtW.QSizePolicy.Minimum
        )
        layout.addItem(spacer)

        layout.addWidget(self._delete_btn)

        return wdg

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

    def _on_sys_cfg_loaded(self) -> None:

        if not self._objective_device:
            self._objective_device = ObjectivesWidget()._guess_objective_device()
        if not self._objective_device:
            return

        self._magnification.clear()
        self._camera_pixel_size = 0.0

        obj_list = self._mmc.getStateLabels(self._objective_device)
        self.table.setRowCount(len(obj_list))

        obj_cfg_px = self._get_px_info()

        with signals_blocked(self.table):
            for idx, objective in enumerate(obj_list):
                objective_item = QtW.QTableWidgetItem(objective)
                objective_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(idx, 0, objective_item)

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

    def _get_px_info(self) -> List[Tuple[str, str, float]]:
        obj_cfg_px = []
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            obj = list(self._mmc.getPixelSizeConfigData(cfg))[0][2]
            px_value = self._mmc.getPixelSizeUmByID(cfg)
            obj_cfg_px.append((obj, cfg, px_value))
        return obj_cfg_px

    def _select_item_flags_and_color(self, col: int) -> Tuple[Qt.ItemFlag, str]:
        # TODO find how to get the defalut color from parent
        default_color = self.table.item(0, 0).background().color()
        return (
            (Qt.ItemIsEnabled | Qt.ItemIsSelectable, "magenta")
            if self._is_read_only(col)
            else (
                Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
                default_color,
            )
        )

    def _set_item_in_table(self, row: int, col: int, value: Any) -> None:
        item = QtW.QTableWidgetItem(str(value))
        item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
        flags, color = self._select_item_flags_and_color(col)
        item.setFlags(flags)
        item.setForeground(QColor(color))
        self.table.setItem(row, col, item)

    def _on_px_defined(
        self, resolutionID: str, deviceLabel: str, propName: str, objective: str
    ) -> None:

        match = self.table.findItems(objective, Qt.MatchExactly)
        row = match[0].row()

        # if there is a resolutionID with the same objective, do nothing.
        resID_objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        if objective == resID_objective and self.table.item(row, 1).text() != "None":
            return

        with signals_blocked(self.table):
            self._set_item_in_table(row, 1, resolutionID)

    def _on_px_set(self, resolutionID: str, pixSize: float) -> None:
        objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        match = self.table.findItems(objective, Qt.MatchExactly)
        row = match[0].row()
        with signals_blocked(self.table):
            self._set_item_in_table(row, 1, resolutionID)
            self._set_item_in_table(row, 4, pixSize)

            if self.img_px_radiobtn.isChecked() or self.cam_px_radiobtn.isChecked():
                self._calculate_and_update_camera_px_size(
                    str(pixSize), self.table.item(row, 2).text()
                )
            else:
                mag = self._calculate_magnification(
                    self.table.item(row, 3).text(), str(pixSize)
                )
                self._set_item_in_table(row, 2, mag)

    def _on_px_deleted(self, resolutionID: str) -> None:
        match = self.table.findItems(resolutionID, Qt.MatchExactly)
        if not match:
            return
        row = match[0].row()
        with signals_blocked(self.table):
            self._set_item_in_table(row, 1, "None")
            self._set_item_in_table(row, 4, "0.0")

    def _on_mag_toggle(self, state: bool) -> None:
        self._enable_column(2, not state)

    def _on_cam_toggle(self, state: bool) -> None:
        self._enable_column(3, not state)

    def _on_img_toggle(self, state: bool) -> None:
        self._enable_column(4, not state)

    def _enable_column(self, column: int, enable: bool) -> None:
        if enable:
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
            color = ""
        else:
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            color = "magenta"
        with signals_blocked(self.table):
            for row in range(self.table.rowCount()):
                item = self.table.item(row, column)
                item.setFlags(flags)
                item.setForeground(QColor(color))

    def _delete_cfg(self) -> None:
        rows = {r.row() for r in self.table.selectedIndexes()}
        for row in rows:
            resolutionID = self.table.item(row, 1).text()
            if resolutionID not in self._mmc.getAvailablePixelSizeConfigs():
                continue
            self._mmc.deletePixelSizeConfig(resolutionID)

    def _on_cell_changed(self, row: int, col: int) -> None:

        mag = self.table.item(row, 2).text()
        camera_px_size = self.table.item(row, 3).text()
        image_px_size = self.table.item(row, 4).text()

        with signals_blocked(self.table):

            if col == 2:  # mag

                if self._is_read_only(3):
                    self._calculate_and_update_camera_px_size(image_px_size, mag)

                elif self._is_read_only(4):
                    image_px_size = self._calculate_image_px_size(camera_px_size, mag)
                    self._set_item_in_table(row, 4, image_px_size)

            elif col == 3:  # cam px size

                if self._is_read_only(2):
                    mag = self._calculate_magnification(camera_px_size, image_px_size)
                    self._set_item_in_table(row, 2, mag)

                elif self._is_read_only(4):
                    image_px_size = self._calculate_image_px_size(camera_px_size, mag)
                    self._set_item_in_table(row, 4, image_px_size)

                self._update_cam_px_size(camera_px_size)

            elif col == 4:  # img px size

                if self._is_read_only(2):
                    mag = self._calculate_magnification(camera_px_size, image_px_size)
                    self._set_item_in_table(row, 2, mag)

                if self._is_read_only(3):
                    self._calculate_and_update_camera_px_size(image_px_size, mag)

        self._apply_changes(row)

    def _apply_changes(self, row: int) -> None:

        obj_label = self.table.item(row, 0).text()
        resolutionID = self.table.item(row, 1).text()
        mag = float(self.table.item(row, 2).text())
        self._camera_pixel_size = float(self.table.item(row, 3).text())
        px_size_um = float(self.table.item(row, 4).text())

        if resolutionID == "None":
            resolutionID = f"{RESOLUTION_ID_PREFIX}{mag}x"
            with signals_blocked(self.table):
                self._set_item_in_table(row, 1, resolutionID)

        self._update_magnification_list(obj_label, mag)
        self._delete_if_exist(resolutionID, obj_label)
        self._define_and_set_px(resolutionID, obj_label, px_size_um)

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

    def _calculate_magnification(
        self, camera_px_size: str, image_px_size: str
    ) -> float:
        try:
            mag = float(camera_px_size) / float(image_px_size)
        except ZeroDivisionError:
            mag = 0.0
        return mag

    def _calculate_image_px_size(
        self, camera_px_size: str, magnification: str
    ) -> float:
        try:
            ipx = float(camera_px_size) / float(magnification)
        except ZeroDivisionError:
            ipx = 0.0
        return ipx

    def _calculate_and_update_camera_px_size(
        self, image_px_size: str, magnification: str
    ) -> None:
        camera_px_size = float(image_px_size) * float(magnification)
        self._update_cam_px_size(camera_px_size)

    def _update_cam_px_size(self, value: Any) -> None:
        for r in range(self.table.rowCount()):
            cpx = self.table.item(r, 3).text()
            if cpx == value:
                continue
            self._set_item_in_table(r, 3, value)

    def _is_read_only(self, col: int) -> bool:
        if col == 2:
            return self.mag_radiobtn.isChecked()  # type: ignore
        elif col == 3:
            return self.cam_px_radiobtn.isChecked()  # type: ignore
        elif col == 4:
            return self.img_px_radiobtn.isChecked()  # type: ignore
        else:
            return False

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
