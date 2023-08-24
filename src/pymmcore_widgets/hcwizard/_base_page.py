from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import QWizardPage


class _ConfigWizardPage(QWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__()
        self._model = model
        self._core = core

    def initializePage(self) -> None:
        # called to initialize the page's contents when the user clicks NEXT
        # If you want to derive the page's default from what the user
        # entered on previous pages, this is the function to reimplement.
        print("init", self.title())
        return super().initializePage()

    def cleanupPage(self) -> None:
        # called to reset the page's contents when the user clicks BACK.
        print("cleanup", self.title())
        return super().cleanupPage()

    def validatePage(self) -> bool:
        # validates the page when the user clicks Next or Finish. It is often used
        # to show an error message if the user has entered incomplete or
        # invalid information.
        print("validate", self.title())
        return super().validatePage()

    def isComplete(self) -> bool:
        # is called to determine whether the Next and/or Finish button
        # should be enabled or disabled.
        # If you reimplement isComplete(), also make sure that
        # completeChanged() is emitted whenever the complete state changes.
        print("complete", self.title())
        return super().isComplete()



class DelayPage(_ConfigWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Set delays for devices without synchronization capabilities")


class LabelsPage(_ConfigWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Define position labels for state devices")


class FinishPage(_ConfigWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Save configuration and exit")
