from vispy import scene

from pymmcore_widgets._vispy_plot import PlotWidget
from pymmcore_widgets.fpbase import get_fluorophore


class SpectraViewer:
    def __init__(self) -> None:
        self.canvas = scene.SceneCanvas(keys="interactive", show=True, size=(900, 400))
        self.view = self.canvas.central_widget.add_view()
        self.plot = PlotWidget(
            bgcolor="#121212",
            lock_axis="y",
            xlabel="Wavelength (nm)",
            # ylabel="Intensity",
        )
        self.plot.yaxis.visible = False
        self.view.add_widget(self.plot)

    def add_fluorophore(self, name: str) -> None:
        fluor = get_fluorophore(name)
        for state in fluor.states:
            if state.excitation_spectrum is not None:
                self.plot.plot(state.excitation_spectrum.data, color=state.exhex)
            if state.emission_spectrum is not None:
                self.plot.plot(state.emission_spectrum.data, color=state.emhex)
