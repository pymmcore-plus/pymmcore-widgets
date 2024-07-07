from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets.points_plans import RelativePointPlanSelector

app = QApplication([])

# Create a widget
wdg = RelativePointPlanSelector()
wdg.show()

app.exec()
