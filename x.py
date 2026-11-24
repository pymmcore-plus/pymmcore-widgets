from vispy import app

from pymmcore_widgets.views._spectra_viewer import SpectraViewer

widget = SpectraViewer()
widget.add_spectrum("mTurquoise")
widget.add_spectrum("mStayGold")
widget.add_spectrum("mCherry")
widget.add_spectrum("Chroma ET525/50m")
app.run()
