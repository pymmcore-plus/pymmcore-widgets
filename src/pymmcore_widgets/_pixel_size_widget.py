import itertools
import re
from typing import Any, List, Optional, Tuple

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QMargins, QSize, Qt
from qtpy.QtGui import QColor
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._objective_widget import ObjectivesWidget

SPACING = 10
MARGINS = QMargins(5, 5, 5, 5)

RESOLUTION_ID_PREFIX = "px_size_"

OBJECTIVE_LABEL = 0
RESOLUTION_ID = 1
CAMERA_PX_SIZE = 2
MAGNIFICATION = 3
IMAGE_PX_SIZE = 4
LABEL_STATUS = 5


class PixelSizeTable(QtW.QTableWidget):
    """Create a Table to set pixel size configurations."""

    def __init__(self, parent: Optional[QtW.QWidget] = None) -> None:
        super().__init__(parent)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(hh.Stretch)
        hh.setDefaultAlignment(Qt.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(hh.Stretch)
        self.setSelectionBehavior(QtW.QAbstractItemView.SelectItems)
        self.setDragDropMode(QtW.QAbstractItemView.NoDragDrop)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(
            [
                "Objective",
                "Configuration Name",
                "Camera Pixel Size (µm)",
                "Magnification",
                "Image Pixel Size (µm)",
                "Status",
                "",
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

        self._create_wdg()

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeDefined.connect(self._on_px_defined)
        self._mmc.events.pixelSizeSet.connect(self._on_px_set)
        self._mmc.events.pixelSizeDeleted.connect(self._on_px_deleted)

        self.table.cellChanged.connect(self._on_cell_changed)

        self._on_sys_cfg_loaded()

    def _create_wdg(self) -> None:
        main_layout = QtW.QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(MARGINS)
        main_layout.setAlignment(Qt.AlignCenter)
        self.setLayout(main_layout)

        wdg = QtW.QGroupBox()
        layout = QtW.QVBoxLayout()
        layout.setSpacing(SPACING)
        layout.setContentsMargins(MARGINS)
        wdg.setLayout(layout)

        btns = self._create_radiobtn_wdg()
        layout.addWidget(btns)

        self.table = PixelSizeTable(parent=self)
        layout.addWidget(self.table)

        self.layout().addWidget(wdg)

    def _add_delete_btn(self, row: int) -> None:
        wdg = QtW.QWidget()
        layout = QtW.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        wdg.setLayout(layout)
        self._delete_btn = QtW.QPushButton(text="Delete")
        self._delete_btn.setFixedWidth(70)
        self._delete_btn.setSizePolicy(QtW.QSizePolicy.Fixed, QtW.QSizePolicy.Fixed)
        self._delete_btn.setToolTip("Delete configuration.")
        self._delete_btn.clicked.connect(self._delete_cfg)

        self._delete_btn.setProperty("row", row)

        layout.addWidget(self._delete_btn)
        self.table.setCellWidget(row, 6, wdg)

    def _add_status_label(self, row: int) -> None:
        self.status_lbl = QtW.QLabel()
        self.status_lbl.setProperty("row", row)
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, LABEL_STATUS, self.status_lbl)

    def _create_radiobtn_wdg(self) -> QtW.QWidget:
        self.rbt_wdg = QtW.QWidget()
        layout = QtW.QHBoxLayout()
        layout.setSpacing(SPACING)
        layout.setContentsMargins(MARGINS)
        self.rbt_wdg.setLayout(layout)

        self.mag_radiobtn = QtW.QRadioButton(text="Calculate Magnifiction")
        self.img_px_radiobtn = QtW.QRadioButton(text="Calculate Image Pixel Size")
        self.img_px_radiobtn.setChecked(True)

        self.mag_radiobtn.toggled.connect(self._on_mag_toggle)
        self.img_px_radiobtn.toggled.connect(self._on_img_toggle)

        spacer = QtW.QSpacerItem(
            10, 10, QtW.QSizePolicy.Expanding, QtW.QSizePolicy.Minimum
        )
        layout.addItem(spacer)

        layout.addWidget(self.mag_radiobtn)
        layout.addWidget(self.img_px_radiobtn)

        return self.rbt_wdg

    def _update_wdg_size(self) -> None:
        h = self.sizeHint().height()
        self.setMinimumWidth(self.sizeHint().width() * 2)
        self.setMinimumHeight(int(h + (h * 20 / 100)))

    def _update_status_label(self, row: int) -> None:
        resolutionID = self.table.item(row, RESOLUTION_ID).text()
        px_size = float(self.table.item(row, IMAGE_PX_SIZE).text())
        lbl = self.table.cellWidget(row, LABEL_STATUS)

        if resolutionID in self._mmc.getAvailablePixelSizeConfigs() and px_size > 0.0:
            lbl.setPixmap(
                icon(MDI6.check_bold, color=(0, 255, 0)).pixmap(QSize(20, 20))
            )
        else:
            lbl.setPixmap(icon(MDI6.close_thick, color="magenta").pixmap(QSize(20, 20)))

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
                self.table.setItem(idx, OBJECTIVE_LABEL, objective_item)

                cfg_name = "None"
                px_value = 0.0
                total_mag = 0.0

                for obj, cfg, px in obj_cfg_px:
                    if objective == obj:
                        cfg_name = cfg
                        px_value = px
                        break

                self._set_item_in_table(idx, RESOLUTION_ID, cfg_name)
                self._set_item_in_table(idx, IMAGE_PX_SIZE, px_value)

                mag_value = (
                    int(match.groups()[0])
                    if (match := re.search(r"(\d{1,3})[xX]", objective))
                    else 0.0
                )
                total_mag = mag_value * self._mmc.getMagnificationFactor()

                self._set_item_in_table(idx, MAGNIFICATION, total_mag)
                self._magnification.append([objective, total_mag])

                if (
                    self._camera_pixel_size == 0.0
                    and total_mag != 0.0
                    and px_value != 0.0
                    and cfg_name
                ):
                    self._camera_pixel_size = total_mag * px_value

                self._set_item_in_table(idx, CAMERA_PX_SIZE, self._camera_pixel_size)

                self._add_delete_btn(idx)

                self._add_status_label(idx)
                self._update_status_label(idx)

        self._update_wdg_size()

    def _get_px_info(self) -> List[Tuple[str, str, float]]:
        obj_cfg_px = []
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            obj = list(self._mmc.getPixelSizeConfigData(cfg))[0][2]
            px_value = self._mmc.getPixelSizeUmByID(cfg)
            obj_cfg_px.append((obj, cfg, px_value))
        return obj_cfg_px

    def _select_item_flags_and_color(self, col: int) -> Tuple[Qt.ItemFlag, str]:
        # TODO find how to get the defalut color from parent
        # default_color = self.table.item(0, 0).foreground().color()
        default_color = ""
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
        if (
            objective == resID_objective
            and self.table.item(row, RESOLUTION_ID).text() != "None"
        ):
            return

        with signals_blocked(self.table):
            self._set_item_in_table(row, RESOLUTION_ID, resolutionID)

    def _on_px_set(self, resolutionID: str, pixSize: float) -> None:
        objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        match = self.table.findItems(objective, Qt.MatchExactly)
        row = match[0].row()
        with signals_blocked(self.table):
            self._set_item_in_table(row, RESOLUTION_ID, resolutionID)
            self._set_item_in_table(row, IMAGE_PX_SIZE, pixSize)

            mag = self._calculate_magnification(
                self.table.item(row, CAMERA_PX_SIZE).text(), str(pixSize)
            )
            self._set_item_in_table(row, MAGNIFICATION, mag)

        self._update_status_label(row)

    def _on_px_deleted(self, resolutionID: str) -> None:
        match = self.table.findItems(resolutionID, Qt.MatchExactly)
        if not match:
            return
        row = match[0].row()
        with signals_blocked(self.table):
            self._set_item_in_table(row, RESOLUTION_ID, "None")
            self._set_item_in_table(row, IMAGE_PX_SIZE, "0.0")

        self._update_status_label(row)

    def _on_mag_toggle(self, state: bool) -> None:
        self._enable_column(MAGNIFICATION, not state)

    def _on_img_toggle(self, state: bool) -> None:
        self._enable_column(IMAGE_PX_SIZE, not state)

    def _enable_column(self, column: int, enable: bool) -> None:
        if enable:
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
            # TODO find how to get the defalut color from parent
            # color = self.table.item(0, 0).foreground().color()
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
        row = self.sender().property("row")
        resolutionID = self.table.item(row, RESOLUTION_ID).text()
        if resolutionID not in self._mmc.getAvailablePixelSizeConfigs():
            with signals_blocked(self.table):
                self._set_item_in_table(row, RESOLUTION_ID, "None")
                self._set_item_in_table(row, IMAGE_PX_SIZE, "0.0")
            return
        self._mmc.deletePixelSizeConfig(resolutionID)

    def _on_cell_changed(self, row: int, col: int) -> None:
        objective_label = self.table.item(row, OBJECTIVE_LABEL).text()
        resolutionID = self.table.item(row, RESOLUTION_ID).text()
        mag = self.table.item(row, MAGNIFICATION).text()
        camera_px_size = self.table.item(row, CAMERA_PX_SIZE).text()
        image_px_size = self.table.item(row, IMAGE_PX_SIZE).text()

        with signals_blocked(self.table):
            if col == RESOLUTION_ID:
                if resolutionID in self._mmc.getAvailablePixelSizeConfigs():

                    _id = "None"
                    for cfg in self._mmc.getAvailablePixelSizeConfigs():
                        cfg_data = list(
                            itertools.chain(*self._mmc.getPixelSizeConfigData(cfg))
                        )
                        if objective_label in cfg_data:
                            _id = cfg
                            break
                    self._set_item_in_table(row, RESOLUTION_ID, _id)

                    raise ValueError(
                        f"There is already a configuration called '{resolutionID}'! "
                        "Please choose a different name."
                    )

                elif self._is_read_only(IMAGE_PX_SIZE):
                    image_px_size = self._calculate_image_px_size(camera_px_size, mag)
                    self._set_item_in_table(row, IMAGE_PX_SIZE, image_px_size)

                elif self._is_read_only(MAGNIFICATION):
                    mag = self._calculate_magnification(camera_px_size, image_px_size)
                    self._set_item_in_table(row, MAGNIFICATION, mag)

                else:
                    return

            elif col == CAMERA_PX_SIZE:  # cam px size
                if self._is_read_only(MAGNIFICATION):
                    mag = self._calculate_magnification(camera_px_size, image_px_size)
                    self._set_item_in_table(row, MAGNIFICATION, mag)

                elif self._is_read_only(IMAGE_PX_SIZE):
                    image_px_size = self._calculate_image_px_size(camera_px_size, mag)
                    self._set_item_in_table(row, IMAGE_PX_SIZE, image_px_size)

                self._update_cam_px_size(camera_px_size)

            elif col == MAGNIFICATION:  # mag
                if self._is_read_only(IMAGE_PX_SIZE):
                    image_px_size = self._calculate_image_px_size(camera_px_size, mag)
                    self._set_item_in_table(row, IMAGE_PX_SIZE, image_px_size)

            elif col == IMAGE_PX_SIZE:  # img px size
                if self._is_read_only(MAGNIFICATION):
                    mag = self._calculate_magnification(camera_px_size, image_px_size)
                    self._set_item_in_table(row, MAGNIFICATION, mag)

            else:
                return

        self._apply_changes(row)

    def _apply_changes(self, row: int) -> None:
        obj_label = self.table.item(row, OBJECTIVE_LABEL).text()
        resolutionID = self.table.item(row, RESOLUTION_ID).text()
        mag = float(self.table.item(row, MAGNIFICATION).text())
        self._camera_pixel_size = float(self.table.item(row, CAMERA_PX_SIZE).text())
        px_size_um = float(self.table.item(row, IMAGE_PX_SIZE).text())

        if resolutionID == "None":
            resolutionID = f"{RESOLUTION_ID_PREFIX}{round(mag, 1)}x"
            with signals_blocked(self.table):
                self._set_item_in_table(row, RESOLUTION_ID, resolutionID)

        self._update_magnification_list(obj_label, mag)
        self._delete_if_exist(resolutionID, obj_label)
        self._define_and_set_px(resolutionID, obj_label, px_size_um)

        self._update_status_label(row)

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

    def _update_cam_px_size(self, value: Any) -> None:
        for r in range(self.table.rowCount()):
            cpx = self.table.item(r, CAMERA_PX_SIZE).text()
            if cpx == value:
                continue
            self._set_item_in_table(r, CAMERA_PX_SIZE, value)

    def _is_read_only(self, col: int) -> bool:
        if col == MAGNIFICATION:
            return self.mag_radiobtn.isChecked()  # type: ignore
        elif col == IMAGE_PX_SIZE:
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
