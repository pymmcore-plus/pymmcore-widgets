from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)
from superqt.iconify import QIconifyIcon
from useq import MDASequence, Position

from pymmcore_widgets._util import get_next_available_path
from pymmcore_widgets.useq_widgets import MDASequenceWidget
from pymmcore_widgets.useq_widgets._mda_sequence import (
    AF_AXIS_TOOLTIP,
    AF_DISABLED_TOOLTIP,
    PYMMCW_METADATA_KEY,
    MDATabs,
)
from pymmcore_widgets.useq_widgets._positions import AF_PER_POS_TOOLTIP
from pymmcore_widgets.useq_widgets._time import TimePlanWidget
from pymmcore_widgets.useq_widgets._z import Mode

from ._core_channels import CoreConnectedChannelTable
from ._core_grid import CoreConnectedGridPlanWidget
from ._core_positions import AF_UNAVAILABLE, CoreConnectedPositionTable
from ._core_z import CoreConnectedZPlanWidget
from ._save_widget import SaveGroupBox

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pymmcore_plus.mda import SupportsFrameReady


class _CoreConnectedPositionTable(CoreConnectedPositionTable):
    def __init__(
        self,
        rows: int = 0,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(rows, mmcore, parent)

        # subclassing to disconnect the signals from this widget so we use the ones
        # we will implement in the MDAWidget that take into account both the autofocus
        # device mand the z plan
        ev = self._mmc.events
        ev.systemConfigurationLoaded.disconnect(self._on_sys_config_loaded)
        ev.propertyChanged.disconnect(self._on_property_changed)


class CoreMDATabs(MDATabs):
    def __init__(
        self, parent: QWidget | None = None, core: CMMCorePlus | None = None
    ) -> None:
        self._mmc = core or CMMCorePlus.instance()
        super().__init__(parent)

    def create_subwidgets(self) -> None:
        self.time_plan = TimePlanWidget(1)
        self.stage_positions = _CoreConnectedPositionTable(1, self._mmc)
        self.z_plan = CoreConnectedZPlanWidget(self._mmc)
        self.grid_plan = CoreConnectedGridPlanWidget(self._mmc)
        self.channels = CoreConnectedChannelTable(1, self._mmc)

    def _enable_tabs(self, enable: bool) -> None:
        """Enable or disable the tab checkboxes and their contents.

        However, we can still mover through the tabs and see their contents.
        """
        # disable tab checkboxes
        for cbox in self._cboxes:
            cbox.setEnabled(enable)
        # disable tabs contents
        self.time_plan.setEnabled(enable)
        self.stage_positions.setEnabled(enable)
        self.z_plan.setEnabled(enable)
        self.grid_plan.setEnabled(enable)
        self.channels.setEnabled(enable)


class MDAWidget(MDASequenceWidget):
    """Main MDA Widget connected to a [`pymmcore_plus.CMMCorePlus`][] instance.

    It provides a GUI to construct and run a [`useq.MDASequence`][].  Unlike
    [`useq_widgets.MDASequenceWidget`][pymmcore_widgets.MDASequenceWidget], this
    widget is connected to a [`pymmcore_plus.CMMCorePlus`][] instance, enabling
    awareness and control of the current state of the microscope.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        # create a couple core-connected variants of the tab widgets
        self._mmc = mmcore or CMMCorePlus.instance()

        super().__init__(parent=parent, tab_widget=CoreMDATabs(None, self._mmc))

        self.save_info = SaveGroupBox(parent=self)
        self.save_info.valueChanged.connect(self.valueChanged)
        self.control_btns = _MDAControlButtons(self._mmc, self)

        # -------- initialize -----------

        self._on_sys_config_loaded()

        # ------------ layout ------------

        layout = cast("QBoxLayout", self.layout())
        layout.insertWidget(0, self.save_info)
        layout.addWidget(self.control_btns)

        # ------------ connect signals ------------

        self.control_btns.run_btn.clicked.connect(self.run_mda)
        self.control_btns.pause_btn.released.connect(self._mmc.mda.toggle_pause)
        self.control_btns.cancel_btn.released.connect(self._mmc.mda.cancel)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

    # ----------- Override type hints in superclass -----------

    @property
    def channels(self) -> CoreConnectedChannelTable:
        return cast("CoreConnectedChannelTable", self.tab_wdg.channels)

    @property
    def z_plan(self) -> CoreConnectedZPlanWidget:
        return cast("CoreConnectedZPlanWidget", self.tab_wdg.z_plan)

    @property
    def stage_positions(self) -> CoreConnectedPositionTable:
        return cast("CoreConnectedPositionTable", self.tab_wdg.stage_positions)

    @property
    def grid_plan(self) -> CoreConnectedGridPlanWidget:
        return cast("CoreConnectedGridPlanWidget", self.tab_wdg.grid_plan)

    # ------------------- public Methods ----------------------

    def value(self) -> MDASequence:
        """Set the current state of the widget from a [`useq.MDASequence`][]."""
        val = super().value()
        replace: dict = {}

        # if the z plan is relative and there are stage positions but the 'include z' is
        # unchecked, use the current z stage position as the relative starting one.
        if (
            val.z_plan
            and val.z_plan.is_relative
            and (val.stage_positions and not self.stage_positions.include_z.isChecked())
        ):
            z = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
            replace["stage_positions"] = tuple(
                pos.replace(z=z) for pos in val.stage_positions
            )

        # if there is an autofocus_plan but the autofocus_motor_offset is None, set it
        # to the current value
        if (
            self._mmc.getAutoFocusDevice()
            and (afplan := val.autofocus_plan)
            and afplan.autofocus_motor_offset is None
        ):
            p2 = afplan.replace(autofocus_motor_offset=self._mmc.getAutoFocusOffset())
            replace["autofocus_plan"] = p2

        # if there are no stage positions, use the current stage position
        if not val.stage_positions:
            replace["stage_positions"] = (self._get_current_stage_position(),)
            # if "p" is not in the axis order, we need to add it or the position will
            # not be in the event
            if "p" not in val.axis_order:
                axis_order = list(val.axis_order)
                # add the "p" axis at the beginning or after the "t" as the default
                if "t" in axis_order:
                    axis_order.insert(axis_order.index("t") + 1, "p")
                else:
                    axis_order.insert(0, "p")
                replace["axis_order"] = tuple(axis_order)

        if replace:
            val = val.replace(**replace)

        meta: dict = val.metadata.setdefault(PYMMCW_METADATA_KEY, {})
        if self.save_info.isChecked():
            meta.update(self.save_info.value())
        return val

    def setValue(self, value: MDASequence) -> None:
        """Get the current state of the widget as a [`useq.MDASequence`][]."""
        super().setValue(value)
        self.save_info.setValue(value.metadata.get(PYMMCW_METADATA_KEY, {}))

    def get_next_available_path(self, requested_path: Path) -> Path:
        """Get the next available path.

        This method is called immediately before running an MDA to ensure that the file
        being saved does not overwrite an existing file. It is also called at the end
        of the experiment to update the save widget with the next available path.

        It may be overridden to provide custom behavior, but it should always return a
        Path object to a non-existing file or folder.

        The default behavior adds/increments a 3-digit counter at the end of the path
        (before the extension) if the path already exists.

        Parameters
        ----------
        requested_path : Path
            The path we are requesting for use.
        """
        return get_next_available_path(requested_path=requested_path)

    def prepare_mda(self) -> bool | str | Path | None:
        """Prepare the MDA sequence experiment.

        Returns
        -------
        bool
            False if MDA to be cancelled due to autofocus issue.
        str | Path
            Preparation successful, save path to be used for saving and saving active
        None
            Preparation successful, saving deactivated
        """
        # in case the user does not press enter after editing the save name.
        self.save_info.save_name.editingFinished.emit()

        # if autofocus has been requested, but the autofocus device is not engaged,
        # and position-specific offsets haven't been set, show a warning
        pos = self.stage_positions
        if (
            self.af_axis.value()
            and not self._mmc.isContinuousFocusLocked()
            and (not self.tab_wdg.isChecked(pos) or not self._use_af_per_position())
            and not self._confirm_af_intentions()
        ):
            return False

        # technically, this is in the metadata as well, but isChecked is more direct
        if self.save_info.isChecked():
            return self._update_save_path_from_metadata(
                self.value(), update_metadata=True
            )
        else:
            return None

    def execute_mda(
        self,
        output: (
            Path
            | str
            | SupportsFrameReady
            | Sequence[Path | str | SupportsFrameReady]
            | None
        ),
    ) -> None:
        """Execute the MDA experiment corresponding to the current value."""
        sequence = self.value()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(sequence, output=output)

    def run_mda(self) -> None:
        save_path = self.prepare_mda()
        if isinstance(save_path, bool):
            return
        self.execute_mda(save_path)

    # ------------------- private Methods ----------------------

    def _on_sys_config_loaded(self) -> None:
        self.stage_positions._update_xy_enablement()
        self.stage_positions._update_z_enablement()
        self._update_autofocus_enablement()
        # TODO: connect objective change event to update suggested step
        self.z_plan.setSuggestedStep(_guess_NA(self._mmc) or 0.5)

    def _on_property_changed(self, device: str, prop: str, _val: str = "") -> None:
        if device != "Core":
            return

        props = {
            "XYStage": self.stage_positions._update_xy_enablement,
            "Focus": self.stage_positions._update_z_enablement,
            "AutoFocus": self._update_autofocus_enablement,
        }
        if prop in props:
            props[prop]()
            self.valueChanged.emit()

    def _update_autofocus_enablement(self) -> None:
        """Enable or disable the autofocus widgets.

        Enable af_axis and af_per_position only if there is an autofocus device and no
        absolute z plan is selected.
        """
        # get the autofocus device
        af_device = self._get_autofocus_device()

        # update the autofocus axis widget
        self.af_axis.setEnabled(bool(af_device))
        self.af_axis.setToolTip(self._get_tooltip(self.af_axis))

        # update the autofocus per position widget
        self.stage_positions.af_per_position.setEnabled(bool(af_device))
        # set tooltip af_per_position
        self.stage_positions.af_per_position.setToolTip(
            self._get_tooltip(self.stage_positions.af_per_position)
        )

    def _get_tooltip(self, wdg: QWidget) -> str:
        """Return the tooltip for the autofocus widgets."""
        # if there is no autofocus device, return the unavailable tooltip
        if not self._mmc.getAutoFocusDevice():
            return AF_UNAVAILABLE
        # if autofocus device is available, but the z plan is in absolute mode, return
        # the disabled tooltip
        if (
            self.tab_wdg.isChecked(self.z_plan)
            and self.z_plan.mode() == Mode.TOP_BOTTOM
            and self._mmc.getAutoFocusDevice()
        ):
            return AF_DISABLED_TOOLTIP
        # if the widget is the autofocus axis, return the autofocus axis tooltip
        if wdg is self.af_axis:
            return AF_AXIS_TOOLTIP
        # if the widget is the autofocus per position, return the autofocus per position
        if wdg is self.stage_positions.af_per_position:
            return AF_PER_POS_TOOLTIP
        return ""

    def _get_autofocus_device(self) -> str | None:
        """Return the autofocus device if available.

        If there is also a z plan selected, the Autofocus device is only available if
        the z plan is not in absolute mode.
        """
        return (
            None
            if self.tab_wdg.isChecked(self.z_plan)
            and self.z_plan.mode() == Mode.TOP_BOTTOM
            else self._mmc.getAutoFocusDevice()
        )

    def _get_current_stage_position(self) -> Position:
        """Return the current stage position."""
        x = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        y = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        z = self._mmc.getPosition() if self._mmc.getFocusDevice() else None
        return Position(x=x, y=y, z=z)

    def _update_save_path_from_metadata(
        self,
        sequence: MDASequence,
        update_widget: bool = True,
        update_metadata: bool = False,
    ) -> Path | None:
        """Get the next available save path from sequence metadata and update widget.

        Parameters
        ----------
        sequence : MDASequence
            The MDA sequence to get the save path from. (must be in the
            'pymmcore_widgets' key of the metadata)
        update_widget : bool, optional
            Whether to update the save widget with the new path, by default True.
        update_metadata : bool, optional
            Whether to update the Sequence metadata with the new path, by default False.
        """
        if (
            (meta := sequence.metadata.get(PYMMCW_METADATA_KEY, {}))
            and (save_dir := meta.get("save_dir"))
            and (save_name := meta.get("save_name"))
        ):
            requested = (Path(save_dir) / str(save_name)).expanduser().resolve()
            next_path = self.get_next_available_path(requested)
            if next_path != requested:
                if update_widget:
                    self.save_info.setValue(next_path)
                    if update_metadata:
                        meta.update(self.save_info.value())
            return next_path
        return None

    def _confirm_af_intentions(self) -> bool:
        msg = (
            "You've selected to use autofocus for this experiment, "
            f"but the '{self._mmc.getAutoFocusDevice()!r}' autofocus device "
            "is not currently engaged. "
            "\n\nRun anyway?"
        )

        response = QMessageBox.warning(
            self,
            "Confirm AutoFocus",
            msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return bool(response == QMessageBox.StandardButton.Ok)

    def _enable_widgets(self, enable: bool) -> None:
        for child in self.children():
            if isinstance(child, CoreMDATabs):
                child._enable_tabs(enable)
            elif child is not self.control_btns and hasattr(child, "setEnabled"):
                child.setEnabled(enable)

    def _on_mda_started(self) -> None:
        self._enable_widgets(False)

    def _on_mda_finished(self, sequence: MDASequence) -> None:
        self._enable_widgets(True)
        # update the save name in the gui with the next available path
        # FIXME: this is actually a bit error prone in the case of super fast
        # experiments and delayed writers that haven't yet written anything to disk
        # (e.g. the next available path might be the same as the current one)
        # however, the quick fix of using a QTimer.singleShot(0, ...) makes for
        # difficulties in testing.
        # FIXME: Also, we really don't care about the last sequence at this point
        # anyway.  We should just update the save widget with the next available path
        # based on what's currently in the save widget, since that's what really
        # matters (not whatever the last requested mda was)
        self._update_save_path_from_metadata(sequence)

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_sys_config_loaded
        )
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)

    def _enable_af(self, state: bool) -> None:
        """Override the autofocus enablement to account for the autofocus device."""
        if not self._mmc.getAutoFocusDevice():
            self._update_autofocus_enablement()
            return
        return super()._enable_af(state)


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
        self.run_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.run_btn.setIcon(QIconifyIcon("mdi:play-circle-outline", color="lime"))
        self.run_btn.setIconSize(icon_size)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pause_btn.setIcon(QIconifyIcon("mdi:pause-circle-outline", color="green"))
        self.pause_btn.setIconSize(icon_size)
        self.pause_btn.hide()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_btn.setIcon(QIconifyIcon("mdi:stop-circle-outline", color="#C33"))
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
            self.pause_btn.setIcon(
                QIconifyIcon("mdi:play-circle-outline", color="lime")
            )
            self.pause_btn.setText("Resume")
        else:
            self.pause_btn.setIcon(
                QIconifyIcon("mdi:pause-circle-outline", color="green")
            )
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
