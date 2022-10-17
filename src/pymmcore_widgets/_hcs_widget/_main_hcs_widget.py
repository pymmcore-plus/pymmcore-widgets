from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import yaml  # type: ignore
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import PMDAEngine
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush
from qtpy.QtWidgets import QTableWidgetItem, QWidget
from superqt.utils import signals_blocked
from useq import MDASequence

from ._graphics_items import FOVPoints, Well
from ._main_hcs_gui import HCSGui
from ._update_yaml_widget import UpdateYaml
from ._well_plate_database import WellPlate

PLATE_DATABASE = Path(__file__).parent / "_well_plate.yaml"
AlignCenter = Qt.AlignmentFlag.AlignCenter


class HCSWidget(HCSGui):
    """Main HCS widget."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self.wp: WellPlate = None  # type: ignore

        # connect
        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.events.mdaEngineRegistered.connect(self._update_mda_engine)

        self.wp_combo.currentTextChanged.connect(self._on_combo_changed)
        self.custom_plate.clicked.connect(self._update_plate_yaml)
        self.clear_button.clicked.connect(self.scene._clear_selection)
        self.run_Button.clicked.connect(self._on_run_clicked)
        self.pause_Button.released.connect(lambda: self._mmc.mda.toggle_pause())
        self.cancel_Button.released.connect(lambda: self._mmc.mda.cancel())
        self.calibration.PlateFromCalibration.connect(self._on_plate_from_calibration)
        self.ch_and_pos_list.position_list_button.clicked.connect(
            self._generate_pos_list
        )

        self._update_wp_combo()

    def _on_sys_cfg(self) -> None:
        self._on_combo_changed(self.wp_combo.currentText())

    def _update_wp_combo(self) -> None:
        plates = self._plates_names_from_database()
        plates.sort()
        self.wp_combo.clear()
        self.wp_combo.addItems(plates)

    def _plates_names_from_database(self) -> list:
        with open(
            PLATE_DATABASE,
        ) as file:
            return list(yaml.safe_load(file))

    def _on_combo_changed(self, value: str) -> None:
        print("_on_combo_changed")
        self.scene.clear()
        self._draw_well_plate(value)
        self.calibration._update_gui(value)

    def _on_plate_from_calibration(self, coords: Tuple) -> None:

        x_list = [x[0] for x in [*coords]]
        y_list = [y[1] for y in [*coords]]
        x_max, x_min = (max(x_list), min(x_list))
        y_max, y_min = (max(y_list), min(y_list))

        width_mm = (x_max - x_min) / 1000
        height_mm = (y_max - y_min) / 1000

        with open(PLATE_DATABASE) as file:
            f = yaml.safe_load(file)
            f.pop("_from calibration")

        with open(PLATE_DATABASE, "w") as file:
            new = {
                "_from calibration": {
                    "circular": False,
                    "id": "_from calibration",
                    "cols": 1,
                    "rows": 1,
                    "well_size_x": width_mm,
                    "well_size_y": height_mm,
                    "well_spacing_x": 0,
                    "well_spacing_y": 0,
                }
            }
            f.update(new)
            yaml.dump(f, file)

        self.scene.clear()
        self._draw_well_plate("_from calibration")

    def _draw_well_plate(self, well_plate: str) -> None:
        print("_draw_well_plate ->", well_plate)
        self.wp = WellPlate.set_format(well_plate)

        max_w = self._width - 10
        max_h = self._height - 10
        start_y = 0.0

        if self.wp.rows == 1 and self.wp.cols > 1:
            size_x = max_w / self.wp.cols
            size_y = size_x
            start_y = (max_h / 2) - (size_y / 2)

        elif self.wp.cols == 1 and self.wp.rows > 1:
            size_y = max_h / self.wp.rows
            size_x = size_y

        else:
            size_y = max_h / self.wp.rows
            size_x = (
                size_y
                if (self.wp.circular or self.wp.well_size_x == self.wp.well_size_y)
                else (max_w / self.wp.cols)
            )
        text_size = size_y / 3  # 2.3

        width = size_x * self.wp.cols

        if width != self.scene.width() and self.scene.width() > 0:
            start_x = (self.scene.width() - width) / 2
            start_x = max(start_x, 0)
        else:
            start_x = 0

        self._create_well_plate(
            self.wp.rows,
            self.wp.cols,
            start_x,
            start_y,
            size_x,
            size_y,
            text_size,
            self.wp.circular,
        )

        # select the plate area if is not a multi well
        items = self.scene.items()
        if len(items) == 1:
            item = items[0]
            item.setSelected(True)
            item._setBrush(QBrush(Qt.magenta))

        self.FOV_selector._load_plate_info(
            self.wp.well_size_x, self.wp.well_size_y, self.wp.circular
        )

    def _create_well_plate(
        self,
        rows: int,
        cols: int,
        start_x: float,
        start_y: float,
        size_x: float,
        size_y: float,
        text_size: float,
        circular: bool,
    ) -> None:
        x = start_x
        y = start_y
        for row in range(rows):
            for col in range(cols):
                self.scene.addItem(
                    Well(x, y, size_x, size_y, row, col, text_size, circular)
                )
                x += size_x
            y += size_y
            x = start_x

    def _update_plate_yaml(self) -> None:
        self.plate = UpdateYaml(self)
        self.plate.yamlUpdated.connect(
            self._update_wp_combo_from_yaml
        )  # UpdateYaml() signal
        self.plate.show()
        self._clear_values()

    def _clear_values(self) -> None:
        self.plate._circular_checkbox.setChecked(False),
        self.plate._id.setText("")
        self.plate._cols.setValue(0)
        self.plate._rows.setValue(0)
        self.plate._well_size_x.setValue(0.0)
        self.plate._well_size_y.setValue(0.0)
        self.plate._well_spacing_x.setValue(0.0)
        self.plate._well_spacing_y.setValue(0.0)

    def _update_wp_combo_from_yaml(self, new_plate: dict) -> None:
        plates = self._plates_names_from_database()
        plates.sort()
        with signals_blocked(self.wp_combo):
            self.wp_combo.clear()
            self.wp_combo.addItems(plates)
        if new_plate:
            value = list(new_plate.keys())[0]
            self.wp_combo.setCurrentText(value)
            self._on_combo_changed(value)
        else:
            items = [self.wp_combo.itemText(i) for i in range(self.wp_combo.count())]
            self.wp_combo.setCurrentText(items[0])
            self._on_combo_changed(items[0])

    def _generate_pos_list(self) -> None:

        if not self.calibration.is_calibrated:
            raise ValueError("Plate not calibrated! Calibrate it first.")

        if not self._mmc.getPixelSizeUm():
            raise ValueError("Pixel Size not defined! Set pixel size first.")

        well_list = self.scene._get_plate_positions()

        if not well_list:
            raise ValueError("No Well selected! Select at least one well first.")

        self.ch_and_pos_list._clear_positions()

        plate_info = self.wp.getAllInfo()

        ordered_wells_list = self._get_wells_stage_coords(well_list, plate_info)

        ordered_wells_and_fovs_list = self._get_well_and_fovs_position_list(
            plate_info, ordered_wells_list
        )

        for r, f in enumerate(ordered_wells_and_fovs_list):
            well_name, stage_coord_x, stage_coord_y = f
            self._add_to_table(r, well_name, stage_coord_x, stage_coord_y)

    def _get_wells_stage_coords(
        self, well_list: List[Tuple[str, int, int]], plate_info: dict
    ) -> List[Tuple[str, float, float]]:
        # center stage coords of calibrated well a1
        a1_x = self.calibration.A1_well[1]
        a1_y = self.calibration.A1_well[2]
        center = np.array([[a1_x], [a1_y]])
        r_matrix = self.calibration.plate_rotation_matrix

        # distance between wells from plate database (mm)
        x_step, y_step = plate_info.get("well_distance")  # type: ignore

        ordered_well_list = []
        original_pos_list = []
        for pos in well_list:
            well, row, col = pos
            # find center stage coords for all the selected wells
            if well == "A1":
                x = a1_x
                y = a1_y
                original_pos_list.append((x, y))

            else:
                x = a1_x + ((x_step * 1000) * col)
                y = a1_y - ((y_step * 1000) * row)
                original_pos_list.append((x, y))

                if r_matrix is not None:

                    coords = [[x], [y]]

                    transformed = np.linalg.inv(r_matrix).dot(coords - center) + center

                    x_rotated, y_rotated = transformed
                    x = x_rotated[0]
                    y = y_rotated[0]

            ordered_well_list.append((well, x, y))

        return ordered_well_list

    def _get_well_and_fovs_position_list(
        self, plate_info: dict, ordered_wells_list: List[Tuple[str, float, float]]
    ) -> List[Tuple[str, float, float]]:

        fovs = [
            item._getPositionsInfo()
            for item in self.FOV_selector.scene.items()
            if isinstance(item, FOVPoints)
        ]
        fovs.reverse()

        # center coord in px (of QGraphicsView))
        cx = 100
        cy = 100

        pos_list = []
        # well dimensions from database (mm)
        well_x, well_y = plate_info.get("well_size")  # type: ignore
        # well dimensions from database (um)
        well_x_um = well_x * 1000
        well_y_um = well_y * 1000

        for pos in ordered_wells_list:
            well_name, center_stage_x, center_stage_y = pos

            for idx, fov in enumerate(fovs):
                # center fov scene x, y coord fx and fov scene width and height
                (
                    center_fov_scene_x,
                    center_fov_scene_y,
                    w_fov_scene,
                    h_fov_scene,
                ) = fov

                # find 1 px value in um depending on well dimension
                px_val_x = well_x_um / w_fov_scene  # µm
                px_val_y = well_y_um / h_fov_scene  # µm

                # shift point coords in scene when center is (0, 0)
                new_fx = center_fov_scene_x - cx
                new_fy = center_fov_scene_y - cy

                # find stage coords of fov point
                stage_coord_x = center_stage_x + (new_fx * px_val_x)
                stage_coord_y = center_stage_y + (new_fy * px_val_y)
                pos_list.append(
                    (f"{well_name}_pos{idx:03d}", stage_coord_x, stage_coord_y)
                )

        return pos_list

    def _add_to_table(
        self, row: int, well_name: str, stage_coord_x: float, stage_coord_y: float
    ) -> None:

        self._add_position_row()
        name = QTableWidgetItem(well_name)
        name.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
        self.ch_and_pos_list.stage_tableWidget.setItem(row, 0, name)
        stage_x = QTableWidgetItem(str(stage_coord_x))
        stage_x.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
        self.ch_and_pos_list.stage_tableWidget.setItem(row, 1, stage_x)
        stage_y = QTableWidgetItem(str(stage_coord_y))
        stage_y.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
        self.ch_and_pos_list.stage_tableWidget.setItem(row, 2, stage_y)

        if self.ch_and_pos_list.z_combo.currentText() != "None":
            selected_z_stage = self.ch_and_pos_list.z_combo.currentText()
            z_pos = self._mmc.getPosition(selected_z_stage)
            item = QTableWidgetItem(str(z_pos))
            item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
            self.ch_and_pos_list.stage_tableWidget.setItem(row, 3, item)

    def _add_position_row(self) -> int:
        idx = self.ch_and_pos_list.stage_tableWidget.rowCount()
        self.ch_and_pos_list.stage_tableWidget.insertRow(idx)
        return int(idx)

    def _get_state(self) -> MDASequence:
        ch_table = self.ch_and_pos_list.channel_tableWidget
        state = {
            "axis_order": self.acquisition_order_comboBox.currentText(),
            "channels": [
                {
                    "config": ch_table.cellWidget(c, 0).currentText(),
                    "group": self._mmc.getChannelGroup() or "Channel",
                    "exposure": ch_table.cellWidget(c, 1).value(),
                }
                for c in range(ch_table.rowCount())
            ],
            "time_plan": None,
            "z_plan": None,
            "stage_positions": [],
        }

        if self.ch_and_pos_list.time_groupBox.isChecked():
            unit = {"min": "minutes", "sec": "seconds", "ms": "milliseconds"}[
                self.ch_and_pos_list.time_comboBox.currentText()
            ]
            state["time_plan"] = {
                "interval": {unit: self.ch_and_pos_list.interval_spinBox.value()},
                "loops": self.ch_and_pos_list.timepoints_spinBox.value(),
            }

        if self.ch_and_pos_list.stack_group.isChecked():

            if self.ch_and_pos_list.z_tabWidget.currentIndex() == 0:
                state["z_plan"] = {
                    "range": self.ch_and_pos_list.zrange_spinBox.value(),
                    "step": self.ch_and_pos_list.step_size_doubleSpinBox.value(),
                }
            elif self.ch_and_pos_list.z_tabWidget.currentIndex() == 1:
                state["z_plan"] = {
                    "above": self.ch_and_pos_list.above_doubleSpinBox.value(),
                    "below": self.ch_and_pos_list.below_doubleSpinBox.value(),
                    "step": self.ch_and_pos_list.step_size_doubleSpinBox.value(),
                }

        for r in range(self.ch_and_pos_list.stage_tableWidget.rowCount()):
            pos = {
                "name": self.ch_and_pos_list.stage_tableWidget.item(r, 0).text(),
                "x": float(self.ch_and_pos_list.stage_tableWidget.item(r, 1).text()),
                "y": float(self.ch_and_pos_list.stage_tableWidget.item(r, 2).text()),
            }
            if self.ch_and_pos_list.z_combo.currentText() != "None":
                pos["z"] = float(
                    self.ch_and_pos_list.stage_tableWidget.item(r, 3).text()
                )
            state["stage_positions"].append(pos)

        return MDASequence(**state)

    def _update_mda_engine(self, newEngine: PMDAEngine, oldEngine: PMDAEngine) -> None:
        oldEngine.events.sequenceStarted.disconnect(self._on_mda_started)
        oldEngine.events.sequenceFinished.disconnect(self._on_mda_finished)
        oldEngine.events.sequencePauseToggled.disconnect(self._on_mda_paused)

        newEngine.events.sequenceStarted.connect(self._on_mda_started)
        newEngine.events.sequenceFinished.connect(self._on_mda_finished)
        newEngine.events.sequencePauseToggled.connect(self._on_mda_paused)

    def _on_mda_started(self) -> None:
        self.pause_Button.show()
        self.cancel_Button.show()
        self.run_Button.hide()

    def _on_mda_paused(self, paused: bool) -> None:
        self.pause_Button.setText("Go" if paused else "Pause")

    def _on_mda_finished(self) -> None:
        self.pause_Button.hide()
        self.cancel_Button.hide()
        self.run_Button.show()

    def _on_run_clicked(self) -> None:

        if len(self._mmc.getLoadedDevices()) < 2:
            raise ValueError("Load a cfg file first.")

        if self.ch_and_pos_list.channel_tableWidget.rowCount() <= 0:
            raise ValueError("Select at least one channel.")

        if self.ch_and_pos_list.stage_tableWidget.rowCount() <= 0:
            raise ValueError("Select at least one position.")

        experiment = self._get_state()

        self._mmc.run_mda(experiment)  # run the MDA experiment asynchronously
        return
