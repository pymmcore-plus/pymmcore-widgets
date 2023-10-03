from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QSize, Signal
from qtpy.QtWidgets import (
    QBoxLayout,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from superqt.fonticon import icon
from useq import MDASequence, Position

from pymmcore_widgets.useq_widgets import MDASequenceWidget
from pymmcore_widgets.useq_widgets._channels import ChannelTable
from pymmcore_widgets.useq_widgets._mda_sequence import MDATabs
from pymmcore_widgets.useq_widgets._time import TimePlanWidget

from ._core_grid import CoreConnectedGridPlanWidget
from ._core_positions import CoreConnectedPositionTable
from ._core_z import CoreConnectedZPlanWidget

if TYPE_CHECKING:
    from typing import TypedDict

    class SaveInfo(TypedDict):
        save_dir: str
        save_name: str


class CoreMDATabs(MDATabs):
    def __init__(
        self, parent: QWidget | None = None, core: CMMCorePlus | None = None
    ) -> None:
        self._mmc = core or CMMCorePlus.instance()
        super().__init__(parent)

    def create_subwidgets(self) -> None:
        self.time_plan = TimePlanWidget(1)
        self.stage_positions = CoreConnectedPositionTable(1, self._mmc)
        self.z_plan = CoreConnectedZPlanWidget(self._mmc)
        self.grid_plan = CoreConnectedGridPlanWidget(self._mmc)
        self.channels = ChannelTable(1)


class MDAWidget(MDASequenceWidget):
    """Widget for running MDA experiments, connecting to a MMCorePlus instance."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        # create a couple core-connected variants of the tab widgets
        self._mmc = mmcore or CMMCorePlus.instance()

        super().__init__(parent=parent, tab_widget=CoreMDATabs(None, self._mmc))

        self.save_info = _SaveGroupBox(parent=self)
        self.save_info.valueChanged.connect(self.valueChanged)
        self.control_btns = _MDAControlButtons(self._mmc, self)

        # -------- initialize -----------

        self._on_sys_config_loaded()

        # ------------ layout ------------

        layout = cast("QBoxLayout", self.layout())
        layout.insertWidget(0, self.save_info)
        layout.addWidget(self.control_btns)

        # ------------ connect signals ------------

        self.control_btns.run_btn.clicked.connect(self._on_run_clicked)
        self.control_btns.pause_btn.released.connect(self._mmc.mda.toggle_pause)
        self.control_btns.cancel_btn.released.connect(self._mmc.mda.cancel)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.channelGroupChanged.connect(self._update_channel_groups)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)

        self.destroyed.connect(self._disconnect)

    def _on_sys_config_loaded(self) -> None:
        # TODO: connect objective change event to update suggested step
        self.z_plan.setSuggestedStep(_guess_NA(self._mmc) or 0.5)
        self._update_channel_groups()

    def value(self) -> MDASequence:
        """Set the current state of the widget."""
        val = super().value()

        # if the z plan is relative, and there are no stage positions, add the current
        # stage position as the relative starting one.
        # Note: this is not the final solution, it shiud be better to move this in
        # pymmcore-plus runner but only after we introduce a concept of a "relative
        # position" in useq.MDAEvent. At the moment, since the pymmcore-plus runner is
        # not aware of the core, we cannot move it there.
        if val.z_plan and val.z_plan.is_relative and not val.stage_positions:
            val = val.replace(stage_positions=[self._get_current_stage_position()])

        meta: dict = val.metadata.setdefault("pymmcore_widgets", {})
        if self.save_info.isChecked():
            meta.update(self.save_info.value())
        return val

    def _get_current_stage_position(self) -> Position:
        """Return the current stage position."""
        x = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        y = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        z = self._mmc.getPosition() if self._mmc.getFocusDevice() else None
        return Position(x=x, y=y, z=z)

    def setValue(self, value: MDASequence) -> None:
        """Get the current state of the widget."""
        super().setValue(value)
        self.save_info.setValue(value.metadata.get("pymmcore_widgets", {}))

    # ------------------- private API ----------------------

    def _update_channel_groups(self) -> None:
        ch_group = self._mmc.getChannelGroup()
        # if there is no channel group available, use all available groups
        names = [ch_group] if ch_group else self._mmc.getAvailableConfigGroups()
        groups = {
            group_name: self._mmc.getAvailableConfigs(group_name)
            for group_name in names
        }
        self.channels.setChannelGroups(groups)

    def _on_run_clicked(self) -> None:
        """Run the MDA sequence experiment."""
        # run the MDA experiment asynchronously
        self._mmc.run_mda(self.value())
        return

    def _enable_widgets(self, enable: bool) -> None:
        for child in self.children():
            if child is not self.control_btns and hasattr(child, "setEnabled"):
                child.setEnabled(enable)

    def _on_mda_started(self) -> None:
        self._enable_widgets(False)

    def _on_mda_finished(self) -> None:
        self._enable_widgets(True)

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)
            self._mmc.events.channelGroupChanged.disconnect(self._update_channel_groups)


class _SaveGroupBox(QGroupBox):
    """A Widget to gather information about MDA file saving."""

    valueChanged = Signal()

    def __init__(
        self, title: str = "Save Acquisition", parent: QWidget | None = None
    ) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)

        self.save_dir = QLineEdit()
        self.save_dir.setPlaceholderText("Select Save Directory")
        self.save_name = QLineEdit()
        self.save_name.setPlaceholderText("Enter Experiment Name")

        browse_btn = QPushButton(text="...")
        browse_btn.clicked.connect(self._on_browse_clicked)

        grid = QGridLayout(self)
        grid.addWidget(QLabel("Directory:"), 0, 0)
        grid.addWidget(self.save_dir, 0, 1)
        grid.addWidget(browse_btn, 0, 2)
        grid.addWidget(QLabel("Name:"), 1, 0)
        grid.addWidget(self.save_name, 1, 1)

        # connect
        self.toggled.connect(self.valueChanged)
        self.save_dir.textChanged.connect(self.valueChanged)
        self.save_name.textChanged.connect(self.valueChanged)

    def value(self) -> SaveInfo:
        """Return current state of the dialog."""
        return {
            "save_dir": self.save_dir.text(),
            "save_name": self.save_name.text() or "Experiment",
        }

    def setValue(self, value: SaveInfo | dict) -> None:
        self.save_dir.setText(value.get("save_dir", ""))
        self.save_name.setText(value.get("save_name", ""))
        self.setChecked(value.get("should_save", False))

    def _on_browse_clicked(self) -> None:
        if save_dir := QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir.text()
        ):
            self.save_dir.setText(save_dir)


class _MDAControlButtons(QWidget):
    """Run, pause, and cancel buttons at the bottom of the MDA Widget."""

    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mmc = mmcore
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        icon_size = QSize(24, 24)
        self.run_btn = QPushButton("Run")
        self.run_btn.setIcon(icon(MDI6.play_circle_outline, color="lime"))
        self.run_btn.setIconSize(icon_size)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_btn.setIconSize(icon_size)
        self.pause_btn.hide()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(icon(MDI6.stop_circle_outline, color="magenta"))
        self.cancel_btn.setIconSize(icon_size)
        self.cancel_btn.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self.run_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.cancel_btn)

        self.destroyed.connect(self._disconnect)

    def _on_mda_started(self) -> None:
        self.run_btn.hide()
        self.pause_btn.show()
        self.cancel_btn.show()

    def _on_mda_finished(self) -> None:
        self.run_btn.show()
        self.pause_btn.hide()
        self.cancel_btn.hide()
        self._on_mda_paused(False)

    def _on_mda_paused(self, paused: bool) -> None:
        if paused:
            self.pause_btn.setIcon(icon(MDI6.play_circle_outline, color="lime"))
            self.pause_btn.setText("Resume")
        else:
            self.pause_btn.setIcon(icon(MDI6.pause_circle_outline, color="green"))
            self.pause_btn.setText("Pause")

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequencePauseToggled.disconnect(self._on_mda_paused)
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)


def _guess_NA(core: CMMCorePlus) -> float | None:
    with suppress(RuntimeError):
        if not (pix_cfg := core.getCurrentPixelSizeConfig()):
            return None  # pragma: no cover

        data = core.getPixelSizeConfigData(pix_cfg)
        for obj in core.guessObjectiveDevices():
            key = (obj, Keyword.Label)
            if key in data:
                val = data[key]
                for word in val.split():
                    try:
                        na = float(word)
                    except ValueError:
                        continue
                    if 0.1 < na < 1.5:
                        return na
    return None
