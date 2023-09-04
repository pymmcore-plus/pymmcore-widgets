from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QSize
from qtpy.QtWidgets import (
    QBoxLayout,
    QCheckBox,
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

from pymmcore_widgets.useq_widgets import MDASequenceWidget

from ._core_positions import CoreConnectedPositionTable
from ._core_z import CoreConnectedZPlanWidgert

if TYPE_CHECKING:
    from typing import TypedDict

    from useq import MDASequence

    class SaveInfo(TypedDict):
        save_dir: str
        file_name: str
        split_positions: bool
        should_save: bool


class MDAWidget(MDASequenceWidget):
    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        self._mmc = mmcore or CMMCorePlus.instance()
        position_wdg = CoreConnectedPositionTable(1, self._mmc)
        z_wdg = CoreConnectedZPlanWidgert(self._mmc)

        super().__init__(parent=parent, position_wdg=position_wdg, z_wdg=z_wdg)
        self.save_info = _SaveGroupBox(parent=self)
        self.control_btns = _MDAControlButtons(self._mmc, self)

        # -------- initialize -----------

        self.z_plan.setSuggestedStep(_guess_NA(self._mmc) or 0.5)
        self._update_channel_groups()

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

        self.destroyed.connect(self._disconnect)

    def value(self) -> MDASequence:
        val = super().value()
        meta: dict = val.metadata.setdefault("pymmcore_widgets", {})
        meta.update(self.save_info.value())
        return val

    def setValue(self, value: MDASequence) -> None:
        super().setValue(value)
        self.save_info.setValue(value.metadata.get("pymmcore_widgets", {}))

    def _update_channel_groups(self) -> None:
        ch = self._mmc.getChannelGroup()
        self.channels.setChannelGroups({ch: self._mmc.getAvailableConfigs(ch)})

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
    ...
    """A Widget to gather information about MDA file saving."""

    def __init__(
        self, title: str = "Save Acquisition", parent: QWidget | None = None
    ) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)

        self.save_dir = QLineEdit()
        self.save_dir.setPlaceholderText("Select Save Directory")
        self.file_name = QLineEdit()
        self.file_name.setPlaceholderText("Choose File Name")
        self.split_positions = QCheckBox(text="Save XY Positions in separate files")

        browse_btn = QPushButton(text="...")
        browse_btn.clicked.connect(self._on_browse_clicked)

        grid = QGridLayout(self)
        grid.addWidget(QLabel("Directory:"), 0, 0)
        grid.addWidget(self.save_dir, 0, 1)
        grid.addWidget(browse_btn, 0, 2)
        grid.addWidget(QLabel("File Name:"), 1, 0)
        grid.addWidget(self.file_name, 1, 1)
        grid.addWidget(self.split_positions, 2, 0, 1, 3)

    def value(self) -> SaveInfo:
        """Return current state of the dialog."""
        return {
            "save_dir": self.save_dir.text(),
            "file_name": self.file_name.text() or "Experiment",
            "split_positions": (
                self.split_positions.isEnabled() and self.split_positions.isChecked()
            ),
            "should_save": self.isChecked(),
        }

    def setValue(self, value: SaveInfo | dict) -> None:
        self.save_dir.setText(value.get("save_dir", ""))
        self.file_name.setText(value.get("file_name", ""))
        self.split_positions.setChecked(value.get("split_positions", False))
        self.setChecked(value.get("should_save", False))

    def _on_browse_clicked(self) -> None:
        if save_dir := QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir.text()
        ):
            self.save_dir.setText(save_dir)


class _MDAControlButtons(QWidget):
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
            return None

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
