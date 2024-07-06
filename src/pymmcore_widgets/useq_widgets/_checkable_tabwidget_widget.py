from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast, overload

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QCheckBox, QTabBar, QTabWidget, QWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QIcon


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

    tabChecked = Signal(int, bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        change_tab_on_check: bool = True,
    ) -> None:
        super().__init__(parent)

        self.change_tab_on_check = change_tab_on_check
        self.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self._cboxes: list[QCheckBox] = []

    def isChecked(
        self,
        key: int | QWidget,
        position: QTabBar.ButtonPosition = QTabBar.ButtonPosition.LeftSide,
    ) -> bool | None:
        """Return whether the tab is checked.

        Parameters
        ----------
        key : int | QWidget
            The tab index, or tab widget.
        position : QTabBar.ButtonPosition
            The position of the tab QCheckbox. By default, ButtonPosition.LeftSide.
        """
        idx = self.indexOf(key) if isinstance(key, QWidget) else key
        btn = self.tabBar().tabButton(idx, position)
        return cast("QCheckBox", btn).isChecked() if btn else None

    def setChecked(
        self,
        key: int | QWidget,
        checked: bool,
        position: QTabBar.ButtonPosition = QTabBar.ButtonPosition.LeftSide,
    ) -> None:
        """Set whether the tab is checked.

        Parameters
        ----------
        key : int | QWidget
            The tab index, or tab widget.
        checked : bool
            Whether the tab should be checked.
        position : QTabBar.ButtonPosition
            The position of the tab QCheckbox. By default, ButtonPosition.LeftSide.
        """
        idx = self.indexOf(key) if isinstance(key, QWidget) else key
        if tab_bar := self.tabBar():
            btn = tab_bar.tabButton(idx, position)
            if btn:
                cast("QCheckBox", btn).setChecked(checked)
        return None

    @overload
    def addTab(
        self,
        widget: None | QWidget,
        a1: None | str,
        /,
        *,
        position: QTabBar.ButtonPosition = ...,
        checked: bool = ...,
    ) -> int: ...

    @overload
    def addTab(
        self,
        widget: None | QWidget,
        icon: QIcon,
        label: None | str,
        /,
        *,
        position: QTabBar.ButtonPosition = ...,
        checked: bool = ...,
    ) -> int: ...

    def addTab(
        self,
        widget: None | QWidget,
        *args: Any,
        position: QTabBar.ButtonPosition = QTabBar.ButtonPosition.LeftSide,
        checked: bool = False,
    ) -> int:
        """Add a tab with a checkable QCheckbox.

        Parameters
        ----------
        widget : QWidget
            The widget to add to the tab.
        *args : Any
            The arguments to pass to the QTabWidget.addTab method.
        position : QTabBar.ButtonPosition
            The position of the tab QCheckbox. By default,
            QTabBar.ButtonPosition.LeftSide.
        checked : bool
            Whether the QCheckbox is checked. By default, False.
        """
        return self.insertTab(
            self.count(),
            widget,
            *args,
            position=position,
            checked=checked,
        )

    @overload
    def insertTab(
        self,
        index: int,
        widget: QWidget | None,
        a2: str | None,
        /,
        *,
        position: QTabBar.ButtonPosition = ...,
        checked: bool = ...,
    ) -> int: ...

    @overload
    def insertTab(
        self,
        index: int,
        widget: QWidget | None,
        icon: QIcon,
        label: str | None,
        /,
        *,
        position: QTabBar.ButtonPosition = ...,
        checked: bool = ...,
    ) -> int: ...

    def insertTab(
        self,
        index: int,
        widget: QWidget | None,
        *args: Any,
        position: QTabBar.ButtonPosition = QTabBar.ButtonPosition.LeftSide,
        checked: bool = False,
    ) -> int:
        """Insert `widget` in a tab with a checkable QCheckbox at the given index."""
        super().insertTab(index, widget, *args)
        cbox = QCheckBox(parent=self)
        # not sure why, but retaining a pointer to cbox seems to be necessary
        # for self.tabBar().tabButton(idx, position) to later return a QCheckBox
        # (instead of some other QWidget).
        self._cboxes.append(cbox)
        if widget is not None:
            widget.setEnabled(checked)
            cbox.toggled.connect(lambda c: self._on_tab_checkbox_toggled(c, widget))
        if tab_bar := self.tabBar():
            tab_bar.setTabButton(index, position, cbox)
            cbox.setChecked(checked)
        return index

    def _on_tab_checkbox_toggled(self, checked: bool, wdg: QWidget) -> None:
        """When checkbox is toggled, enable/disable the widget in the tab."""
        wdg.setEnabled(checked)
        tab_index = self.indexOf(wdg)
        if checked and self.change_tab_on_check:
            self.setCurrentIndex(tab_index)
        self.tabChecked.emit(tab_index, checked)
