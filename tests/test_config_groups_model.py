from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtCore import QModelIndex, Qt
from qtpy.QtGui import QFont, QIcon, QPixmap
from qtpy.QtWidgets import QMessageBox

from pymmcore_widgets.config_presets import QConfigGroupsModel
from pymmcore_widgets.config_presets._views._config_presets_table import (
    _ConfigGroupPivotModel,
)

if TYPE_CHECKING:
    from pytestqt.modeltest import ModelTester
    from pytestqt.qtbot import QtBot


@pytest.fixture
def model() -> QConfigGroupsModel:
    """Fixture to create a QConfigGroupsModel instance."""
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QConfigGroupsModel.create_from_core(core)
    return model


def test_model_initialization() -> None:
    """Test the initialization of the QConfigGroupsModel."""
    # not using the fixture here, as we want to test the model creation directly
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    python_info = list(ConfigGroup.all_config_groups(core).values())
    model = QConfigGroupsModel(python_info)

    assert isinstance(model, QConfigGroupsModel)
    assert model.rowCount() > 0
    assert model.columnCount() == 3

    # original data is recovered intact
    assert model.get_groups() == python_info
    assert model.data(QModelIndex()) is None


def test_model_basic_methods(model: QConfigGroupsModel) -> None:
    """Test basic methods of the QConfigGroupsModel."""
    assert model.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags

    grp = model.index(0)
    preset = model.index(0, 0, grp)
    setting = model.index(0, 2, preset)

    assert model.flags(grp) & Qt.ItemFlag.ItemIsEnabled
    assert model.flags(preset) & Qt.ItemFlag.ItemIsEnabled
    assert model.flags(setting) & Qt.ItemFlag.ItemIsEditable

    assert model.headerData(0, Qt.Orientation.Horizontal) == "Item"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "Property"
    assert model.headerData(2, Qt.Orientation.Horizontal) == "Value"


@pytest.mark.parametrize(
    "role, type",
    [
        (Qt.ItemDataRole.DisplayRole, str),
        (Qt.ItemDataRole.EditRole, str),
        (Qt.ItemDataRole.UserRole, (ConfigGroup, ConfigPreset, Setting)),
        (Qt.ItemDataRole.FontRole, QFont),
        (Qt.ItemDataRole.DecorationRole, (QIcon, QPixmap)),
    ],
)
def test_model_data(model: QConfigGroupsModel, role: int, type: type) -> None:
    grp0_index = model.index(0, 0)
    preset0_index = model.index(0, 0, grp0_index)
    setting0_dev_idx = model.index(0, 0, preset0_index)
    setting0_prop_idx = model.index(0, 1, preset0_index)
    setting0_value_idx = model.index(0, 2, preset0_index)

    group_data = model.data(grp0_index, role)
    assert isinstance(group_data, type)

    preset_data = model.data(preset0_index, role)
    assert isinstance(preset_data, type)

    dev_name = model.data(setting0_dev_idx, role)
    assert isinstance(dev_name, type)
    if role == Qt.ItemDataRole.DisplayRole:
        prop_name = model.data(setting0_prop_idx, role)
        assert isinstance(prop_name, type)
        prop_value = model.data(setting0_value_idx, role)
        assert isinstance(prop_value, type)


def test_model_set_data(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test setting data in the model."""
    grp0_index = model.index(0, 0)
    preset0_index = model.index(0, 0, grp0_index)
    setting0_dev_idx = model.index(0, 0, preset0_index)
    setting0_prop_idx = model.index(0, 1, preset0_index)
    setting0_value_idx = model.index(0, 2, preset0_index)

    with qtbot.waitSignal(model.dataChanged):
        assert model.setData(grp0_index, "NewGroupName")
    with qtbot.waitSignal(model.dataChanged):
        assert model.setData(preset0_index, "NewPresetName")
    with qtbot.waitSignal(model.dataChanged):
        assert model.setData(setting0_dev_idx, "NewDevice")
    with qtbot.waitSignal(model.dataChanged):
        assert model.setData(setting0_prop_idx, "NewProperty")
    with qtbot.waitSignal(model.dataChanged):
        assert model.setData(setting0_value_idx, "NewSettingValue")

    group0 = model.get_groups()[0]
    preset0 = next(iter(group0.presets.values()))
    setting0 = preset0.settings[0]

    assert group0.name == "NewGroupName"
    assert preset0.name == "NewPresetName"
    assert setting0.device_name == "NewDevice"
    assert setting0.property_name == "NewProperty"
    assert setting0.property_value == "NewSettingValue"

    # setting to the same value should not change the model
    current_name = grp0_index.data(Qt.ItemDataRole.EditRole)
    assert model.setData(grp0_index, current_name) is False
    # setting to an empty string should not change the model
    assert model.setData(grp0_index, "") is False
    # setting to a value that already exists should show a warning
    existing_name = model.index(1).data(Qt.ItemDataRole.EditRole)  # next row down
    with patch.object(QMessageBox, "warning") as mock_warning:
        assert model.setData(grp0_index, existing_name) is False
        mock_warning.assert_called_once()


def test_index_queries(model: QConfigGroupsModel) -> None:
    """Test index queries in the model."""
    group0 = model.get_groups()[0]
    # non-existent group returns an invalid index
    assert not model.index_for_group("Python").isValid()
    # existing group returns a valid index
    group0_index = model.index_for_group(group0.name)
    assert group0_index.isValid()

    # non-existent preset returns an invalid index
    preset0 = next(iter(group0.presets.values()))
    assert not model.index_for_preset(group0.name, "NonExistentPreset").isValid()
    # existing preset returns a valid index using group name
    assert model.index_for_preset(group0.name, preset0.name).isValid()
    # ... or using group_index
    assert model.index_for_preset(group0_index, preset0.name).isValid()
    # but not an invalid group index
    invalid_group_index = QModelIndex()
    assert not model.index_for_preset(invalid_group_index, preset0.name).isValid()


def test_add_dupe_group(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test adding a duplicate group."""
    groups = {g.name for g in model.get_groups()}
    grp0_index = model.index(0)
    idx = model.add_group("New Group")
    assert idx.isValid()
    assert idx.data(Qt.ItemDataRole.DisplayRole) == "New Group"
    idx2 = model.duplicate_group(grp0_index)
    assert idx2.isValid()
    model.duplicate_group(grp0_index)  # and again ... copy (1)

    new_groups = {g.name for g in model.get_groups()}
    assert new_groups - groups == {
        "New Group",
        grp0_index.data(Qt.ItemDataRole.DisplayRole) + " copy",
        grp0_index.data(Qt.ItemDataRole.DisplayRole) + " copy (1)",
    }

    with pytest.raises(ValueError, match="Reference index is not a ConfigGroup."):
        model.duplicate_group(QModelIndex())


def test_add_dupe_preset(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test adding a duplicate preset."""
    grp0_index = model.index(0, 0)
    preset0_index = model.index(0, 0, grp0_index)
    idx = model.add_preset(grp0_index, "New Preset")
    assert idx.isValid()
    assert idx.data(Qt.ItemDataRole.DisplayRole) == "New Preset"

    model.duplicate_preset(preset0_index)

    new_presets = {p.name for p in model.get_groups()[0].presets.values()}
    assert "New Preset" in new_presets
    assert preset0_index.data(Qt.ItemDataRole.DisplayRole) + " copy" in new_presets

    with pytest.raises(ValueError, match="Reference index is not a ConfigPreset."):
        model.duplicate_preset(QModelIndex())

    with pytest.raises(ValueError, match="Reference index is not a ConfigGroup."):
        model.add_preset(QModelIndex(), "New Preset")


def test_remove(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test removing groups and presets."""
    group_names = {x.name for x in model.get_groups()}
    grp0_index = model.index(0)
    grp0_name = grp0_index.data(Qt.ItemDataRole.DisplayRole)
    assert grp0_name in group_names
    model.remove(grp0_index)
    assert grp0_name not in {x.name for x in model.get_groups()}


def test_update_preset_settings(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test updating preset settings."""
    original_data = model.get_groups()
    preset0 = next(iter(original_data[0].presets.values()))
    assert len(preset0.settings) > 1
    assert preset0.settings[0].device_name != "NewDevice"

    grp0_index = model.index(0, 0)
    preset0_index = model.index(0, 0, grp0_index)
    new_settings = [
        Setting(
            device_name="NewDevice",
            property_name="NewProperty",
            property_value="NewValue",
        )
    ]
    model.update_preset_settings(preset0_index, new_settings)

    new_data = model.get_groups()
    preset0_new = next(iter(new_data[0].presets.values()))
    assert len(preset0_new.settings) == 1
    assert preset0_new.settings == new_settings

    with pytest.raises(ValueError, match="Reference index is not a ConfigPreset."):
        model.update_preset_settings(QModelIndex(), new_settings)


def test_standard_item_model(
    model: QConfigGroupsModel, qtmodeltester: ModelTester
) -> None:
    qtmodeltester.check(model)


def test_pivot_model(model: QConfigGroupsModel, qtmodeltester: ModelTester) -> None:
    pivot = _ConfigGroupPivotModel()
    pivot.setSourceModel(model)
    pivot.setGroup("Channel")
    qtmodeltester.check(pivot)
