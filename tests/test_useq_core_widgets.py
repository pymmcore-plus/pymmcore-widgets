from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast
from unittest.mock import Mock, patch

import pytest
import useq
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QMessageBox

from pymmcore_widgets import HCSWizard
from pymmcore_widgets._util import get_next_available_path
from pymmcore_widgets.mda import MDAWidget
from pymmcore_widgets.mda._core_channels import CoreConnectedChannelTable
from pymmcore_widgets.mda._core_grid import CoreConnectedGridPlanWidget
from pymmcore_widgets.mda._core_mda import CoreMDATabs
from pymmcore_widgets.mda._core_positions import CoreConnectedPositionTable
from pymmcore_widgets.mda._core_z import CoreConnectedZPlanWidget
from pymmcore_widgets.useq_widgets._mda_sequence import (
    PYMMCW_METADATA_KEY,
    AutofocusAxis,
    KeepShutterOpen,
    QFileDialog,
)
from pymmcore_widgets.useq_widgets._positions import AF_DEFAULT_TOOLTIP, _MDAPopup

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")
MDA = useq.MDASequence(
    time_plan=useq.TIntervalLoops(interval=0.01, loops=2),
    stage_positions=[(0, 1, 2), useq.Position(x=42, y=0, z=3)],
    channels=[{"config": "DAPI", "exposure": 1}],
    z_plan=useq.ZRangeAround(range=1, step=0.3),
    grid_plan=useq.GridRowsColumns(rows=2, columns=1),
    axis_order="tpgzc",
    keep_shutter_open_across=("z",),
)

SAVE_META = {
    "save_dir": "dir",
    "save_name": "name.ome.tiff",
    "format": "ome-tiff",
    "should_save": True,
}


def test_core_connected_mda_wdg(qtbot: QtBot):
    wdg = MDAWidget()
    core = wdg._mmc
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)
    new_grid = MDA.grid_plan.replace(fov_width=512, fov_height=512)
    assert wdg.value().replace(metadata={}) == MDA.replace(grid_plan=new_grid)

    with qtbot.waitSignal(wdg._mmc.mda.events.sequenceFinished):
        wdg.control_btns.run_btn.click()

    assert wdg.control_btns.pause_btn.text() == "Pause"
    core.mda.events.sequencePauseToggled.emit(True)
    assert wdg.control_btns.pause_btn.text() == "Resume"
    core.mda.events.sequencePauseToggled.emit(False)
    assert wdg.control_btns.pause_btn.text() == "Pause"
    wdg.control_btns._disconnect()
    wdg._disconnect()


def test_core_connected_position_wdg(qtbot: QtBot, qapp) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)
    wdg.setValue(MDA)
    assert pos_table.table().rowCount() == 2

    p0 = pos_table.value()[0]
    assert p0.x == MDA.stage_positions[0].x
    assert p0.y == MDA.stage_positions[0].y
    assert p0.z == MDA.stage_positions[0].z

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)
    xyidx = pos_table.table().indexOf(pos_table._xy_btn_col)
    z_idx = pos_table.table().indexOf(pos_table._z_btn_col)
    pos_table.table().cellWidget(0, xyidx).click()
    pos_table.table().cellWidget(0, z_idx).click()
    p0 = pos_table.value()[0]
    assert round(p0.x) == 11
    assert round(p0.y) == 22
    assert round(p0.z) == 33

    wdg._mmc.waitForSystem()
    pos_table.move_to_selection.setChecked(True)
    pos_table.table().selectRow(0)
    pos_table._on_selection_change()


def _assert_position_wdg_state(
    stage: str, pos_table: CoreConnectedPositionTable, is_hidden: bool
) -> None:
    """Assert the correct widget state for the given stage."""
    if stage == "XY":
        # both x and y columns should be hidden if XY device is not loaded/selected
        x_col = pos_table.table().indexOf(pos_table.X)
        y_col = pos_table.table().indexOf(pos_table.Y)
        x_hidden = pos_table.table().isColumnHidden(x_col)
        y_hidden = pos_table.table().isColumnHidden(y_col)
        assert x_hidden == is_hidden
        assert y_hidden == is_hidden
        # the set position button should be hidden if XY device is not loaded/selected
        xy_btn_col = pos_table.table().indexOf(pos_table._xy_btn_col)
        xy_btn_hidden = pos_table.table().isColumnHidden(xy_btn_col)
        assert xy_btn_hidden == is_hidden
        # values() should return None for x and y if XY device is not loaded/selected
        if is_hidden:
            xy = [(v.x, v.y) for v in pos_table.value()]
            assert all(x is None and y is None for x, y in xy)

    elif stage == "Z":
        # the set position button should be hidden
        z_btn_col = pos_table.table().indexOf(pos_table._z_btn_col)
        assert pos_table.table().isColumnHidden(z_btn_col)
        # values() should return None for z
        if is_hidden:
            z = [v.z for v in pos_table.value()]
            assert all(z is None for z in z)
        # the include z checkbox should be unchecked
        assert not pos_table.include_z.isChecked()
        # the include z checkbox should be disabled if Z device is not loaded/selected
        assert pos_table.include_z.isEnabled() == (not is_hidden)
        # tooltip should should change if Z device is not loaded/selected
        tooltip = "Focus device unavailable." if is_hidden else ""
        assert pos_table.include_z.toolTip() == tooltip

    elif stage == "Autofocus":
        # the set position button should be hidden
        af_btn_col = pos_table.table().indexOf(pos_table._af_btn_col)
        assert pos_table.table().isColumnHidden(af_btn_col)
        if is_hidden:
            sub_seq = [v.sequence for v in pos_table.value()]
            assert all(s is None for s in sub_seq)
        # the use autofocus checkbox should be unchecked
        assert not pos_table.af_per_position.isChecked()
        # the use autofocus checkbox should be disabled if Autofocus device is not
        # loaded/selected
        assert pos_table.af_per_position.isEnabled() == (not is_hidden)
        # tooltip should should change if Autofocus device is not loaded/selected
        tooltip = "AutoFocus device unavailable." if is_hidden else AF_DEFAULT_TOOLTIP
        assert pos_table.af_per_position.toolTip() == tooltip


@pytest.mark.parametrize("stage", ["XY", "Z", "Autofocus"])
def test_core_connected_position_wdg_cfg_loaded(
    stage: str, qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    # stage device is not loaded, the respective columns should be hidden and
    # values() should return None. This behavior should change
    # when a new cfg stage device is loaded.
    mmc = global_mmcore
    mmc.unloadDevice(stage)

    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)

    # stage is not loaded
    _assert_position_wdg_state(stage, pos_table, is_hidden=True)

    with qtbot.waitSignal(mmc.events.systemConfigurationLoaded):
        mmc.loadSystemConfiguration(TEST_CONFIG)

    # stage is loaded (systemConfigurationLoaded is triggered)
    _assert_position_wdg_state(stage, pos_table, is_hidden=False)


@pytest.mark.parametrize("stage", ["XY", "Z", "Autofocus"])
def test_core_connected_position_wdg_property_changed(
    stage: str, qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    # if stage device are loaded but not set as default device, their respective columns
    # should be hidden and values() should return None. This behavior should change when
    # stage device is set as default device.
    mmc = global_mmcore

    with qtbot.waitSignal(mmc.events.propertyChanged):
        if stage == "XY":
            mmc.setProperty("Core", "XYStage", "")
        elif stage == "Z":
            mmc.setProperty("Core", "Focus", "")
        elif stage == "Autofocus":
            mmc.setProperty("Core", "AutoFocus", "")
        mmc.waitForSystem()

    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)

    # stage is not set as default device
    _assert_position_wdg_state(stage, pos_table, is_hidden=True)

    with qtbot.waitSignal(mmc.events.propertyChanged):
        if stage == "XY":
            mmc.setProperty("Core", "XYStage", "XY")
        elif stage == "Z":
            mmc.setProperty("Core", "Focus", "Z")
        elif stage == "Autofocus":
            mmc.setProperty("Core", "AutoFocus", "Autofocus")

    # stage is set as default device (propertyChanged is triggered)
    _assert_position_wdg_state(stage, pos_table, is_hidden=False)


@pytest.fixture
def mock_getAutoFocusOffset(global_mmcore: CMMCorePlus):
    # core.getAutoFocusOffset() with the demo Autofocus device does not do
    # anything, so we need to mock it
    def _getAutoFocusOffset():
        return 10

    with patch.object(global_mmcore, "getAutoFocusOffset", _getAutoFocusOffset):
        yield


def test_core_position_table_add_position(
    qtbot: QtBot, mock_getAutoFocusOffset: None
) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)

    wdg.stage_positions.af_per_position.setChecked(True)

    assert pos_table.table().rowCount() == 1

    # test when autofocus is not engaged and af_per_position is checked
    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok
    ):
        with qtbot.waitSignals([pos_table.valueChanged], order="strict", timeout=1000):
            pos_table.act_add_row.trigger()

    # a new position has NOT been added
    assert pos_table.table().rowCount() == 1

    # test when autofocus is engaged and af_per_position is checked
    with patch.object(wdg._mmc, "isContinuousFocusLocked", return_value=True):
        with qtbot.waitSignals([pos_table.valueChanged], order="strict", timeout=1000):
            pos_table.act_add_row.trigger()

    val = pos_table.value()[-1]
    assert round(val.x, 1) == 11
    assert round(val.y, 1) == 22
    assert round(val.z, 1) == 33
    # setting it to to 10 because the mock_getAutoFocusOffset() returns 10
    assert val.sequence.autofocus_plan.autofocus_motor_offset == 10

    # a new position has been added
    assert pos_table.table().rowCount() == 2


def test_core_connected_relative_z_plan(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg._mmc.setXYPosition(11, 22)
    wdg._mmc.setZPosition(33)
    wdg._mmc.waitForSystem()

    MDA = useq.MDASequence(
        channels=[{"config": "DAPI", "exposure": 1}],
        z_plan=useq.ZRangeAround(range=1, step=0.3),
        axis_order="pzc",
    )
    wdg.setValue(MDA)

    val = wdg.value().stage_positions[-1]
    assert round(val.x, 1) == 11
    assert round(val.y, 1) == 22
    assert round(val.z, 1) == 33
    assert not val.sequence


def test_position_table_connected_popup(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)

    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)
    seq_col = pos_table.table().indexOf(pos_table.SEQ)
    btn = pos_table.table().cellWidget(0, seq_col)

    def handle_dialog():
        popup = btn.findChild(_MDAPopup)
        mda = popup.mda_tabs
        assert isinstance(mda.z_plan, CoreConnectedZPlanWidget)
        assert isinstance(mda.grid_plan, CoreConnectedGridPlanWidget)
        popup.accept()

    QTimer.singleShot(100, handle_dialog)

    with qtbot.waitSignal(wdg.valueChanged):
        btn.seq_btn.click()


def test_core_position_table_checkboxes_toggled(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()
    pos_table = wdg.stage_positions
    assert isinstance(pos_table, CoreConnectedPositionTable)

    wdg.setValue(MDA)

    z_btn_col = pos_table.table().indexOf(pos_table._z_btn_col)
    af_btn_col = pos_table.table().indexOf(pos_table._af_btn_col)

    pos_table.include_z.setChecked(False)
    pos_table.af_per_position.setChecked(False)

    assert pos_table.table().isColumnHidden(z_btn_col)
    assert pos_table.table().isColumnHidden(af_btn_col)

    pos_table.include_z.setChecked(True)
    pos_table.af_per_position.setChecked(True)

    assert not pos_table.table().isColumnHidden(z_btn_col)
    assert not pos_table.table().isColumnHidden(af_btn_col)


def test_core_mda_autofocus(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    AF = useq.AxesBasedAF(autofocus_motor_offset=10, axes=("p",))
    POS = [
        useq.Position(x=0, y=0, z=0, sequence=useq.MDASequence(autofocus_plan=AF)),
        useq.Position(x=1, y=1, z=1, sequence=useq.MDASequence(autofocus_plan=AF)),
    ]
    MDA = useq.MDASequence(stage_positions=POS)
    wdg.setValue(MDA)

    assert wdg.value().autofocus_plan
    assert wdg.value().autofocus_plan.autofocus_motor_offset == 10
    assert not wdg.value().stage_positions[0].sequence
    assert not wdg.value().stage_positions[1].sequence

    AF1 = useq.AxesBasedAF(autofocus_motor_offset=15, axes=("p",))
    POS1 = [
        useq.Position(x=0, y=0, z=0, sequence=useq.MDASequence(autofocus_plan=AF)),
        useq.Position(x=1, y=1, z=1, sequence=useq.MDASequence(autofocus_plan=AF1)),
    ]
    MDA = MDA.replace(stage_positions=POS1)

    # here we need to mock the core isContinuousFocusLocked method because the Autofocus
    # demo device cannot be set as "Locked in Focus" and since af_per_position is
    # checked, we would trigger a warning dialog (dialog is tested in previous test)
    with patch.object(wdg._mmc, "isContinuousFocusLocked", return_value=True):
        wdg.setValue(MDA)
    assert not wdg.value().autofocus_plan
    assert (
        wdg.value().stage_positions[0].sequence.autofocus_plan.autofocus_motor_offset
        == 10
    )
    assert (
        wdg.value().stage_positions[1].sequence.autofocus_plan.autofocus_motor_offset
        == 15
    )

    POS2 = [
        useq.Position(x=0, y=0, z=0, sequence=useq.MDASequence(autofocus_plan=AF)),
        useq.Position(
            x=0,
            y=0,
            z=0,
            sequence=useq.MDASequence(
                autofocus_plan=AF,
                grid_plan=useq.GridRowsColumns(rows=2, columns=1),
            ),
        ),
    ]
    MDA = MDA.replace(stage_positions=POS2)

    with patch.object(wdg._mmc, "isContinuousFocusLocked", return_value=True):
        wdg.setValue(MDA)
    assert wdg.value().autofocus_plan
    assert wdg.value().autofocus_plan.autofocus_motor_offset == 10
    assert not wdg.value().stage_positions[0].sequence
    assert wdg.value().stage_positions[1].sequence


def test_af_axis_wdg(qtbot: QtBot):
    wdg = AutofocusAxis()
    qtbot.addWidget(wdg)
    wdg.show()

    assert not wdg.value()
    wdg.setValue(("p", "t", "g"))
    assert wdg.value() == ("p", "t", "g")


def test_keep_shutter_open_wdg(qtbot: QtBot):
    wdg = KeepShutterOpen()
    qtbot.addWidget(wdg)
    wdg.show()

    assert not wdg.value()
    wdg.setValue(("z", "t"))
    assert wdg.value() == ("z", "t")


def test_run_mda_af_warning(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    MDA = useq.MDASequence(
        stage_positions=[useq.Position(x=0, y=0, z=0)],
        time_plan=useq.TIntervalLoops(interval=1, loops=2),
        autofocus_plan=useq.AxesBasedAF(axes=("p", "t")),
    )
    wdg.setValue(MDA)

    def _cancel(*args, **kwargs):
        return QMessageBox.StandardButton.Cancel

    with patch.object(QMessageBox, "warning", _cancel):
        wdg.control_btns.run_btn.click()

    assert not wdg._mmc.mda.is_running()

    def _ok(*args, **kwargs):
        return QMessageBox.StandardButton.Ok

    with patch.object(QMessageBox, "warning", _ok):
        with qtbot.waitSignal(wdg._mmc.mda.events.sequenceStarted):
            wdg.control_btns.run_btn.click()
        with qtbot.waitSignal(wdg._mmc.mda.events.sequenceFinished):
            assert wdg._mmc.mda.is_running()


def test_core_connected_channel_wdg(qtbot: QtBot):
    wdg = CoreConnectedChannelTable()
    qtbot.addWidget(wdg)
    wdg.show()

    # delete current channel group
    wdg._mmc.deleteConfigGroup("Channel")

    # "Channel" not in combo
    assert "Channel" not in [
        wdg._group_combo.itemText(i) for i in range(wdg._group_combo.count())
    ]

    # create new channel group called "Channels" (before it was "Channel")
    wdg._mmc.defineConfig("Channels", "DAPI", "Dichroic", "Label", "400DCLP")
    wdg._mmc.defineConfig("Channels", "FITC", "Dichroic", "Label", "Q505LP")

    assert "Channel" not in wdg._mmc.getAvailableConfigGroups()
    assert "Channels" in wdg._mmc.getAvailableConfigGroups()

    wdg._group_combo.setCurrentText("Channels")

    with qtbot.waitSignals([wdg.valueChanged], order="strict", timeout=1000):
        wdg.act_add_row.trigger()
        wdg.act_add_row.trigger()

    value = wdg.value()
    assert len(value) == 2
    assert value[0].group == "Channels"
    assert value[1].group == "Channels"


def test_enable_core_tab(qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    def wdgs_enabled(mda_tabs: CoreMDATabs) -> bool:
        return (
            mda_tabs.time_plan.isEnabled()
            and mda_tabs.stage_positions.isEnabled()
            and mda_tabs.z_plan.isEnabled()
            and mda_tabs.grid_plan.isEnabled()
            and mda_tabs.channels.isEnabled()
        )

    mda_tabs = cast(CoreMDATabs, wdg.tab_wdg)

    mda_tabs._enable_tabs(True)
    # all tabs are enabled (you can switch between them)
    assert [mda_tabs.tabBar().isTabEnabled(t) for t in range(mda_tabs.count())]
    # the tabs checkboxes are enabled
    assert all(cbox.isEnabled() for cbox in mda_tabs._cboxes)
    # the the tabs content is enabled
    assert wdgs_enabled(mda_tabs)

    mda_tabs._enable_tabs(False)

    # all tabs are still enabled (you can still switch between them)
    assert [mda_tabs.tabBar().isTabEnabled(t) for t in range(mda_tabs.count())]
    # the tab checkboxes are disabled
    assert not all(cbox.isEnabled() for cbox in mda_tabs._cboxes)
    # the the tabs content is enabled
    assert not wdgs_enabled(mda_tabs)


def test_relative_z_with_no_include_z(global_mmcore: CMMCorePlus, qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    MDA = useq.MDASequence(
        channels=[{"config": "DAPI", "exposure": 1}],
        stage_positions=[(1, 2, 3), (4, 5, 6)],
        z_plan=useq.ZRangeAround(go_up=True, range=2.0, step=1.0),
    )
    wdg.setValue(MDA)

    wdg._mmc.setZPosition(30)
    wdg._mmc.waitForSystem()

    assert wdg.stage_positions.include_z.isChecked()
    assert wdg.value().stage_positions[0].z == 3
    assert wdg.value().stage_positions[1].z == 6

    wdg.stage_positions.include_z.setChecked(False)
    assert not wdg.stage_positions.include_z.isChecked()
    assert wdg.value().stage_positions[0].z == 30
    assert wdg.value().stage_positions[1].z == 30


def test_mda_no_pos_set(global_mmcore: CMMCorePlus, qtbot: QtBot):
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    global_mmcore.setXYPosition(10, 20)
    global_mmcore.setZPosition(30)

    MDA = useq.MDASequence(channels=[{"config": "DAPI", "exposure": 1}])
    wdg.setValue(MDA)

    assert wdg.value().stage_positions
    assert round(wdg.value().stage_positions[0].x) == 10
    assert round(wdg.value().stage_positions[0].y) == 20
    assert round(wdg.value().stage_positions[0].z) == 30

    assert "p" in wdg.value().axis_order


@pytest.mark.parametrize("ext", ["json", "yaml"])
def test_core_mda_wdg_load_save(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ext: str
) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    dest = tmp_path / f"sequence.{ext}"
    # monkeypatch the dialog to load/save to our temp file
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (dest, None))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (dest, None))

    # write the sequence to file and load the widget from it
    mda = MDA.replace(metadata={**MDA.metadata, PYMMCW_METADATA_KEY: SAVE_META})
    dest.write_text(mda.yaml() if ext == "yaml" else mda.model_dump_json())
    wdg.load()

    meta = wdg.value().metadata[PYMMCW_METADATA_KEY]
    assert meta["save_dir"] == SAVE_META["save_dir"]
    assert meta["save_name"] == SAVE_META["save_name"]
    assert meta["format"] == SAVE_META["format"]

    # save the widget to file and load it back
    dest.unlink()
    wdg.save()
    assert useq.MDASequence.from_file(dest).metadata[PYMMCW_METADATA_KEY] == meta


def test_mda_set_value_with_seq_metadata(qtbot: QtBot) -> None:
    """Test setting the value of the MDAWidget with a seq that has save metadata."""
    mda = MDAWidget()
    qtbot.addWidget(mda)

    mda.setValue(useq.MDASequence(metadata={PYMMCW_METADATA_KEY: SAVE_META}))
    assert mda.save_info.isChecked()
    assert mda.save_info.save_dir.text() == SAVE_META["save_dir"]
    assert mda.save_info.save_name.text() == SAVE_META["save_name"]
    assert mda.save_info._writer_combo.currentText() == SAVE_META["format"]


def test_mda_sequenceFinished_save_name(
    global_mmcore: CMMCorePlus,
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the save name is updated after the sequence is finished."""
    mda_wdg = MDAWidget(mmcore=global_mmcore)
    qtbot.addWidget(mda_wdg)

    # add a file to tempdir
    requested_file = tmp_path / "name.ome.tiff"

    mda_wdg.save_info.setValue(requested_file)
    assert mda_wdg.save_info.isChecked()
    assert mda_wdg.save_info.value()["save_name"] == "name.ome.tiff"

    requested_file.touch()  # mock the write
    mda_wdg._on_mda_finished(mda_wdg.value())

    # the save widget should now have a new name
    assert mda_wdg.save_info.value()["save_name"] == "name_001.ome.tiff"


@pytest.mark.parametrize("extension", [".ome.tiff", ".ome.tif", ".ome.zarr", ""])
def test_get_next_available_paths(extension: str, tmp_path: Path) -> None:
    # non existing paths returns the same path
    path = tmp_path / f"test{extension}"
    assert get_next_available_path(path) == path

    make: Callable = Path.mkdir if extension in {".ome.zarr", ""} else Path.touch

    # existing files add a counter to the path
    make(path)
    assert get_next_available_path(path) == tmp_path / f"test_001{extension}"

    # if a path with a counter exists, the next (maximum) counter is used
    make(tmp_path / f"test_004{extension}")
    assert get_next_available_path(path) == tmp_path / f"test_005{extension}"


def test_get_next_available_paths_special_cases(tmp_path: Path) -> None:
    base = tmp_path / "test.txt"
    assert get_next_available_path(base).name == base.name

    # only 3+ digit numbers are considered as counters
    (tmp_path / "test_04.txt").touch()
    assert get_next_available_path(base).name == base.name

    # if an existing thing with a higher number is there, the next number is used
    # (even if the requested path does not exist, but has a lower number)
    (tmp_path / "test_004.txt").touch()
    assert get_next_available_path(tmp_path / "test_003.txt").name == "test_005.txt"

    # if we explicitly ask for a higher number, we should get it
    assert get_next_available_path(tmp_path / "test_010.txt").name == "test_010.txt"

    # only 3+ digit numbers are considered as counters
    assert get_next_available_path(tmp_path / "test_02.txt").name == "test_02_005.txt"

    # we go to the next number of digits if need be
    (tmp_path / "test_999.txt").touch()
    assert get_next_available_path(base).name == "test_1000.txt"

    # more than 3 digits are used as is
    high = tmp_path / "test_12345.txt"
    high.touch()
    assert get_next_available_path(high).name == "test_12346.txt"


def test_core_mda_with_hcs_value(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    # uncheck all tabs
    for t in range(wdg.tab_wdg.count() + 1):
        wdg.tab_wdg.setChecked(t, False)

    assert wdg.stage_positions._hcs_wizard is None
    assert wdg.stage_positions._plate_plan is None

    pos = useq.WellPlatePlan(
        plate="96-well", a1_center_xy=(0, 0), selected_wells=((0, 1), (0, 1))
    )
    seq = useq.MDASequence(stage_positions=pos)

    mock = Mock()
    wdg.valueChanged.connect(mock)
    wdg.setValue(seq)
    mock.assert_called_once()

    assert wdg.value().stage_positions == pos
    assert wdg.stage_positions.table().rowCount() == len(pos)

    assert isinstance(wdg.stage_positions._hcs_wizard, HCSWizard)
    assert wdg.stage_positions._plate_plan == pos


def test_core_mda_with_hcs_enable_disable(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    table = wdg.stage_positions.table()
    name_col = table.indexOf(wdg.stage_positions.NAME)
    xy_btn_col = table.indexOf(wdg.stage_positions._xy_btn_col)
    z_btn_col = table.indexOf(wdg.stage_positions._z_btn_col)
    z_col = table.indexOf(wdg.stage_positions.Z)
    sub_seq_btn_col = table.indexOf(wdg.stage_positions.SEQ)

    mda = useq.MDASequence(stage_positions=[(0, 0, 0), (1, 1, 1)])
    wdg.setValue(mda)

    # edit table btn is hidden
    assert wdg.stage_positions._edit_hcs_pos.isHidden()
    # all table visible
    assert not table.isColumnHidden(name_col)
    assert not table.isColumnHidden(xy_btn_col)
    assert not table.isColumnHidden(z_btn_col)
    assert not table.isColumnHidden(z_col)
    assert not table.isColumnHidden(sub_seq_btn_col)
    # all toolbar actions enabled
    assert all(action.isEnabled() for action in wdg.stage_positions.toolBar().actions())
    # include_z checkbox enabled
    assert wdg.stage_positions.include_z.isEnabled()
    # autofocus checkbox enabled
    assert wdg.stage_positions.af_per_position.isEnabled()

    mda = useq.MDASequence(
        stage_positions=useq.WellPlatePlan(
            plate="96-well",
            a1_center_xy=(0, 0),
            selected_wells=((0, 1), (0, 1)),
        )
    )
    wdg.setValue(mda)

    # edit table btn is visible
    assert not wdg.stage_positions._edit_hcs_pos.isHidden()
    # all columns hidden but name
    assert not table.isColumnHidden(name_col)
    assert table.isColumnHidden(xy_btn_col)
    assert table.isColumnHidden(z_btn_col)
    assert table.isColumnHidden(z_col)
    assert table.isColumnHidden(sub_seq_btn_col)
    # all toolbar actions disabled but the move stage checkbox
    assert all(
        not action.isEnabled() for action in wdg.stage_positions.toolBar().actions()[1:]
    )
    # include_z checkbox disabled
    assert wdg.stage_positions.include_z.isHidden()
    # autofocus checkbox disabled
    assert wdg.stage_positions.af_per_position.isHidden()


@pytest.mark.parametrize("ext", ["json", "yaml"])
def test_core_mda_with_hcs_load_save(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ext: str
) -> None:
    wdg = MDAWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    dest = tmp_path / f"sequence.{ext}"
    # monkeypatch the dialog to load/save to our temp file
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (dest, None))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (dest, None))

    # write the sequence to file and load the widget from it
    mda = MDA.replace(
        stage_positions=useq.WellPlatePlan(
            plate="96-well",
            a1_center_xy=(0, 0),
            selected_wells=((0, 0), (1, 1)),
            well_points_plan=useq.RelativePosition(fov_width=512.0, fov_height=512.0),
        )
    )
    dest.write_text(mda.yaml() if ext == "yaml" else mda.model_dump_json())
    wdg.load()

    pos = wdg.value().stage_positions

    # save the widget to file and load it back
    dest.unlink()
    wdg.save()
    assert useq.MDASequence.from_file(dest).stage_positions == pos
