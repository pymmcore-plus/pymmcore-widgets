from pathlib import Path

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.hcwizard.config_wizard import ConfigWizard
from pymmcore_widgets.hcwizard.finish_page import DEST_CONFIG

TEST_CONFIG = Path(__file__).parent / "test_config.cfg"


def _non_empty_lines(path: Path) -> list[str]:
    return [
        ln
        for line in path.read_text().splitlines()
        if (ln := line.strip()) and not ln.startswith("#")
    ]


def test_config_wizard(global_mmcore: CMMCorePlus, qtbot, tmp_path: Path):
    out = tmp_path / "out.cfg"
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.setField(DEST_CONFIG, str(out))
    wiz.accept()

    assert out.exists()

    global_mmcore.loadSystemConfiguration(str(TEST_CONFIG))
    st1 = global_mmcore.getSystemState()

    global_mmcore.loadSystemConfiguration(str(out))
    st2 = global_mmcore.getSystemState()

    assert st1 == st2
