from vispy import app

from pymmcore_widgets.views._spectra_viewer import SpectraViewer

widget = SpectraViewer()
widget.add_fluorophore("mTurquoise")
widget.add_fluorophore("mStayGold")
widget.add_fluorophore("mCherry")
app.run()
