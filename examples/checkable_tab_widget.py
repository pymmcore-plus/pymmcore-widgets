from qtpy.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from pymmcore_widgets import CheckableTabWidget

app = QApplication([])

checkable_tabwidget = CheckableTabWidget()

wdg_tab_1 = QWidget()
wdg_tab_1.setLayout(QVBoxLayout())
wdg_tab_1.layout().addWidget(QLabel("wdg of tab 1"))
checkable_tabwidget.addTab(wdg_tab_1, "tab 1")

wdg_tab_2 = QWidget()
wdg_tab_2.setLayout(QVBoxLayout())
wdg_tab_2.layout().addWidget(QLabel("wdg of tab 2"))
checkable_tabwidget.addTab(wdg_tab_2, "tab 2")

checkable_tabwidget.show()
app.exec_()
