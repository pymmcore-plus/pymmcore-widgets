from __future__ import annotations

from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QCheckBox, QTabBar, QTabWidget, QWidget


class CheckableTabWidget(QTabWidget):
    """A QTabWidget subclass where each tab has a checkable QCheckbox.

    Toggling the QCheckbox enables/disables the widget(s) in the tab.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    checkbox_position : QTabBar.ButtonPosition
        The position of the tab QCheckbox. By default, QTabBar.ButtonPosition.LeftSide.
    change_tab_on_check : bool
        Whether to change and select the tab when the respective QCheckbox is checked.
        By default, True.
    movable : bool
        Whether the tabs are movable. By default, True.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        checkbox_position: QTabBar.ButtonPosition = QTabBar.ButtonPosition.LeftSide,
        change_tab_on_check: bool = True,
        movable: bool = True,
    ) -> None:
        super().__init__(parent)

        self._checkbox = QCheckBox
        # self.checkbox_position below not private because it could be used to get the
        # QCheckbox object using self.tabBar().tabButton(index, checkbox_position)
        self.checkbox_position = checkbox_position
        self._change_tab_on_check = change_tab_on_check

        self.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabBar().setMovable(movable)

    def addTab(self, widget: QWidget, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Add a tab with a checkable QCheckbox.

        Parameters
        ----------
        widget : QWidget
            The widget to add to the tab.
        *args : Any
            Positional arguments to pass to the base class method.
        **kwargs : Any
            Keyword arguments to pass to the base class method.
        """
        widget.setEnabled(False)
        super().addTab(widget, *args, **kwargs)
        idx = self.count() - 1
        self._cbox = self._checkbox(parent=self.tabBar())
        self._cbox.toggled.connect(self._on_tab_checkbox_toggled)
        self.tabBar().setTabButton(idx, self.checkbox_position, self._cbox)

    def _on_tab_checkbox_toggled(self, checked: bool) -> None:
        """Enable/disable the widget in the tab."""
        tab_index = self.tabBar().tabAt(self.sender().pos())
        self.widget(tab_index).setEnabled(checked)
        if self._change_tab_on_check:
            self.setCurrentIndex(tab_index)
