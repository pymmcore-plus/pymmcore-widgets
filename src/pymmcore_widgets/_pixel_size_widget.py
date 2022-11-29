from __future__ import annotations

import contextlib
import itertools
import re
import warnings
from typing import Any, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from ._util import block_core, guess_objective_or_prompt

OBJECTIVE_LABEL = 0
RESOLUTION_ID = 1
CAMERA_PX_SIZE = 2
MAGNIFICATION = 3
IMAGE_PX_SIZE = 4


class PixelSizeTable(QTableWidget):
    """Create a QTableWidget to set pixel size configurations."""

    HEADERS = {
        "objective": "Objective",
        "resolutionID": "Resolution ID",
        "cameraPixelSize": "Camera Pixel Size (um)",
        "magnification": "Magnification",
        "imagePixelSize": "Image Pixel Size (um)",
        "delete": "Delete",
    }

    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mmc = mmcore
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.Stretch)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(hh.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)

    def _rebuild(
        self, obj_dev: str, _cam_mag_dict: dict[str, tuple[float, float]] = None  # type: ignore # noqa:E501
    ) -> None:
        records = self._get_pixel_info(obj_dev, _cam_mag_dict)
        self.clear()
        self.setRowCount(len(records))
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(list(self.HEADERS.values()))

        for row, record in enumerate(records):
            self._populate_row(row, record)

        self._update_status()

    def _get_pixel_info(
        self, obj_dev: str, _cam_mag_dict: dict[str, tuple[float, float]] = None  # type: ignore # noqa:E501
    ) -> list[dict[str, Any]]:
        """Returns a list of records, that can be used to build a table.

        [
            {'objective': 'Something', 'resolutionID": 'something', ...},
            ...
        ]
        """
        # e.g.
        # { 'Nikon 20X Plan Fluor ELWD': ('Res20x', 0.5) }
        obj_cfg_px: dict[str, tuple[str, float]] = {}
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            obj = next(iter(self._mmc.getPixelSizeConfigData(cfg)))[2]
            obj_cfg_px[obj] = cfg, self._mmc.getPixelSizeUmByID(cfg)

        # get pixel info for each objective
        rows = []
        mag_factor = self._mmc.getMagnificationFactor()
        cam_px_guess = 0.0
        for obj_label in self._mmc.getStateLabels(obj_dev):
            res_id, px_value = obj_cfg_px.get(obj_label, ("None", 0.0))

            if _cam_mag_dict:
                cam_px_size, tot_mag = _cam_mag_dict[obj_label]
            else:
                cam_px_size = 0.0
                tot_mag = self._guess_mag(obj_label) * mag_factor

            rows.append(
                {
                    "objective": obj_label,
                    "resolutionID": res_id,
                    "cameraPixelSize": cam_px_size,
                    "magnification": f"{tot_mag:.1f}",
                    "imagePixelSize": f"{px_value:.4f}",
                }
            )

            if not cam_px_guess and (tot_mag and px_value):
                cam_px_guess = tot_mag * px_value

        if cam_px_guess:
            for row in rows:
                row["cameraPixelSize"] = f"{cam_px_guess:.2f}"

        return rows

    def _guess_mag(self, obj_label: str) -> float:
        return (
            float(match.groups()[0])
            if (match := re.search(r"(\d{1,3})[xX]", obj_label))
            else 0.0
        )

    def _update_status(self) -> None:
        for row in range(self.rowCount()):
            resolutionID = self.cellWidget(row, RESOLUTION_ID).text()
            px_size = float(self.cellWidget(row, IMAGE_PX_SIZE).text())

            if (
                resolutionID in self._mmc.getAvailablePixelSizeConfigs()
                and resolutionID != "None"
                and px_size > 0.0
            ):
                opacity = 1.00
            else:
                opacity = 0.50

            for c in range(1, self.columnCount() - 1):
                op = QGraphicsOpacityEffect()
                item = self.cellWidget(row, c)
                op.setOpacity(opacity)
                item.setGraphicsEffect(op)
                assert item.graphicsEffect().opacity() == opacity

    def _populate_row(self, row: int, record: dict) -> None:
        """Populate a row with widgets."""
        for col, key in enumerate(self.HEADERS):
            if key == "objective":
                self._new_table_item(record[key], row)
            else:
                if key == "delete":
                    wdg = self._new_delete_btn()
                else:
                    wdg = self._new_line_edit(record[key])
                    if key == "resolutionID":
                        wdg.setProperty("resID", record[key])
                self.setCellWidget(row, col, wdg)

    def _new_line_edit(self, value: Any) -> QLineEdit:
        item = QLineEdit(str(value))
        item.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFrame(False)
        if isinstance(value, (int, float)):
            item.setValidator(QDoubleValidator())
        return item

    def _new_table_item(self, value: Any, row: int) -> None:
        objective_item = QTableWidgetItem(value)
        objective_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        )
        self.setItem(row, OBJECTIVE_LABEL, objective_item)

    def _new_delete_btn(self) -> QWidget:
        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wdg.setLayout(layout)

        btn = QPushButton(text="Delete")
        btn.setFixedWidth(70)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setToolTip("Delete configuration.")
        btn.clicked.connect(self._delete_cfg)

        btn.setAutoDefault(False)
        layout.addWidget(btn)
        return wdg

    def _delete_cfg(self) -> None:
        w = self.sender().parent()
        row = self.indexAt(w.pos()).row()
        resId_edit = cast(QLineEdit, self.cellWidget(row, RESOLUTION_ID))
        img_px_edit = cast(QLineEdit, self.cellWidget(row, IMAGE_PX_SIZE))
        if resId_edit.text() in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(resId_edit.text())
        resId_edit.setText("None")
        img_px_edit.setText("0.0000")
        self._update_status()


class PixelSizeWidget(QDialog):
    """A widget for pixel size control.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.objective_device = guess_objective_or_prompt(parent=self)

        self._create_wdg()

        self._rebuild()

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeChanged.connect(self._on_px_set)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.pixelSizeChanged.disconnect(self._on_px_set)

    def _create_wdg(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(main_layout)

        wdg = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
        wdg.setLayout(layout)

        btns = self._create_radiobtn_wdg()
        layout.addWidget(btns)

        self.table = PixelSizeTable(self._mmc)
        layout.addWidget(self.table)

        self.layout().addWidget(wdg)

    def _create_radiobtn_wdg(self) -> QWidget:
        self.rbt_wdg = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
        self.rbt_wdg.setLayout(layout)

        self.mag_radiobtn = QRadioButton(text="Calculate Magnification")
        self.img_px_radiobtn = QRadioButton(text="Calculate Image Pixel Size")
        self.img_px_radiobtn.setChecked(True)

        self.mag_radiobtn.toggled.connect(self._on_mag_toggle)
        self.img_px_radiobtn.toggled.connect(self._on_img_toggle)

        spacer = QSpacerItem(
            10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        layout.addItem(spacer)

        layout.addWidget(self.mag_radiobtn)
        layout.addWidget(self.img_px_radiobtn)

        return self.rbt_wdg

    def _on_mag_toggle(self, state: bool) -> None:
        self._enable_column(MAGNIFICATION, not state)

    def _on_img_toggle(self, state: bool) -> None:
        self._enable_column(IMAGE_PX_SIZE, not state)

    def _enable_column(self, column: int, enable: bool) -> None:
        with signals_blocked(self.table):
            for row in range(self.table.rowCount()):
                item = cast(QLineEdit, self.table.cellWidget(row, column))
                if enable:
                    item.setReadOnly(False)
                    item.setStyleSheet("")
                else:
                    item.setReadOnly(True)
                    item.setStyleSheet("color:magenta")

    def _on_sys_cfg_loaded(self) -> None:
        self.objective_device = guess_objective_or_prompt(parent=self)
        self._rebuild()

    def _on_px_set(self, value: float) -> None:

        rows = []
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            if value == self._mmc.getPixelSizeUmByID(cfg):
                for r in range(self.table.rowCount()):
                    resID = self.table.cellWidget(r, RESOLUTION_ID).text()
                    if resID == cfg:
                        rows.append(r)
                        break

        for row in rows:
            self.table.cellWidget(row, IMAGE_PX_SIZE).setText(f"{value:.4f}")
            camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE)
            if value:
                _mag = self._calculate_magnification(camera_px_size.text(), str(value))
                self.table.cellWidget(row, MAGNIFICATION).setText(f"{_mag:.1f}")

        self._rebuild()

    def _rebuild(self, value: float = 0.0) -> None:
        if not self.objective_device:
            return
        self._connect_lineedit(False)
        self.table._rebuild(self.objective_device, self._store_mag_cam_px_size())
        self._reset_radiobutton()
        h = self.sizeHint().height()
        self.resize(self.sizeHint().width() * 2, int(h + (h * 20 / 100)))
        self._connect_lineedit(True)

        if value:
            self._update_mag(value)

    def _store_mag_cam_px_size(self) -> dict[str, tuple[float, float]]:
        _cam_mag_dict = {}
        for row in range(self.table.rowCount()):
            objective_label = self.table.item(row, OBJECTIVE_LABEL).text()
            camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE).text()
            mag = self.table.cellWidget(row, MAGNIFICATION).text()
            _cam_mag_dict[objective_label] = (float(camera_px_size), float(mag))
        return _cam_mag_dict

    def _reset_radiobutton(self) -> None:
        if self.mag_radiobtn.isChecked():
            self._enable_column(MAGNIFICATION, False)
        else:
            self._enable_column(IMAGE_PX_SIZE, False)

    def _connect_lineedit(self, state: bool) -> None:
        for col in range(1, 5):
            for row in range(self.table.rowCount()):
                item = cast(QLineEdit, self.table.cellWidget(row, col))
                if state:
                    if col == RESOLUTION_ID:
                        item.editingFinished.connect(self._on_resolutioID_changed)
                    if col == CAMERA_PX_SIZE:
                        item.editingFinished.connect(self._on_camera_px_size_changed)
                    if col == MAGNIFICATION:
                        item.editingFinished.connect(self._on_magnification_changed)
                    if col == IMAGE_PX_SIZE:
                        item.editingFinished.connect(self._on_image_px_size_changed)
                else:
                    with contextlib.suppress(TypeError):
                        if col == RESOLUTION_ID:
                            item.editingFinished.disconnect(
                                self._on_resolutioID_changed
                            )
                        if col == CAMERA_PX_SIZE:
                            item.editingFinished.disconnect(
                                self._on_camera_px_size_changed
                            )
                        if col == MAGNIFICATION:
                            item.editingFinished.disconnect(
                                self._on_magnification_changed
                            )
                        if col == IMAGE_PX_SIZE:
                            item.editingFinished.disconnect(
                                self._on_image_px_size_changed
                            )

    def _is_read_only(self, col: int) -> bool:
        if col == MAGNIFICATION:
            return self.mag_radiobtn.isChecked()  # type: ignore
        elif col == IMAGE_PX_SIZE:
            return self.img_px_radiobtn.isChecked()  # type: ignore
        else:
            return False

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

    def _update_mag(self, value: float) -> None:
        for row in range(self.table.rowCount()):
            image_px_size = self.table.cellWidget(row, IMAGE_PX_SIZE).text()
            if f"{value:.4f}" == image_px_size:
                camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE).text()
                mag = self.table.cellWidget(row, MAGNIFICATION)
                _mag = self._calculate_magnification(camera_px_size, image_px_size)
                mag.setText(f"{_mag:.1f}")

    def _on_resolutioID_changed(self) -> None:
        sender = self.sender()
        row = self.table.indexAt(sender.pos()).row()
        wdg = cast(QLineEdit, self.table.cellWidget(row, RESOLUTION_ID))
        wdg.focusNextChild()
        value = wdg.text()

        if value in self._mmc.getAvailablePixelSizeConfigs():

            if wdg.property("resID") == value:
                return

            wdg.setText("None")

            warnings.warn(
                f"There is already a configuration called '{value}'. "
                "Choose a different resolutionID."
            )
            with contextlib.suppress(ValueError):
                self._mmc.deletePixelSizeConfig(wdg.property("resID"))

            self.table._update_status()

            return

        else:
            camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE)
            image_px_size = self.table.cellWidget(row, IMAGE_PX_SIZE)
            mag = self.table.cellWidget(row, MAGNIFICATION)
            wdg.setProperty("resID", value)

            if self._is_read_only(IMAGE_PX_SIZE):
                _image_px_size = self._calculate_image_px_size(
                    camera_px_size.text(), mag.text()
                )
                image_px_size.setText(f"{_image_px_size:.4f}")

            elif self._is_read_only(MAGNIFICATION):
                _mag = self._calculate_magnification(
                    camera_px_size.text(), image_px_size.text()
                )
                self.table.cellWidget(row, MAGNIFICATION).setText(f"{_mag:.1f}")

            self._apply_changes(row)

    def _on_camera_px_size_changed(self) -> None:
        sender = self.sender()
        row = self.table.indexAt(sender.pos()).row()
        wdg = self.table.cellWidget(row, CAMERA_PX_SIZE)
        wdg.focusNextChild()
        value = wdg.text()

        for r in range(self.table.rowCount()):
            self.table.cellWidget(r, CAMERA_PX_SIZE).setText(f"{float(value):.2f}")

            mag = self.table.cellWidget(r, MAGNIFICATION)
            image_px_size = self.table.cellWidget(r, IMAGE_PX_SIZE)

            if self._is_read_only(MAGNIFICATION):
                _mag = self._calculate_magnification(value, image_px_size.text())
                self.table.cellWidget(r, MAGNIFICATION).setText(f"{_mag:.1f}")

            elif self._is_read_only(IMAGE_PX_SIZE):
                _image_px_size = self._calculate_image_px_size(value, mag.text())
                self.table.cellWidget(r, IMAGE_PX_SIZE).setText(f"{_image_px_size:.4f}")

            self._apply_changes(r)

    def _on_magnification_changed(self) -> None:
        sender = self.sender()
        row = self.table.indexAt(sender.pos()).row()
        wdg = self.table.cellWidget(row, MAGNIFICATION)
        wdg.focusNextChild()
        value = wdg.text()
        camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE)

        if self._is_read_only(IMAGE_PX_SIZE):
            _image_px_size = self._calculate_image_px_size(camera_px_size.text(), value)
            self.table.cellWidget(row, IMAGE_PX_SIZE).setText(f"{_image_px_size:.4f}")

        self._apply_changes(row)

    def _on_image_px_size_changed(self) -> None:
        sender = self.sender()
        row = self.table.indexAt(sender.pos()).row()
        value = self.table.cellWidget(row, IMAGE_PX_SIZE).text()
        wdg = self.table.cellWidget(row, RESOLUTION_ID)
        wdg.setFocus()
        camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE)

        if self._is_read_only(MAGNIFICATION):
            _mag = self._calculate_magnification(camera_px_size.text(), value)
            self.table.cellWidget(row, MAGNIFICATION).setText(f"{_mag:.1f}")

        self._apply_changes(row)

    def _apply_changes(self, row: int) -> None:
        obj_label = self.table.item(row, OBJECTIVE_LABEL).text()
        resolutionID = self.table.cellWidget(row, RESOLUTION_ID).text()
        px_size_um = float(self.table.cellWidget(row, IMAGE_PX_SIZE).text())

        with block_core(self._mmc.events):
            self._delete_if_exist(resolutionID, obj_label)
            self._mmc.definePixelSizeConfig(
                resolutionID, self.objective_device, "Label", obj_label  # type: ignore # noqa: E501
            )
            self._mmc.setPixelSizeUm(resolutionID, px_size_um)

        if "None" in self._mmc.getAvailablePixelSizeConfigs():
            with block_core(self._mmc.events):
                self._mmc.deletePixelSizeConfig("None")

        self.table._update_status()

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
