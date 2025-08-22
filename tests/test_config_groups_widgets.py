from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt

from pymmcore_widgets import ConfigGroupsTree
from pymmcore_widgets._models import ConfigGroup, QConfigGroupsModel
from pymmcore_widgets.config_presets import ConfigPresetsTable
from pymmcore_widgets.config_presets._views._property_setting_delegate import (
    PropertySettingDelegate,
)
from pymmcore_widgets.device_properties._property_widget import PropertyWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_config_groups_tree(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    tree = ConfigGroupsTree.create_from_core(core)
    qtbot.addWidget(tree)
    tree.show()
    model = tree.model()
    assert isinstance(model, QConfigGroupsModel)

    # test the editor delegate -----------------------------

    delegate = tree.itemDelegateForColumn(2)
    assert isinstance(delegate, PropertySettingDelegate)

    setting_value = model.index(0, 2, model.index(0, 0, model.index(0, 0)))
    assert model.data(setting_value) == "1"

    # open an editor
    tree.edit(setting_value)
    editor = tree.focusWidget()
    assert isinstance(editor, PropertyWidget)
    with qtbot.waitSignal(delegate.commitData):
        editor.setValue("2")

    # make sure the model is updated
    assert model.data(setting_value) == "2"
    group0 = model.get_groups()[0]
    preset0 = next(iter(group0.presets.values()))
    assert preset0.settings[0].value == "2"


@pytest.mark.filterwarnings("ignore:CMMCorePlus.instance\\(\\) called")
def test_config_presets_table(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    table = ConfigPresetsTable.create_from_core(core)
    table.show()
    view = table.view
    model = table.sourceModel()
    assert isinstance(model, QConfigGroupsModel)

    table.setGroup("Channel")
    qtbot.addWidget(table)
    table.show()
    view.stretchHeaders()
    assert isinstance(table.sourceModel(), QConfigGroupsModel)

    assert not view.isTransposed()
    view.transpose()
    assert view.isTransposed()
    assert isinstance(table.sourceModel(), QConfigGroupsModel)

    view.transpose()
    assert not view.isTransposed()

    data = model.index(1).data(Qt.ItemDataRole.UserRole)  # type: ignore[attr-defined]
    assert isinstance(data, ConfigGroup)
    assert len(data.presets) == 4

    # test removing
    view.selectColumn(0)
    table.remove_action.trigger()
    assert len(data.presets) == 3

    # test duplicating
    view.selectColumn(0)
    table.duplicate_action.trigger()
    assert len(data.presets) == 4

    # check name of headers
    vm = view.model()
    assert vm
    header_names = [
        vm.headerData(i, Qt.Orientation.Horizontal) for i in range(vm.columnCount())
    ]
    assert header_names == ["DAPI", "DAPI copy", "FITC", "Rhodamine"]
