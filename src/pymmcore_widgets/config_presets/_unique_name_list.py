from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, overload

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from collections.abc import Iterable


class UniqueListWidget(QListWidget):
    @overload
    def addItem(self, item: QListWidgetItem | None, /) -> None: ...
    @overload
    def addItem(self, label: str | None, /) -> None: ...
    def addItem(self, item: QListWidgetItem | str | None) -> None:
        if item is None:
            item = QListWidgetItem()
        txt = item.text() if isinstance(item, QListWidgetItem) else item
        for i in self._iter_texts():
            if i == txt:
                raise ValueError(f"Item with text {txt!r} already exists.")
        super().addItem(item)

    def addItems(self, labels: Iterable[str | None]) -> None:
        for label in labels:
            self.addItem(label)

    def _iter_texts(self) -> Iterable[str]:
        for i in range(self.count()):
            if item := self.item(i):
                yield item.text()


class UniqueKeyList(QWidget):
    """A QListWidget container that displays a list of unique keys.

    Buttons are provided to add, remove, and duplicate keys. The text of each key is
    editable, and the widget ensures that all keys are unique (*provided the API of the
    underlying QListWidget is not used directly*). Signals are emitted when keys are
    added, removed, or changed.

    Parameters
    ----------
    parent : QWidget | None
        The parent widget.
    base_key : str
        The base key used to generate new keys. Default is 'Item'.
    confirm_removal : bool
        Whether to confirm removal of items with a dialog. Default is True.
    """

    keyAdded = Signal(str, object)  # new key, old_key (if duplicated) | None
    keyRemoved = Signal(str)  # removed key
    keyChanged = Signal(str, str)  # new key, old key
    currentkeyChanged = Signal()
    # TODO: could possibly add removingKey, and changingKey signals if needed

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        base_key: str = "Item",
        confirm_removal: bool = True,
    ) -> None:
        super().__init__(parent)

        self._base_key = base_key
        self._confirm_removal = confirm_removal
        self._select_new_items = True
        self._default_flags = (
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )

        # stores the text of the currently selected item in case of editing
        self._active_item_text: str = ""
        # stores the texts of the items before the current item was changed
        self._previous_keys: set[str] = set()

        # WIDGETS ---------------------------------------------------

        self._list_widget = QListWidget(self)
        self._list_widget.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked
            | QListWidget.EditTrigger.SelectedClicked
        )

        self.btn_new = QPushButton("New")
        self.btn_remove = QPushButton("Remove...")
        self.btn_duplicate = QPushButton("Duplicate")

        # connections ------------------------------------

        self._list_widget.currentItemChanged.connect(self._on_current_item_changed)
        self._list_widget.itemChanged.connect(self._on_item_changed)

        self.btn_new.clicked.connect(self._add_unique_key)
        self.btn_remove.clicked.connect(self._remove_current)
        self.btn_duplicate.clicked.connect(self._duplicate_current)

        # layout ---------------------------------------------------

        # public so that subclasses can add more buttons

        self.btn_layout = QVBoxLayout()
        self.btn_layout.addWidget(self.btn_new)
        self.btn_layout.addWidget(self.btn_remove)
        self.btn_layout.addWidget(self.btn_duplicate)
        self.btn_layout.addStretch()

        layout = QHBoxLayout(self)
        layout.addWidget(self._list_widget)
        layout.addLayout(self.btn_layout)

    # PUBLIC API ---------------------------------------------------

    def listWidget(self) -> QListWidget:
        """Return the QListWidget used to display the keys.

        Note that directly using the QListWidget API can bypass the uniqueness checks
        and emissions of signals. Use with caution.
        """
        return self._list_widget

    def clear(self) -> None:
        """Clear all keys from the list."""
        self._list_widget.clear()

    def addKey(self, key: str | QListWidgetItem) -> None:
        """Add a key to the list.

        Parameters
        ----------
        key : str | QListWidgetItem
            The key to add. If a QListWidgetItem is provided, its text must be unique.

        Raises
        ------
        ValueError
            If the key is already in the list.
        """
        if isinstance(key, QListWidgetItem):
            item, txt = key, key.text()
        else:
            txt = str(key)
            item = QListWidgetItem(txt)

        if any(i == txt for i in self._iter_texts()):
            raise ValueError(f"Item with text {txt!r} already exists.")

        item.setFlags(self._default_flags)
        self._list_widget.addItem(item)
        self.keyAdded.emit(txt, None)

        # select the new item
        if self._select_new_items:
            self._list_widget.setCurrentRow(self._list_widget.count() - 1)

    def addKeys(self, keys: Iterable[str]) -> None:
        """Add multiple keys to the list.

        Raises
        ------
        ValueError
            If any of the keys are already in the list.
        """
        with signals_blocked(self):
            for key in keys:
                self.addKey(key)

        # slightly hacky... this is to ensure that the currentkeyChanged signal
        # is emitted only once after all keys have been added
        for key in keys:
            self.keyAdded.emit(key, None)
        self.currentkeyChanged.emit()

    def removeKey(self, key: str | int) -> None:
        """Remove a key from the list.

        Parameters
        ----------
        key : str | int
            The key to remove. If a string is provided, the first item with that text
            will be removed. If an integer is provided, the item at that index will be
            removed.
        """
        if isinstance(key, int):
            idx: int = key
        else:
            for i, txt in enumerate(self._iter_texts()):
                if txt == key:
                    idx = i
                    break
            else:  # key not found
                return

        # NOTE! takeItem will result in current Item changing, which will trigger
        # _on_current_item_changed BEFORE the item is actually removed.
        # so we need to update self._previous_keys manually here
        if item := self._list_widget.takeItem(idx):
            self._previous_keys = set(self._iter_texts())
            self.keyRemoved.emit(item.text())

    def currentkey(self) -> str | None:
        """Return the text of the currently selected item."""
        if (current := self._list_widget.currentItem()) is not None:
            return current.text()  # type: ignore [no-any-return]
        return None

    def setCurrentkey(self, key: str) -> None:
        """Set the currently selected item by its text."""
        if key == self.currentkey():
            return
        for i, txt in enumerate(self._iter_texts()):
            if txt == key:
                self._list_widget.setCurrentRow(i)
                return
        warnings.warn(f"Item with text {key!r} not found.", stacklevel=2)

    def setConfirmRemoval(self, confirm: bool) -> None:
        """Set whether to confirm removal of items with a dialog."""
        self._confirm_removal = confirm

    def setSelectNewItems(self, select: bool) -> None:
        """Set whether to select new items after adding them."""
        self._select_new_items = select

    def setDefaultFlags(self, flags: Qt.ItemFlag) -> None:
        """Set the default flags for new items."""
        self._default_flags = flags

    def setBaseKey(self, base_key: str) -> None:
        """Set the base key used to generate new keys.

        By default, the base key is 'Item'.
        """
        self._base_key = base_key

    # PRIVATE ---------------------------------------------------

    def _iter_texts(self) -> Iterable[str]:
        """Convenience method to iterate over the texts of the items."""
        for i in range(self._list_widget.count()):
            if item := self._list_widget.item(i):
                yield item.text()

    def _next_unique_key(self, base_key: str | None = None) -> str:
        """Return the next unique key in the form 'base_key [i?]'."""
        if base_key is None:
            base_key = self._base_key

        new_key = base_key
        existing = set(self._iter_texts())
        i = 1
        # NOTE: if an intermediate key is removed, it will be reused
        while new_key in existing:
            new_key = f"{base_key} {i}"
            i += 1
        return new_key

    def _add_unique_key(self) -> None:
        """Add a new item to the list."""
        self.addKey(self._next_unique_key())

    def _remove_current(self) -> None:
        """Remove the currently selected item."""
        if (current := self._list_widget.currentItem()) is None:
            return

        if self._confirm_removal:
            if (
                QMessageBox.question(
                    self,
                    "Remove Preset",
                    f"Are you sure you want to remove {current.text()!r}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.No
            ):
                return

        self.removeKey(self._list_widget.currentRow())

    def _duplicate_current(self) -> None:
        """Create a new key by duplicating the currently selected key."""
        if (current := self._list_widget.currentItem()) is None:
            return

        # get current key and create a new unique key based on it
        base_key = current.text()
        new_key = self._next_unique_key(f"{base_key} Copy")
        # add the new key, but block signals so that we can emit
        # the keyAdded signal with the old key (which implies duplication)
        with signals_blocked(self):
            self.addKey(new_key)
        self.keyAdded.emit(new_key, base_key)

    def _on_current_item_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        """Called whenever the *current* item changes (not its data)."""
        self._previous_keys = set(self._iter_texts())
        if current is not None:
            # Store the text of the current item so that we can check for duplicates
            # if the item is later edited.
            prev_text, self._active_item_text = self._active_item_text, current.text()
            # emit signal if the key has changed
            if prev_text != self._active_item_text:
                self.currentkeyChanged.emit()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """Called whenever the data of item has changed.."""
        new_text, previous_text = item.text(), self._active_item_text
        if new_text != previous_text and new_text in self._previous_keys:
            QMessageBox.warning(self, "Duplicate Item", f"{new_text!r} already exists.")
            item.setText(previous_text)
            return

        # it's a valid change
        self._active_item_key = new_text
        self.keyChanged.emit(new_text, previous_text)
