from pathlib import Path
from typing import Optional

from fonticon_mdi6 import MDI6
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QComboBox,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from ._calibration_widget import PlateCalibration
from ._generate_fov_widget import SelectFOV
from ._hcs_mda_widget import MDAWidget
from ._plate_graphics_scene_widget import GraphicsScene

PLATE_DATABASE = Path(__file__).parent / "_well_plate.yaml"
AlignCenter = Qt.AlignmentFlag.AlignCenter


class HCSGui(QWidget):
    """Main GUI for the HSC plugin."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        lbl = self._create_label()
        layout.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(AlignCenter)
        self.tabwidget = self._add_tab_wdg()
        scroll.setWidget(self.tabwidget)

        layout.insertWidget(0, scroll)

        bottom_wdg = self._create_bottom_wdg()
        layout.addWidget(bottom_wdg)

    def _add_tab_wdg(self) -> QTabWidget:

        tab = QTabWidget()
        tab.setTabPosition(QTabWidget.West)

        select_plate_tab = self._create_plate_and_fov_tab()
        calibration = self._create_calibration_tab()
        self.ch_and_pos_list = MDAWidget(parent=self)

        tab.addTab(select_plate_tab, "  Plate and FOVs Selection  ")
        tab.addTab(calibration, "  Plate Calibration  ")
        tab.addTab(self.ch_and_pos_list, "  Channel and Positions List  ")

        return tab

    def _create_plate_and_fov_tab(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(20)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        self.scene = GraphicsScene()
        self.view = QGraphicsView(self.scene, self)
        self.view.setStyleSheet("background:grey;")
        self._width = 500
        self._height = 300
        self.view.setMinimumSize(self._width, self._height)

        # well plate selector combo and clear selection QPushButton
        upper_wdg = QWidget()
        upper_wdg_layout = QHBoxLayout()
        wp_combo_wdg = self._create_wp_combo_selector()
        self.custom_plate = QPushButton(text="Custom Plate")
        self.clear_button = QPushButton(text="Clear Selection")
        upper_wdg_layout.addWidget(wp_combo_wdg)
        upper_wdg_layout.addWidget(self.custom_plate)
        upper_wdg_layout.addWidget(self.clear_button)
        upper_wdg.setLayout(upper_wdg_layout)

        self.FOV_selector = SelectFOV()

        # add widgets
        view_group = QGroupBox()
        view_group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        view_gp_layout = QVBoxLayout()
        view_gp_layout.setSpacing(0)
        view_gp_layout.setContentsMargins(10, 10, 10, 10)
        view_group.setLayout(view_gp_layout)
        view_gp_layout.addWidget(upper_wdg)
        view_gp_layout.addWidget(self.view)
        wdg_layout.addWidget(view_group)

        FOV_group = QGroupBox()
        FOV_group.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        FOV_gp_layout = QVBoxLayout()
        FOV_gp_layout.setSpacing(0)
        FOV_gp_layout.setContentsMargins(10, 10, 10, 10)
        FOV_group.setLayout(FOV_gp_layout)
        FOV_gp_layout.addWidget(self.FOV_selector)
        wdg_layout.addWidget(FOV_group)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        wdg_layout.addItem(verticalSpacer)

        return wdg

    def _create_calibration_tab(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(20)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        cal_group = QGroupBox()
        cal_group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        cal_group_layout = QVBoxLayout()
        cal_group_layout.setSpacing(0)
        cal_group_layout.setContentsMargins(10, 20, 10, 10)
        cal_group.setLayout(cal_group_layout)
        self.calibration = PlateCalibration()
        cal_group_layout.addWidget(self.calibration)
        wdg_layout.addWidget(cal_group)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        wdg_layout.addItem(verticalSpacer)

        return wdg

    def _create_bottom_wdg(self) -> QWidget:
        wdg = QWidget()
        wdg.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        wdg_layout = QHBoxLayout()
        wdg_layout.setAlignment(Qt.AlignVCenter)
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(10, 5, 10, 10)
        wdg.setLayout(wdg_layout)

        acq_wdg = QWidget()
        acq_wdg_layout = QHBoxLayout()
        acq_wdg_layout.setSpacing(0)
        acq_wdg_layout.setContentsMargins(0, 0, 0, 0)
        acq_wdg.setLayout(acq_wdg_layout)
        acquisition_order_label = QLabel(text="Acquisition Order:")
        lbl_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        acquisition_order_label.setSizePolicy(lbl_sizepolicy)
        self.acquisition_order_comboBox = QComboBox()
        self.acquisition_order_comboBox.setMinimumWidth(100)
        self.acquisition_order_comboBox.addItems(["tpzc", "tpcz", "ptzc", "ptcz"])
        acq_wdg_layout.addWidget(acquisition_order_label)
        acq_wdg_layout.addWidget(self.acquisition_order_comboBox)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        min_width = 100
        icon_size = 40
        self.run_Button = QPushButton(text="Run")
        self.run_Button.setMinimumWidth(min_width)
        self.run_Button.setStyleSheet("QPushButton { text-align: center; }")
        self.run_Button.setSizePolicy(btn_sizepolicy)
        self.run_Button.setIcon(icon(MDI6.play_circle_outline, color=(0, 255, 0)))
        self.run_Button.setIconSize(QSize(icon_size, icon_size))
        self.pause_Button = QPushButton("Pause")
        self.pause_Button.setMinimumWidth(min_width)
        self.pause_Button.setStyleSheet("QPushButton { text-align: center; }")
        self.pause_Button.setSizePolicy(btn_sizepolicy)
        self.pause_Button.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_Button.setIconSize(QSize(icon_size, icon_size))
        self.pause_Button.hide()
        self.cancel_Button = QPushButton("Cancel")
        self.cancel_Button.setMinimumWidth(min_width)
        self.cancel_Button.setStyleSheet("QPushButton { text-align: center; }")
        self.cancel_Button.setSizePolicy(btn_sizepolicy)
        self.cancel_Button.setIcon(icon(MDI6.stop_circle_outline, color="magenta"))
        self.cancel_Button.setIconSize(QSize(icon_size, icon_size))
        self.cancel_Button.hide()

        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Expanding)

        wdg_layout.addWidget(acq_wdg)
        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(self.run_Button)
        wdg_layout.addWidget(self.pause_Button)
        wdg_layout.addWidget(self.cancel_Button)

        return wdg

    def _create_label(self) -> QWidget:

        wdg = QWidget()
        wdg_lay = QHBoxLayout()
        wdg_lay.setSpacing(5)
        wdg_lay.setContentsMargins(10, 5, 10, 5)
        wdg_lay.setAlignment(Qt.AlignLeft)
        wdg.setLayout(wdg_lay)

        self._total_time_lbl = QLabel(text="TEST")
        self._total_time_lbl.setAlignment(Qt.AlignLeft)
        self._total_time_lbl.setSizePolicy(
            QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        )
        wdg_lay.addWidget(self._total_time_lbl)

        return wdg

    def _create_wp_combo_selector(self) -> QWidget:

        combo_wdg = QWidget()
        wp_combo_layout = QHBoxLayout()
        wp_combo_layout.setContentsMargins(0, 0, 0, 0)
        wp_combo_layout.setSpacing(0)

        combo_label = QLabel()
        combo_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        combo_label.setText("Plate:")
        combo_label.setMaximumWidth(75)

        self.wp_combo = QComboBox()

        wp_combo_layout.addWidget(combo_label)
        wp_combo_layout.addWidget(self.wp_combo)
        combo_wdg.setLayout(wp_combo_layout)

        return combo_wdg
