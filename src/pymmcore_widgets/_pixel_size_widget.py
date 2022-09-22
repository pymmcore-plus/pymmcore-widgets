import itertools
import re
from typing import Any, List, Optional, Tuple

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from superqt.utils import signals_blocked

from ._objective_widget import ObjectivesWidget

OBJECTIVE_LABEL = 0
RESOLUTION_ID = 1
CAMERA_PX_SIZE = 2
MAGNIFICATION = 3
IMAGE_PX_SIZE = 4


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
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(
            [
                "Objective",
                "ResolutionID",
                "Camera Pixel Size (µm)",
                "Magnification",
                "Image Pixel Size (µm)",
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

        self._on_sys_cfg_loaded()

    def _create_wdg(self) -> None:
        main_layout = QtW.QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setAlignment(Qt.AlignCenter)
        self.setLayout(main_layout)

        wdg = QtW.QGroupBox()
        layout = QtW.QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
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
        self.table.setCellWidget(row, 5, wdg)

    def _create_radiobtn_wdg(self) -> QtW.QWidget:
        self.rbt_wdg = QtW.QWidget()
        layout = QtW.QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
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

    def _update_status(self, row: int) -> None:
        resolutionID = self.table.cellWidget(row, RESOLUTION_ID).text()
        px_size = float(self.table.cellWidget(row, IMAGE_PX_SIZE).text())

        if resolutionID in self._mmc.getAvailablePixelSizeConfigs() and px_size > 0.0:
            opacity = 1.00
        else:
            opacity = 0.50

        for c in range(1, self.table.columnCount() - 1):
            op = QtW.QGraphicsOpacityEffect()
            item = self.table.cellWidget(row, c)
            op.setOpacity(opacity)
            item.setGraphicsEffect(op)
            item.setAutoFillBackground(True)

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
            red_id_item = self.table.cellWidget(idx, RESOLUTION_ID)
            red_id_item.setProperty("resID", red_id_item.text())

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
            self._update_status(idx)

        self._update_wdg_size()

    def _get_px_info(self) -> List[Tuple[str, str, float]]:
        obj_cfg_px = []
        for cfg in self._mmc.getAvailablePixelSizeConfigs():
            obj = list(self._mmc.getPixelSizeConfigData(cfg))[0][2]
            px_value = self._mmc.getPixelSizeUmByID(cfg)
            obj_cfg_px.append((obj, cfg, px_value))
        return obj_cfg_px

    def _set_item_in_table(self, row: int, col: int, value: Any) -> None:
        item = QtW.QLineEdit(text=str(value))
        item.setProperty("row", row)
        item.setProperty("col", col)
        item.setAlignment(Qt.AlignCenter)
        item.setFrame(False)
        if self._is_read_only(col):
            item.setReadOnly(True)
            item.setStyleSheet("color:magenta")
        else:
            item.setReadOnly(False)
            item.setStyleSheet("")

        item.editingFinished.connect(self._on_text_changed)
        self.table.setCellWidget(row, col, item)

    def _on_text_changed(self) -> None:
        try:
            row = self.sender().property("row")
            col = self.sender().property("col")
            item = self.table.cellWidget(row, col)
        except AttributeError:
            return
        item.focusNextChild()
        self._on_cell_changed(row, col)

    def _on_px_defined(
        self, resolutionID: str, deviceLabel: str, propName: str, objective: str
    ) -> None:

        match = self.table.findItems(objective, Qt.MatchExactly)
        row = match[0].row()

        # if there is a resolutionID with the same objective, do nothing.
        resID_objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        res_ID_item = self.table.cellWidget(row, RESOLUTION_ID)

        if objective == resID_objective and res_ID_item.text() == "None":
            return

        with signals_blocked(res_ID_item):
            self.table.cellWidget(row, RESOLUTION_ID).setText(resolutionID)

    def _on_px_set(self, resolutionID: str, pixSize: float) -> None:

        objective = list(self._mmc.getPixelSizeConfigData(resolutionID))[0][2]
        match = self.table.findItems(objective, Qt.MatchExactly)
        row = match[0].row()

        res_ID_item = self.table.cellWidget(row, RESOLUTION_ID)
        img_px_item = self.table.cellWidget(row, IMAGE_PX_SIZE)
        cam_px_item = self.table.cellWidget(row, CAMERA_PX_SIZE)
        mag_item = self.table.cellWidget(row, MAGNIFICATION)

        with signals_blocked(res_ID_item):
            res_ID_item.setText(resolutionID)
        with signals_blocked(img_px_item):
            img_px_item.setText(str(pixSize))

        mag = self._calculate_magnification(cam_px_item.text(), str(pixSize))
        with signals_blocked(mag_item):
            mag_item.setText(str(mag))

        self._update_status(row)

    def _on_px_deleted(self, resolutionID: str) -> None:
        row = -1
        for r in range(self.table.rowCount()):
            res_id_item = self.table.cellWidget(r, RESOLUTION_ID)
            im_px_item = self.table.cellWidget(r, IMAGE_PX_SIZE)
            if res_id_item.text() == resolutionID:
                with signals_blocked(res_id_item):
                    res_id_item.setText("None")
                with signals_blocked(im_px_item):
                    im_px_item.setText("0.0")
                row = r
                break
        if row >= 0:
            self._update_status(row)

    def _on_mag_toggle(self, state: bool) -> None:
        self._enable_column(MAGNIFICATION, not state)

    def _on_img_toggle(self, state: bool) -> None:
        self._enable_column(IMAGE_PX_SIZE, not state)

    def _enable_column(self, column: int, enable: bool) -> None:
        with signals_blocked(self.table):
            for row in range(self.table.rowCount()):
                item = self.table.cellWidget(row, column)
                if enable:
                    item.setReadOnly(False)
                    item.setStyleSheet("")
                else:
                    item.setReadOnly(True)
                    item.setStyleSheet("color:magenta")
                self._update_status(row)

    def _delete_cfg(self) -> None:
        row = self.sender().property("row")
        res_ID_item = self.table.cellWidget(row, RESOLUTION_ID)
        if res_ID_item.text() not in self._mmc.getAvailablePixelSizeConfigs():
            with signals_blocked(res_ID_item):
                res_ID_item.setText("None")
            im_px_item = self.table.cellWidget(row, IMAGE_PX_SIZE)
            with signals_blocked(im_px_item):
                im_px_item.setText("0.0")
            return
        self._mmc.deletePixelSizeConfig(res_ID_item.text())

    def _on_cell_changed(self, row: int, col: int) -> None:
        objective_label = self.table.item(row, OBJECTIVE_LABEL)
        resolutionID = self.table.cellWidget(row, RESOLUTION_ID)
        mag = self.table.cellWidget(row, MAGNIFICATION)
        camera_px_size = self.table.cellWidget(row, CAMERA_PX_SIZE)
        image_px_size = self.table.cellWidget(row, IMAGE_PX_SIZE)

        if col == RESOLUTION_ID:
            self._on_resolutioID_changed(
                row, objective_label, resolutionID, camera_px_size, image_px_size, mag
            )

        elif col == CAMERA_PX_SIZE:
            self._on_camera_px_size_changed(row, camera_px_size, image_px_size, mag)

        elif col == MAGNIFICATION:
            self._on_magnification_changed(row, camera_px_size, image_px_size, mag)

        elif col == IMAGE_PX_SIZE:
            self._on_image_px_size_changed(row, camera_px_size, image_px_size, mag)

        else:
            return

        if resolutionID.text() == "None":
            return

        self._apply_changes(row)

    def _on_resolutioID_changed(
        self,
        row: int,
        objective_label: QtW.QTableWidgetItem,
        resolutionID: QtW.QWidget,
        camera_px_size: QtW.QWidget,
        image_px_size: QtW.QWidget,
        mag: QtW.QWidget,
    ) -> None:
        if resolutionID.text() in self._mmc.getAvailablePixelSizeConfigs():

            if resolutionID.property("resID") == resolutionID.text():
                return

            # get current resolutionID name
            _id = "None"
            for cfg in self._mmc.getAvailablePixelSizeConfigs():
                cfg_data = list(itertools.chain(*self._mmc.getPixelSizeConfigData(cfg)))
                if objective_label.text() in cfg_data:
                    _id = cfg
                    break

            with signals_blocked(resolutionID):
                resolutionID.setText(_id)
                resolutionID.setProperty("resID", _id)

            raise ValueError(
                f"There is already a configuration called '{resolutionID.text()}'. "
                "Choose a different resolutionID."
            )

        elif self._is_read_only(IMAGE_PX_SIZE):
            resolutionID.setProperty("resID", resolutionID.text())
            _image_px_size = self._calculate_image_px_size(
                camera_px_size.text(), mag.text()
            )
            with signals_blocked(image_px_size):
                self.table.cellWidget(row, IMAGE_PX_SIZE).setText(str(_image_px_size))

        elif self._is_read_only(MAGNIFICATION):
            resolutionID.setProperty("resID", resolutionID.text())
            _mag = self._calculate_magnification(
                camera_px_size.text(), image_px_size.text()
            )
            with signals_blocked(mag):
                self.table.cellWidget(row, MAGNIFICATION).setText(str(_mag))

    def _on_camera_px_size_changed(
        self,
        row: int,
        camera_px_size: QtW.QWidget,
        image_px_size: QtW.QWidget,
        mag: QtW.QWidget,
    ) -> None:

        if self._is_read_only(MAGNIFICATION):
            _mag = self._calculate_magnification(
                camera_px_size.text(), image_px_size.text()
            )
            with signals_blocked(mag):
                self.table.cellWidget(row, MAGNIFICATION).setText(str(_mag))

        elif self._is_read_only(IMAGE_PX_SIZE):
            _image_px_size = self._calculate_image_px_size(
                camera_px_size.text(), mag.text()
            )
            with signals_blocked(image_px_size):
                self.table.cellWidget(row, IMAGE_PX_SIZE).setText(str(_image_px_size))

        self._update_cam_px_size(camera_px_size.text())

    def _on_magnification_changed(
        self,
        row: int,
        camera_px_size: QtW.QWidget,
        image_px_size: QtW.QWidget,
        mag: QtW.QWidget,
    ) -> None:

        if self._is_read_only(IMAGE_PX_SIZE):
            _image_px_size = self._calculate_image_px_size(
                camera_px_size.text(), mag.text()
            )
            with signals_blocked(image_px_size):
                self.table.cellWidget(row, IMAGE_PX_SIZE).setText(str(_image_px_size))

    def _on_image_px_size_changed(
        self,
        row: int,
        camera_px_size: QtW.QWidget,
        image_px_size: QtW.QWidget,
        mag: QtW.QWidget,
    ) -> None:

        if self._is_read_only(MAGNIFICATION):
            _mag = self._calculate_magnification(
                camera_px_size.text(), image_px_size.text()
            )
            with signals_blocked(mag):
                self.table.cellWidget(row, MAGNIFICATION).setText(str(_mag))

    def _apply_changes(self, row: int) -> None:
        obj_label = self.table.item(row, OBJECTIVE_LABEL).text()
        resolutionID = self.table.cellWidget(row, RESOLUTION_ID).text()
        mag = float(self.table.cellWidget(row, MAGNIFICATION).text())
        self._camera_pixel_size = float(
            self.table.cellWidget(row, CAMERA_PX_SIZE).text()
        )
        px_size_um = float(self.table.cellWidget(row, IMAGE_PX_SIZE).text())

        self._update_magnification_list(obj_label, mag)
        self._delete_if_exist(resolutionID, obj_label)
        self._define_and_set_px(resolutionID, obj_label, px_size_um)

        self._update_status(row)

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
            cpx = self.table.cellWidget(r, CAMERA_PX_SIZE).text()
            if cpx == value:
                continue
            self.table.cellWidget(r, CAMERA_PX_SIZE).setText(str(value))
            self._on_cell_changed(r, CAMERA_PX_SIZE)

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
