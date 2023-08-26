from pathlib import Path

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.hcwizard.config_wizard import ConfigWizard

TEST_CONFIG = Path(__file__).parent / "test_config.cfg"


def _non_empty_lines(path: Path) -> list[str]:
    return [
        ln
        for line in path.read_text().splitlines()
        if (ln := line.strip()) and not ln.startswith("#")
    ]


def test_config_wizard(global_mmcore: CMMCorePlus, qtbot, tmp_path: Path):
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    assert wiz.currentPage().isFinalPage()

    out = tmp_path / "out.cfg"
    wiz.save(out)
