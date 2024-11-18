from vispy import scene

from pymmcore_widgets._vispy_plot import PlotWidget
from pymmcore_widgets.fpbase import Spectrum, get_filter, get_fluorophore


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

    def add_spectrum(self, name: str) -> None:
        spectra: list[tuple[Spectrum, str]] = []
        try:
            spectra.append((get_filter(name), "#AAAAAA"))
        except ValueError:
            fluor = get_fluorophore(name)
            for state in fluor.states:
                if state.excitation_spectrum:
                    spectra.append((state.excitation_spectrum, state.exhex))
                if state.emission_spectrum:
                    spectra.append((state.emission_spectrum, state.emhex))

        for spectrum, color in spectra:
            self.plot.plot(spectrum.data, color=color)
