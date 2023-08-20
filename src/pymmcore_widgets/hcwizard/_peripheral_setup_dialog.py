from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Device, Microscope
from qtpy.QtWidgets import QDialog


class PeripheralSetupDlg(QDialog):
    def __init__(self, device: Device, model: Microscope, core: CMMCorePlus):
        super().__init__()
