import webbrowser

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Device, Microscope
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)
from superqt.fonticon import icon

from ._base_page import ConfigWizardPage


class _DelaySpin(QDoubleSpinBox):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimum(0)
        self.setMaximum(10000)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)


class DelayTable(QTableWidget):
    """Simple Property Table."""

    def __init__(self, model: Microscope, parent=None):
        headers = ["", "Label", "Adapter", "Delay [ms]"]
        super().__init__(0, len(headers), parent)
        self._model = model
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(self.SelectionMode.NoSelection)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.setColumnWidth(0, 200)

    def rebuild(self) -> None:
        """Rebuild the table for the given device and prop_names."""
        devs = [d for d in self._model.devices if d.uses_delay]

        self.setRowCount(len(devs))
        for i, dev in enumerate(devs):
            btn = QToolButton()
            btn.setIcon(icon(MDI6.information_outline, color="blue"))
            self.setCellWidget(i, 0, btn)
            self.setItem(i, 1, QTableWidgetItem(dev.name))
            self.setItem(i, 2, QTableWidgetItem(dev.adapter_name))
            spin_wdg = _DelaySpin()
            self.setCellWidget(i, 3, spin_wdg)

            @btn.clicked.connect
            def _on_click(state: bool, lib: str = dev.library) -> None:
                webbrowser.open(f"https://micro-manager.org/{lib}")

            @spin_wdg.valueChanged.connect
            def _on_change(v: float, d: Device = dev) -> None:
                d.delay_ms = v

        hh = self.horizontalHeader()
        hh.resizeSections(hh.ResizeMode.ResizeToContents)


class DelayPage(ConfigWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Set delays for devices without synchronization capabilities")
        self.setSubTitle(
            "Set how long to wait for the device to act before Micro-Manager will "
            "move on (for example, waiting for a shutter to open before an image "
            "is snapped). Many devices will determine this automatically; refer to "
            "the help for more information."
        )

        self.delays_table = DelayTable(self._model)

        layout = QVBoxLayout(self)
        layout.addWidget(self.delays_table)

    def _show_help(self) -> None:
        from webbrowser import open

        # TODO: some of these will be 404
        open(f"https://micro-manager.org/{lib_name}")

    def initializePage(self) -> None:
        self.delays_table.rebuild()
        return super().initializePage()
