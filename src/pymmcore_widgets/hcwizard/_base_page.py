from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import QWizardPage


class ConfigWizardPage(QWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__()
        self._model = model
        self._core = core
