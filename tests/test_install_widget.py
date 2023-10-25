import platform

import pytest

from pymmcore_widgets import InstallWidget

LINUX = platform.system() == "Linux"


@pytest.mark.skipif(LINUX, reason="Linux not supported")
def test_install_widget(qtbot):
    wdg = InstallWidget()
    qtbot.addWidget(wdg)
    wdg.show()
