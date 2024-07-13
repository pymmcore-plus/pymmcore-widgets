from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_widgets.control._presets_widget import PresetsWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_preset_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    for group in global_mmcore.getAvailableConfigGroups():
        wdg = PresetsWidget(group)
        qtbot.addWidget(wdg)
        presets = list(global_mmcore.getAvailableConfigs(group))
        assert list(wdg.allowedValues()) == presets

        # no need testing the changes of a config group that has <= 1 item
        if len(presets) <= 1:
            return

        with qtbot.waitSignal(global_mmcore.events.configSet):
            global_mmcore.setConfig(group, presets[-1])
        assert wdg.value() == presets[-1] == global_mmcore.getCurrentConfig(group)

        wdg.setValue(presets[0])
        assert global_mmcore.getCurrentConfig(group) == presets[0]

        if group == "Camera":
            global_mmcore.setProperty("Camera", "Binning", "8")
            assert wdg._combo.styleSheet() == "color: magenta;"
            global_mmcore.setProperty("Camera", "Binning", "1")
            assert wdg._combo.styleSheet() == ""

            global_mmcore.setConfig("Camera", "HighRes")
            assert wdg._combo.currentText() == "HighRes"
            assert wdg._combo.styleSheet() == ""
            global_mmcore.setProperty("Camera", "Binning", "2")
            assert wdg._combo.currentText() == "HighRes"
            assert wdg._combo.styleSheet() == "color: magenta;"
            global_mmcore.setProperty("Camera", "BitDepth", "10")
            assert wdg._combo.currentText() == "MedRes"
            assert wdg._combo.styleSheet() == ""

            warning_string = (
                "'test' preset is missing the following properties:"
                "[('Camera', 'BitDepth')]"
            )
            with pytest.warns(UserWarning, match=warning_string):
                with qtbot.waitSignals([global_mmcore.events.configDefined]):
                    global_mmcore.defineConfig(
                        "Camera", "test", "Camera", "Binning", "4"
                    )
                assert len(wdg.allowedValues()) == 4
                assert "test" in wdg.allowedValues()
                global_mmcore.deleteConfig("Camera", "test")
                assert len(wdg.allowedValues()) == 3
                assert "test" not in wdg.allowedValues()

            warning_string = (
                "[('Dichroic', 'Label')]are not included in the 'Camera' group "
                "and will not be added!"
            )
            with pytest.warns(UserWarning, match=warning_string):
                with qtbot.waitSignals([global_mmcore.events.configDefined]):
                    global_mmcore.defineConfig(
                        "Camera", "test", "Dichroic", "Label", "400DCLP"
                    )
                assert len(wdg.allowedValues()) == 3
                assert "test" not in wdg.allowedValues()

        wdg._disconnect()
        # once disconnected, core changes shouldn't call out to the widget
        global_mmcore.setConfig(group, presets[1])
        assert global_mmcore.getCurrentConfig(group) != wdg.value()

    global_mmcore.deleteConfigGroup("Camera")
    assert "Camera" not in global_mmcore.getAvailableConfigGroups()
