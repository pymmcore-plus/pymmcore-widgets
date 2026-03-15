from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex, Qt
from qtpy.QtGui import QFont, QIcon, QPixmap

from pymmcore_widgets._models import (
    ConfigGroup,
    ConfigGroupPivotModel,
    ConfigPreset,
    Device,
    DevicePropertySetting,
    QConfigGroupsModel,
    QDevicePropertyModel,
    get_config_groups,
)
from pymmcore_widgets._models._q_device_prop_model import DevicePropertyFlatProxy

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
    python_info = list(get_config_groups(core))
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
        (Qt.ItemDataRole.UserRole, (ConfigGroup, ConfigPreset, DevicePropertySetting)),
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
    assert setting0.device_label == "NewDevice"
    assert setting0.property_name == "NewProperty"
    assert setting0.value == "NewSettingValue"

    # setting to the same value should not change the model
    current_name = grp0_index.data(Qt.ItemDataRole.EditRole)
    assert model.setData(grp0_index, current_name) is False
    # setting to an empty string should not change the model
    assert model.setData(grp0_index, "") is False
    # setting to a value that already exists should show a warning
    existing_name = model.index(1).data(Qt.ItemDataRole.EditRole)  # next row down
    # existing name should not modify the model
    with pytest.warns(
        UserWarning,
        match=f"Not adding duplicate name '{existing_name}'. It already exists.",
    ):
        # this should not change the model
        assert model.setData(grp0_index, existing_name) is False


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

    with pytest.warns(UserWarning, match="Reference index is not a ConfigGroup."):
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

    with pytest.warns(UserWarning, match="Reference index is not a ConfigPreset."):
        model.duplicate_preset(QModelIndex())

    with pytest.warns(UserWarning, match="Reference index is not a ConfigGroup."):
        model.add_preset(QModelIndex(), "New Preset")


def test_remove(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test removing groups and presets."""
    group_names = {x.name for x in model.get_groups()}
    grp0_index = model.index(0)
    grp0_name = grp0_index.data(Qt.ItemDataRole.DisplayRole)
    assert grp0_name in group_names
    model.remove(grp0_index)
    assert grp0_name not in {x.name for x in model.get_groups()}


def test_node_registry_cleanup(model: QConfigGroupsModel) -> None:
    """Removing rows should clean up the node registry to prevent leaks."""
    registry_before = len(model._node_registry)
    assert registry_before > 0

    # Count nodes in first group (group + presets + settings)
    grp0 = model._root.children[0]
    node_count = 1  # group node itself
    for preset in grp0.children:
        node_count += 1  # preset node
        node_count += len(preset.children)  # setting nodes

    model.removeRows(0, 1, QModelIndex())
    assert len(model._node_registry) == registry_before - node_count


def test_update_preset_settings(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test updating preset settings."""
    original_data = model.get_groups()
    preset0 = next(iter(original_data[0].presets.values()))
    assert len(preset0.settings) > 1
    assert preset0.settings[0].device_label != "NewDevice"

    grp0_index = model.index(0, 0)
    preset0_index = model.index(0, 0, grp0_index)
    new_settings = [
        DevicePropertySetting(
            device="NewDevice", property_name="NewProperty", value="NewValue"
        )
    ]
    model.update_preset_settings(preset0_index, new_settings)

    new_data = model.get_groups()
    preset0_new = next(iter(new_data[0].presets.values()))
    assert len(preset0_new.settings) == 1
    assert preset0_new.settings == new_settings

    with pytest.warns(UserWarning, match="Reference index is not a ConfigPreset."):
        model.update_preset_settings(QModelIndex(), new_settings)


def test_update_preset_properties(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    """Test updating preset properties."""
    # Get original data
    original_data = model.get_groups()
    preset0 = next(iter(original_data[0].presets.values()))
    original_settings_count = len(preset0.settings)
    assert original_settings_count > 1

    existing_setting1 = preset0.settings[0]
    existing_setting2 = preset0.settings[1]
    existing_key1 = existing_setting1.key()
    existing_key2 = existing_setting2.key()

    grp0_index = model.index(0, 0)
    preset0_index = model.index(0, 0, grp0_index)

    new_setting = DevicePropertySetting(device="NewDevice", property_name="NewProp")
    new_properties = [existing_setting1, existing_setting2, new_setting]

    model.update_preset_properties(preset0_index, new_properties)

    # Verify the changes
    new_data = model.get_groups()
    preset0_new = next(iter(new_data[0].presets.values()))

    # Should have exactly 3 settings now
    assert len(preset0_new.settings) == 3

    # Check that existing settings are preserved with their values
    settings_by_key = {s.key(): s for s in preset0_new.settings}
    assert existing_key1 in settings_by_key
    assert existing_key2 in settings_by_key
    assert ("NewDevice", "NewProp") in settings_by_key

    # Verify existing settings kept their values
    assert settings_by_key[existing_key1].value == existing_setting1.value
    assert settings_by_key[existing_key2].value == existing_setting2.value

    # Verify new setting has empty value
    assert settings_by_key[("NewDevice", "NewProp")].value == ""
    assert settings_by_key[("NewDevice", "NewProp")].device_label == "NewDevice"
    assert settings_by_key[("NewDevice", "NewProp")].property_name == "NewProp"

    # Test with invalid index
    with pytest.warns(UserWarning, match="Reference index is not a ConfigPreset."):
        model.update_preset_properties(QModelIndex(), new_properties)


def test_name_change_valid(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    assert model.is_name_change_valid(model.index(0), "Camera") is None  # same name
    assert model.is_name_change_valid(model.index(0), "  ") == "Name cannot be empty"
    assert model.is_name_change_valid(model.index(0), "New Group Name") is None
    assert (
        model.is_name_change_valid(model.index(0), "Channel")
        == "Name 'Channel' already exists"
    )
    assert (
        model.is_name_change_valid(QModelIndex(), "Camera") == "Cannot rename root node"
    )


def test_set_channel_group(model: QConfigGroupsModel, qtbot: QtBot) -> None:
    channel_group = {g.name for g in model.get_groups() if g.is_channel_group}
    assert channel_group == {"Channel"}

    with qtbot.waitSignal(model.dataChanged):
        model.set_channel_group(model.index(0, 0))
    new_channel_group = {g.name for g in model.get_groups() if g.is_channel_group}
    assert new_channel_group == {"Camera"}

    with qtbot.assertNotEmitted(model.dataChanged):
        model.set_channel_group(model.index(0, 0))  # set to the same thing again
    new_channel_group = {g.name for g in model.get_groups() if g.is_channel_group}
    assert new_channel_group == {"Camera"}

    with qtbot.waitSignal(model.dataChanged):
        model.set_channel_group(QModelIndex())  # reset to no channel group
    reset_channel_group = {g.name for g in model.get_groups() if g.is_channel_group}
    assert reset_channel_group == set()


def test_standard_item_model(
    model: QConfigGroupsModel, qtmodeltester: ModelTester
) -> None:
    qtmodeltester.check(model)


def test_pivot_model(model: QConfigGroupsModel, qtmodeltester: ModelTester) -> None:
    pivot = ConfigGroupPivotModel()
    pivot.setSourceModel(model)
    pivot.setGroup("Channel")
    pivot.setGroup(pivot.index(1, 0))  # set by index
    qtmodeltester.check(pivot)


def test_pivot_model_two_way_sync(
    model: QConfigGroupsModel, qtmodeltester: ModelTester, qtbot: QtBot
) -> None:
    """Test _ConfigGroupPivotModel stays in sync with QConfigGroupsModel."""
    # Create pivot model and set it up
    pivot = ConfigGroupPivotModel()
    pivot.setSourceModel(model)
    pivot.setGroup("Camera")  # Camera group has 3 presets and 2 settings each
    qtmodeltester.check(pivot)

    # Get initial state
    camera_group_idx = model.index_for_group("Camera")

    # Verify initial pivot model state matches source
    assert pivot.rowCount() == 2  # Camera-Binning, Camera-BitDepth
    assert pivot.columnCount() == 3  # HighRes, LowRes, MedRes
    assert pivot.headerData(0, Qt.Orientation.Horizontal) == "HighRes"
    assert pivot.headerData(1, Qt.Orientation.Horizontal) == "LowRes"
    assert pivot.headerData(2, Qt.Orientation.Horizontal) == "MedRes"
    assert pivot.headerData(0, Qt.Orientation.Vertical) == "Camera-Binning"
    assert pivot.headerData(1, Qt.Orientation.Vertical) == "Camera-BitDepth"

    # Test 1: Changes in source model trigger _rebuild in pivot model
    # Add a new preset to the source model and verify pivot model updates
    new_preset_idx = model.add_preset(camera_group_idx, "TestPreset")
    assert new_preset_idx.isValid()

    # Pivot should automatically rebuild and show the new preset
    assert pivot.columnCount() == 4  # Now includes TestPreset
    assert pivot.headerData(3, Qt.Orientation.Horizontal) == "TestPreset"

    # Add a setting to the new preset
    test_settings = [
        DevicePropertySetting(device="Camera", property_name="Binning", value="8"),
        DevicePropertySetting(device="Camera", property_name="BitDepth", value="14"),
    ]
    model.update_preset_settings(new_preset_idx, test_settings)

    # Pivot should show the new data
    assert pivot.data(pivot.index(0, 3)) == "8"  # Camera-Binning for TestPreset
    assert pivot.data(pivot.index(1, 3)) == "14"  # Camera-BitDepth for TestPreset

    # Test 2: Modifying data in source model updates pivot model
    highres_preset_idx = model.index_for_preset(camera_group_idx, "HighRes")
    # Value column of first setting
    highres_setting_idx = model.index(0, 2, highres_preset_idx)

    with qtbot.waitSignal(model.dataChanged):
        model.setData(highres_setting_idx, "3")  # Change binning from 1 to 3

    # Pivot should reflect the change
    assert pivot.data(pivot.index(0, 0)) == "3"  # Camera-Binning for HighRes

    # Test 3: Changes in pivot model update source model (setData direction)
    # Change a value in the pivot model
    pivot_idx = pivot.index(1, 1)  # Camera-BitDepth for LowRes
    new_value = "16"

    assert pivot.setData(pivot_idx, new_value)

    # Verify the source model was updated
    updated_groups = model.get_groups()
    updated_camera_group = next(g for g in updated_groups if g.name == "Camera")
    lowres_preset = updated_camera_group.presets["LowRes"]
    bitdepth_setting = next(
        s for s in lowres_preset.settings if s.property_name == "BitDepth"
    )
    assert bitdepth_setting.value == new_value

    # Test 4: Removing presets from source updates pivot
    # Remove the TestPreset we added
    model.remove(new_preset_idx)
    assert pivot.columnCount() == 3  # Back to original 3 presets

    # Test 5: Adding a new device/property combination
    # Add a setting with a new device/property to trigger row changes
    medres_preset_idx = model.index_for_preset(camera_group_idx, "MedRes")
    medres_preset_node = model._node_from_index(medres_preset_idx)

    # Cast the payload to ConfigPreset type
    from typing import cast

    medres_preset = cast("ConfigPreset", medres_preset_node.payload)

    # Add a new setting that doesn't exist in other presets
    new_settings = [
        *medres_preset.settings,
        DevicePropertySetting(
            device="Camera", property_name="NewProperty", value="NewValue"
        ),
    ]
    model.update_preset_settings(medres_preset_idx, new_settings)

    # Pivot should add a new row for the new device/property combination
    assert pivot.rowCount() == 3  # Now includes Camera-NewProperty
    assert pivot.headerData(2, Qt.Orientation.Vertical) == "Camera-NewProperty"
    assert pivot.data(pivot.index(2, 2)) == "NewValue"  # MedRes has the new property

    # Other presets should show None/empty for this new property
    assert pivot.data(pivot.index(2, 0)) is None  # HighRes doesn't have NewProperty
    assert pivot.data(pivot.index(2, 1)) is None  # LowRes doesn't have NewProperty

    # Test 6: Group change triggers complete rebuild
    pivot.setGroup("LightPath")  # Switch to a different group
    assert pivot.columnCount() == 3  # Camera-left, Camera-right, Eyepiece
    assert pivot.rowCount() == 1  # Only Path-State
    assert pivot.headerData(0, Qt.Orientation.Vertical) == "Path-State"

    # Switch back to Camera group
    pivot.setGroup("Camera")
    assert pivot.rowCount() == 3  # Should reflect the state we left it in
    assert pivot.columnCount() == 3


# ── QDevicePropertyModel tests ─────────────────────────────────────


@pytest.fixture
def device_model() -> QDevicePropertyModel:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    return QDevicePropertyModel.create_from_core(core)


def test_device_property_model_init(
    device_model: QDevicePropertyModel, qtmodeltester: ModelTester
) -> None:
    qtmodeltester.check(device_model)
    assert device_model.rowCount() > 0
    assert device_model.columnCount() == 2
    assert device_model.data(QModelIndex()) is None
    assert device_model.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags

    # Headers
    assert device_model.headerData(0, Qt.Orientation.Horizontal) == "Device/Property"
    assert device_model.headerData(1, Qt.Orientation.Horizontal) == "Type"


def test_device_property_model_data_roles(
    device_model: QDevicePropertyModel,
) -> None:
    # Find a device with properties
    dev_idx = QModelIndex()
    for i in range(device_model.rowCount()):
        idx = device_model.index(i, 0)
        if device_model.rowCount(idx) > 0:
            dev_idx = idx
            break
    assert dev_idx.isValid(), "No device with properties found"

    # Device-level data
    assert isinstance(dev_idx.data(Qt.ItemDataRole.DisplayRole), str)
    assert isinstance(dev_idx.data(Qt.ItemDataRole.UserRole), Device)
    # DecorationRole on device col 0 returns a pixmap or icon
    deco = dev_idx.data(Qt.ItemDataRole.DecorationRole)
    assert deco is not None

    # Property-level data
    prop_idx = device_model.index(0, 0, dev_idx)
    assert isinstance(prop_idx.data(Qt.ItemDataRole.DisplayRole), str)
    assert isinstance(prop_idx.data(Qt.ItemDataRole.UserRole), DevicePropertySetting)

    # CheckStateRole on property
    cs = device_model.data(prop_idx, Qt.ItemDataRole.CheckStateRole)
    assert cs == Qt.CheckState.Unchecked

    # Type column for property
    prop_type_idx = device_model.index(0, 1, dev_idx)
    assert isinstance(prop_type_idx.data(Qt.ItemDataRole.DisplayRole), str)


def test_device_property_model_check_state(
    device_model: QDevicePropertyModel, qtbot: QtBot
) -> None:
    # Find a non-read-only, non-pre-init property to check
    prop_idx = None
    for dev_row in range(device_model.rowCount()):
        dev_idx = device_model.index(dev_row, 0)
        for row in range(device_model.rowCount(dev_idx)):
            idx = device_model.index(row, 0, dev_idx)
            prop = idx.data(Qt.ItemDataRole.UserRole)
            if isinstance(prop, DevicePropertySetting):
                if not prop.is_read_only and not prop.is_pre_init:
                    prop_idx = idx
                    break
        if prop_idx is not None:
            break
    assert prop_idx is not None, "No checkable property found"

    with qtbot.waitSignal(device_model.dataChanged):
        assert device_model.setData(
            prop_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
        )
    assert (
        device_model.data(prop_idx, Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Checked
    )

    with qtbot.waitSignal(device_model.dataChanged):
        assert device_model.setData(
            prop_idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
        )

    # Invalid index returns False
    assert not device_model.setData(
        QModelIndex(), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
    )

    # Flags include checkable on col 0
    flags = device_model.flags(prop_idx)
    assert flags & Qt.ItemFlag.ItemIsUserCheckable


def test_device_property_model_set_get_devices(
    device_model: QDevicePropertyModel,
) -> None:
    original_devices = device_model.get_devices()
    assert len(original_devices) > 0

    device_model.set_devices([])
    assert device_model.rowCount() == 0

    device_model.set_devices(original_devices)
    assert device_model.rowCount() == len(original_devices)

    # get_devices returns a deep copy
    copy = device_model.get_devices()
    assert copy == original_devices
    assert copy is not original_devices


def test_device_property_flat_proxy(
    device_model: QDevicePropertyModel, qtmodeltester: ModelTester
) -> None:
    proxy = DevicePropertyFlatProxy()
    proxy.setSourceModel(device_model)
    qtmodeltester.check(proxy)

    assert proxy.columnCount() == 2
    # rowCount should be total number of properties across all devices
    total_props = sum(
        device_model.rowCount(device_model.index(i, 0))
        for i in range(device_model.rowCount())
    )
    assert proxy.rowCount() == total_props
    assert not proxy.parent(proxy.index(0, 0)).isValid()  # flat

    # Column 0 = device label, Column 1 = property name
    first = proxy.index(0, 0)
    assert isinstance(first.data(Qt.ItemDataRole.DisplayRole), str)
    second = proxy.index(0, 1)
    assert isinstance(second.data(Qt.ItemDataRole.DisplayRole), str)

    # Headers
    assert proxy.headerData(0, Qt.Orientation.Horizontal) == "Device"
    assert proxy.headerData(1, Qt.Orientation.Horizontal) == "Property"


def test_device_property_flat_proxy_check_propagation(
    device_model: QDevicePropertyModel, qtbot: QtBot
) -> None:
    proxy = DevicePropertyFlatProxy()
    proxy.setSourceModel(device_model)

    # Find a checkable property
    for row in range(proxy.rowCount()):
        idx = proxy.index(row, 1)
        prop = idx.data(Qt.ItemDataRole.UserRole)
        if isinstance(prop, DevicePropertySetting):
            if not prop.is_read_only and not prop.is_pre_init:
                break
    else:
        pytest.skip("No checkable property found in flat proxy")

    # Set check via proxy
    assert proxy.setData(idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)

    # Verify source model has the check
    dev_idx = device_model.index(0, 0)
    for r in range(device_model.rowCount(dev_idx)):
        src_idx = device_model.index(r, 0, dev_idx)
        src_prop = src_idx.data(Qt.ItemDataRole.UserRole)
        if isinstance(src_prop, DevicePropertySetting) and src_prop.key() == prop.key():
            assert (
                device_model.data(src_idx, Qt.ItemDataRole.CheckStateRole)
                == Qt.CheckState.Checked
            )
            break


def test_device_property_flat_proxy_sort(
    device_model: QDevicePropertyModel,
) -> None:
    proxy = DevicePropertyFlatProxy()
    proxy.setSourceModel(device_model)

    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    if proxy.rowCount() >= 2:
        first = proxy.index(0, 0).data() or ""
        second = proxy.index(1, 0).data() or ""
        assert first <= second

    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    if proxy.rowCount() >= 2:
        first = proxy.index(0, 0).data() or ""
        second = proxy.index(1, 0).data() or ""
        assert first >= second
