from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union, cast

from platformdirs import user_data_dir
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)
from useq import GridRowsColumns, MDASequence, Position, RandomPoints

from ._calibration_widget import CalibrationData, PlateCalibrationWidget
from ._fov_widget import Center, FOVSelectorWidget
from ._graphics_items import Well  # noqa: TCH001
from ._plate_model import DEFAULT_PLATE_DB_PATH, Plate, load_database, save_database
from ._plate_widget import PlateInfo, PlateSelectorWidget
from ._pydantic_model import FrozenModel
from ._util import apply_rotation_matrix, get_well_center, nearest_neighbor

EXPANDING = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
TOP_X: float = -10000000000
TOP_Y: float = 10000000000
# Path to the user data directory to store the plate database
USER_DATA_DIR = Path(user_data_dir(appname="pymmcore_widgets"))
USER_PLATE_DATABASE_PATH = USER_DATA_DIR / "plate_database.json"

AnyMode = Union[Center, GridRowsColumns, RandomPoints, None]


def _cast_mode(
    mode: dict | str | Center | GridRowsColumns | RandomPoints | None,
) -> AnyMode:
    """Get the grid type from the grid_plan."""
    if not mode:
        return None
    if isinstance(mode, str):
        mode = cast(AnyMode, MDASequence(grid_plan=json.loads(mode)).grid_plan)
    elif isinstance(mode, dict):
        mode = cast(AnyMode, MDASequence(grid_plan=mode).grid_plan)
    return mode


class HCSData(FrozenModel):
    """Store all the info needed to setup an HCS experiment.

    Attributes
    ----------
    plate : Plate
        The selected well plate. By default, None.
    wells : list[Well] | None
        The selected wells as Well object: Well(name, row, column). By default, None.
    mode : Center | RandomPoints | GridRowsColumns | None
        The mode used to select the FOVs. By default, None.
    calibration : CalibrationData | None
        The data necessary to calibrate the plate. By default, None.
    """

    plate: Optional[Plate] = None  # noqa: UP007
    wells: Optional[List[Well]] = None  # noqa: UP006, UP007
    mode: Union[Center, RandomPoints, GridRowsColumns, None] = None  # noqa: UP007
    calibration: Optional[CalibrationData] = None  # noqa: UP007
    positions: Optional[List[Position]] = None  # noqa: UP006, UP007


class PlatePage(QWizardPage):
    def __init__(
        self,
        plate_database_path: Path | str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setTitle("Plate and Well Selection")

        self._plate_widget = PlateSelectorWidget(
            plate_database_path=plate_database_path
        )

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._plate_widget)

        self.setButtonText(QWizard.WizardButton.NextButton, "Calibration >")

        self.combo = self._plate_widget.plate_combo

    def value(self) -> PlateInfo:
        """Return the selected well plate and the selected wells."""
        return self._plate_widget.value()

    def setValue(self, value: PlateInfo) -> None:
        """Set the current plate and the selected wells.

        `value` is a list of (well_name, row, column).
        """
        self._plate_widget.setValue(value)


class PlateCalibrationPage(QWizardPage):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self.setTitle("Plate Calibration")

        self._calibration = PlateCalibrationWidget(mmcore=mmcore)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._calibration)
        layout.addItem(QSpacerItem(0, 0, *EXPANDING))

        self.setButtonText(QWizard.WizardButton.NextButton, "FOVs >")

    def value(self) -> CalibrationData | None:
        """Return the calibration info."""
        return self._calibration.value()

    def setValue(self, value: CalibrationData | None) -> None:
        """Set the calibration info."""
        self._calibration.setValue(value)


class FOVSelectorPage(QWizardPage):
    def __init__(
        self,
        plate: Plate | None = None,
        mode: Center | RandomPoints | GridRowsColumns | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle("Field of View Selection")

        self._fov_widget = FOVSelectorWidget(plate, mode, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._fov_widget)
        layout.addItem(QSpacerItem(0, 0, *EXPANDING))

        self.setButtonText(QWizard.WizardButton.FinishButton, "Value")

    def value(
        self,
    ) -> tuple[Plate | None, Center | RandomPoints | GridRowsColumns | None]:
        """Return the list of FOVs."""
        return self._fov_widget.value()

    def setValue(
        self, plate: Plate | None, mode: Center | RandomPoints | GridRowsColumns | None
    ) -> None:
        """Set the list of FOVs."""
        self._fov_widget.setValue(plate, mode)


class HCSWizard(QWizard):
    """A wizard to setup an High Content experiment.

    This widget can be used to select a plate, calibrate it, and then select the FOVs
    to image in different modes (Center, RandomPoint or GridRowsColumns).

    Parameters
    ----------
    parent : QWidget | None
        The parent widget. By default, None.
    mmcore : CMMCorePlus | None
        The CMMCorePlus instance. By default, None.
    plate_database_path : Path | str | None
        The path to the plate database. By default, None.
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        plate_database_path: Path | str | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setWindowTitle("HCS Wizard")

        # add custom button to save
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        _save_btn = self.button(QWizard.WizardButton.CustomButton1)
        _save_btn.setText("Save")
        self.setButton(QWizard.WizardButton.CustomButton1, _save_btn)
        self.button(QWizard.WizardButton.CustomButton1).clicked.connect(self._save)
        # add custom button to load
        self.setOption(QWizard.WizardOption.HaveCustomButton2, True)
        _load_btn = self.button(QWizard.WizardButton.CustomButton2)
        _load_btn.setText("Load")
        self.setButton(QWizard.WizardButton.CustomButton2, _load_btn)
        self.button(QWizard.WizardButton.CustomButton2).clicked.connect(self._load)

        # layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 50, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # check if the default plate database exists, if not create it in the
        # user data directory. If the database is provided, use it without storing it
        # in the user data directory.
        if not plate_database_path:
            if not USER_PLATE_DATABASE_PATH.exists():
                USER_PLATE_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            save_database(
                load_database(DEFAULT_PLATE_DB_PATH), USER_PLATE_DATABASE_PATH
            )

        # setup plate page
        self.plate_page = PlatePage(plate_database_path or USER_PLATE_DATABASE_PATH)

        # get currently selected plate
        plate, _ = self.plate_page.value()

        # setup calibration page
        self.calibration_page = PlateCalibrationPage()
        self.calibration_page.setValue(CalibrationData(plate=plate))

        # setup fov page
        fov_w, fov_h = self._get_fov_size()
        mode = Center(x=0, y=0, fov_width=fov_w, fov_height=fov_h)
        self.fov_page = FOVSelectorPage(plate, mode)

        # add pages to wizard
        self.addPage(self.plate_page)
        self.addPage(self.calibration_page)
        self.addPage(self.fov_page)

        # connections
        self.plate_page.combo.currentTextChanged.connect(self._on_plate_combo_changed)
        self._mmc.events.pixelSizeChanged.connect(self._on_px_size_changed)
        self._mmc.events.systemConfigurationLoaded.connect(
            self._on_system_config_loaded
        )

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> HCSData:
        """Return the values of the wizard."""
        plate, well_list = self.plate_page.value()

        calibration_data = self.calibration_page.value()
        if calibration_data is not None:
            assert calibration_data.plate == plate

        fov_plate, mode = self.fov_page.value()
        assert fov_plate == plate

        positions = self.get_positions()

        return HCSData(
            plate=plate,
            wells=well_list,
            mode=mode,
            calibration=calibration_data,
            positions=positions,
        )

    def setValue(self, value: HCSData) -> None:
        """Set the values of the wizard."""
        plate = value.plate

        self.plate_page.setValue(PlateInfo(plate, value.wells))

        calibration = value.calibration
        if calibration is not None and calibration.plate != plate:
            calibration = calibration.replace(plate=plate)
        self.calibration_page.setValue(value.calibration)

        mode = value.mode
        if mode is None:
            w = (self._mmc.getImageWidth() * self._mmc.getPixelSizeUm()) or None
            h = (self._mmc.getImageHeight() * self._mmc.getPixelSizeUm()) or None
            mode = Center(x=0, y=0, fov_width=w, fov_height=h)

        self.fov_page.setValue(value.plate, mode)

    def save_database(self, database_path: Path | str) -> None:
        """Save the current plate database to a json file."""
        self.plate_page._plate_widget.save_database(database_path)

    def load_database(self, database_path: Path | str | None = None) -> None:
        """Load a plate database. If None, a dialog will open to select a file."""
        self.plate_page._plate_widget.load_database(database_path)

    def database_path(self) -> str:
        """Return the path to the current plate database."""
        return self.plate_page._plate_widget.database_path()

    def database(self) -> dict[str, Plate]:
        """Return the current plate database."""
        return self.plate_page._plate_widget.database()

    def get_positions(self) -> list[Position] | None:
        """Return the list of FOVs as useq.Positions expressed in stage coordinates."""
        wells_centers = self._get_well_center_in_stage_coordinates()
        if wells_centers is None:
            return None
        return self._get_fovs_in_stage_coords(wells_centers)

    def accept(self) -> None:
        """Override QWizard default accept method."""
        self.valueChanged.emit(self.value())

    # _________________________PRIVATE METHODS_________________________ #

    def _save(self) -> None:
        """Save the current wizard values as a json file."""
        (path, _) = QFileDialog.getSaveFileName(
            self, "Save Plate Database", "", "json(*.json)"
        )

        if not path:
            return

        data = self.value().model_dump_json()
        Path(path).write_text(data)

    def _load(self) -> None:
        """Load a .json wizard configuration."""
        import json

        (path, _) = QFileDialog.getOpenFileName(
            self, "Load Plate Database", "", "json(*.json)"
        )

        if not path:
            return

        with open(Path(path)) as file:
            data = json.load(file)
            self.setValue(HCSData(**data))

    def _on_system_config_loaded(self) -> None:
        """Update the scene when the system configuration is loaded."""
        plate, _ = self.plate_page.value()
        self._update_wizard_pages(plate)

    def _on_plate_combo_changed(self, plate_id: str) -> None:
        db = self.database()
        plate = db[plate_id] if plate_id else None
        self._update_wizard_pages(plate)

    def _update_wizard_pages(self, plate: Plate | None) -> None:
        self.calibration_page.setValue(CalibrationData(plate=plate))
        fov_w, fov_h = self._get_fov_size()
        self.fov_page.setValue(
            plate, Center(x=0, y=0, fov_width=fov_w, fov_height=fov_h)
        )

    def _on_px_size_changed(self) -> None:
        """Update the scene when the pixel size is changed."""
        plate, mode = self.fov_page.value()
        assert plate == self.plate_page.value().plate

        if plate is None:
            return

        # update the mode with the new fov size
        if mode is not None:
            fov_w, fov_h = self._get_fov_size()
            mode = mode.replace(fov_width=fov_w, fov_height=fov_h)

        # update the fov_page with the fov size
        self.fov_page.setValue(plate, mode)

    def _get_fov_size(self) -> tuple[float, float]:
        """Return the image size in mm depending on the camera device."""
        if (
            self._mmc is None
            or not self._mmc.getCameraDevice()
            or not self._mmc.getPixelSizeUm()
        ):
            return (0.0, 0.0)

        _cam_x = self._mmc.getImageWidth()
        _cam_y = self._mmc.getImageHeight()
        image_width_mm = _cam_x * self._mmc.getPixelSizeUm()
        image_height_mm = _cam_y * self._mmc.getPixelSizeUm()

        return image_width_mm, image_height_mm

    def _get_well_center_in_stage_coordinates(
        self,
    ) -> list[tuple[Well, float, float]] | None:
        plate, _ = self.plate_page.value()

        if plate is None:
            return None

        calibration = self.calibration_page.value()

        _, wells = self.plate_page.value()

        if wells is None or calibration is None or calibration.well_A1_center is None:
            return None

        a1_x, a1_y = calibration.well_A1_center
        wells_center_stage_coords = []
        for well in wells:
            x, y = get_well_center(plate, well, a1_x, a1_y)
            if calibration.rotation_matrix is not None:
                x, y = apply_rotation_matrix(
                    calibration.rotation_matrix, a1_x, a1_y, x, y
                )
            wells_center_stage_coords.append((well, x, y))

        return wells_center_stage_coords

    def _get_fovs_in_stage_coords(
        self, wells_centers: list[tuple[Well, float, float]]
    ) -> list[Position]:
        """Get the calibrated stage coords of each FOV of the selected wells."""
        _, mode = self.fov_page.value()

        if mode is None:
            return []

        positions: list[Position] = []

        for well, well_center_x, well_center_y in wells_centers:
            if isinstance(mode, Center):
                positions.append(
                    Position(x=well_center_x, y=well_center_y, name=f"{well.name}")
                )

            elif isinstance(mode, (RandomPoints, GridRowsColumns)):
                # if mode is RandomPoints, order the points by nearest neighbor from the
                # most top-left point. If GridRowsColumns, just use the order given by
                # the mode iteration.
                fovs = (
                    nearest_neighbor(list(mode), TOP_X, TOP_Y)
                    if isinstance(mode, RandomPoints)
                    else list(mode)
                )
                for idx, fov in enumerate(fovs):
                    x = fov.x + well_center_x
                    y = fov.y + well_center_y
                    positions.append(Position(x=x, y=y, name=f"{well.name}_{idx:04d}"))

            else:
                raise ValueError(f"Invalid mode: {mode}")

        return positions

    # this is just for testing, remove later _______________________
    # def drawPlateMap(self) -> None:
    #     """Draw the plate map for the current experiment."""
    #     # get the well centers in stage coordinates
    #     well_centers = self._get_well_center_in_stage_coordinates()

    #     if well_centers is None:
    #         return

    #     _, ax = plt.subplots()

    #     plate, _ = self.plate_page.value()

    #     if plate is None:
    #         return

    #     # draw wells
    #     for _, well_center_x, well_center_y in well_centers:
    #         plt.plot(well_center_x, well_center_y, "mo")

    #         if plate.circular:
    #             sh = patches.Circle(
    #                 (well_center_x, well_center_y),
    #                 radius=plate.well_size_x * 1000 / 2,
    #                 fill=False,
    #             )
    #         else:
    #             w = plate.well_size_x * 1000
    #             h = plate.well_size_y * 1000
    #             x = well_center_x - w / 2
    #             y = well_center_y - h / 2
    #             sh = patches.Rectangle((x, y), width=w, height=h, fill=False)

    #         ax.add_patch(sh)

    #     # draw FOVs
    #     positions = self.get_positions()
    #     if positions is None:
    #         return

    #     x = [p.x for p in positions]  # type: ignore
    #     y = [p.y for p in positions]  # type: ignore
    #     plt.scatter(x, y, color="green")

    #     ax.axis("equal")
    #     ax.xaxis.set_visible(False)
    #     ax.yaxis.set_visible(False)
    #     plt.show()

    # _______________________________________________________________
