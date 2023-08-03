from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Generic, NamedTuple, TypeVar, cast

import pint
from fonticon_mdi6 import MDI6
from PyQt6.QtGui import QValidator
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

if TYPE_CHECKING:
    from typing import Any, Callable, Iterator, Sequence

    ValueWidget = type[QCheckBox | QSpinBox | QDoubleSpinBox | QComboBox]
    from PyQt6.QtGui import QAction

    Record = dict[str, Any]
else:
    from qtpy.QtGui import QAction


@dataclass(frozen=True)
class ColumnMeta:
    """Dataclass for storing metadata about a column in a table widget."""

    key: str
    header: str | None = None
    type: WdgGetSet | type = str
    default: Any = None
    checkable: bool = False
    checked: bool = True
    hidden: bool = False
    minimum: int | None = None
    maximum: int | None = None
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter
    resize_mode: QHeaderView.ResizeMode = QHeaderView.ResizeMode.ResizeToContents

    # role used to store ColumnMeta in header items
    _ROLE: ClassVar[int] = Qt.ItemDataRole.UserRole + 1

    def header_text(self) -> str:
        return self.header or self.key.title().replace("_", " ")

    def __post_init__(self) -> None:
        if not isinstance(self.type, (WdgGetSet, type)):  # pragma: no cover
            raise TypeError(
                f"type argument must be a type or WdgGetSet, not {self.type!r}"
            )
        if self.checkable and self.type != str:  # pragma: no cover
            raise ValueError("Only string columns can be checkable")

        if (
            self.default is not None
            and self.type is str
            and not isinstance(self.default, str)
        ):
            object.__setattr__(self, "type", type(self.default))

    @property
    def choices(self) -> Sequence[str]:
        if isinstance(self.type, type) and issubclass(self.type, enum.Enum):
            return [i.value for i in self.type]
        return []

    @property
    def CheckState(self) -> Qt.CheckState | None:
        if self.checkable:
            return Qt.CheckState.Checked if self.checked else Qt.CheckState.Unchecked
        return None

    def wdg_get_set(self) -> WdgGetSet | None:
        return None if self.type is str else _get_wdg_get_set(self.type)


CHECKABLE = (
    Qt.ItemFlag.ItemIsUserCheckable
    | Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsEditable
    | Qt.ItemFlag.ItemIsSelectable
)


T = TypeVar("T")
W = TypeVar("W", bound=QWidget)


class WdgGetSet(NamedTuple, Generic[W, T]):
    widget: type[W]
    setter: Callable[[W, T], None]
    getter: Callable[[W], T]


class _TableSpinboxMixin:
    def __init__(self: QDoubleSpinBox | QSpinBox) -> None:
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setKeyboardTracking(False)
        self.setMaximum(10001)
        self.setMinimumWidth(70)
        self.setStyleSheet("QAbstractSpinBox { border: none; }")

    # disable mouse wheel scrolling on table spinboxes
    def wheelEvent(self, event: Any) -> None:
        pass  # pragma: no cover


class _CenteredCheckBox(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._checkbox = QCheckBox()
        layout.addWidget(self._checkbox)

    def isChecked(self) -> bool:
        return self._checkbox.isChecked()  # type: ignore

    def setChecked(self, value: bool) -> None:
        self._checkbox.setChecked(value)


class QQuantityValidator(QValidator):
    def __init__(
        self,
        dimensionality: str | None = None,
        ureg: pint.UnitRegistry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.dimensionality = dimensionality
        self.ureg = ureg or pint.application_registry

    def validate(self, a0: str | None, a1: int) -> tuple[QValidator.State, str, int]:
        if self.is_valid(a0):
            return (QValidator.State.Acceptable, a0, a1)
        return (QValidator.State.Intermediate, a0 or "", a1)

    def is_valid(self, text: str | None) -> bool:
        if not text:
            return False
        try:
            q = self.ureg.parse_expression(text)
            if self.dimensionality:
                return isinstance(q, pint.Quantity) and bool(
                    q.is_compatible_with(self.dimensionality)
                )
            return True
        except pint.UndefinedUnitError:
            return False


class QQuantityLineEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._validator = QQuantityValidator(parent=self)
        self.setValidator(self._validator)
        self._last_valid: str = self.text()
        self.editingFinished.connect(self._on_editing_finished)

    def setDimensionality(self, dimensionality: str | None) -> None:
        self._validator.dimensionality = dimensionality

    def setUreg(self, ureg: pint.UnitRegistry) -> None:
        if not isinstance(ureg, pint.UnitRegistry):
            raise TypeError(f"ureg must be a pint.UnitRegistry, not {type(ureg)}")
        self._validator.ureg = ureg

    def focusOutEvent(self, event: Any) -> None:
        # When the widget loses focus, check if the text is valid
        self._on_editing_finished()
        super().focusOutEvent(event)

    def setText(self, value: str | None) -> None:
        if not self._validator.is_valid(value):
            raise ValueError(f"Invalid value: {value!r}")
        super().setText(value)
        self._last_valid = cast(str, value)

    def _on_editing_finished(self) -> None:
        # When the editing is finished, check if the final text is valid
        final_text = self.text()
        if self._validator.is_valid(final_text):
            self._last_valid = final_text
            self.setText(f"{self.quantity():~P}")  # short pretty format
        else:
            self.setText(self._last_valid)

    def quantity(self) -> pint.Quantity:
        return self._validator.ureg.parse_expression(self.text())


class QTimeLineEdit(QQuantityLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDimensionality("second")
        self.setStyleSheet("QLineEdit { border: none; }")


class TableDoubleSpinBox(QDoubleSpinBox, _TableSpinboxMixin):
    pass


class TableSpinBox(QSpinBox, _TableSpinboxMixin):
    pass


TYPE_TO_WDG: dict[type, WdgGetSet] = {
    bool: WdgGetSet(
        _CenteredCheckBox, _CenteredCheckBox.setChecked, _CenteredCheckBox.isChecked
    ),
    int: WdgGetSet(TableSpinBox, QSpinBox.setValue, QSpinBox.value),
    float: WdgGetSet(TableDoubleSpinBox, QDoubleSpinBox.setValue, QDoubleSpinBox.value),
    enum.Enum: WdgGetSet(
        QComboBox,
        lambda w, v: QComboBox.setCurrentText(w, str(v.value)),
        QComboBox.currentText,
    ),
    pint.Quantity: WdgGetSet(QTimeLineEdit, QTimeLineEdit.setText, QTimeLineEdit.text),
}


def _get_wdg_get_set(type_: type | WdgGetSet) -> WdgGetSet:
    if isinstance(type_, WdgGetSet):
        return type_  # pragma: no cover
    for t, wdg_type in TYPE_TO_WDG.items():
        if issubclass(type_, t):
            return wdg_type
    raise TypeError(f"Unsupported type: {type_!r}")  # pragma: no cover


class _DataTable(QWidget, Generic[T]):
    COLUMNS: ClassVar[tuple[ColumnMeta, ...]]

    def __init_subclass__(cls) -> None:
        cls.COLUMNS = tuple(
            i for i in cls.__dict__.values() if isinstance(i, ColumnMeta)
        )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(parent=parent)

        # -------- table --------
        self._table = QTableWidget(rows, 0, self)
        self._table.verticalHeader().setVisible(False)
        h_header = cast("QHeaderView", self._table.horizontalHeader())
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # when a new row is inserted, populate it with default values
        self._table.model().rowsInserted.connect(self._on_rows_inserted)

        # -------- actions (for toolbar below) --------
        # fmt: off
        red = "#C33"
        green = "#3A3"
        gray = "#666"

        self.act_add_row = QAction(icon(MDI6.plus_thick, color=green), "Add new row", self) # noqa
        self.act_add_row.triggered.connect(self._add_row)

        self.act_select_all = QAction(icon(MDI6.select_all, color=gray), "Select all rows", self)  # noqa
        self.act_select_all.triggered.connect(self.table.selectAll)

        self.act_select_none = QAction(icon(MDI6.select_remove, color=gray), "Clear selection", self)  # noqa
        self.act_select_none.triggered.connect(self.table.clearSelection)

        # hard to implement so far
        # self.act_move_up = QAction(icon(MDI6.arrow_up_thin, color=gray), "Move selected row up", self)  # noqa
        # self.act_move_up.triggered.connect(self._move_selected_rows_up)

        # self.act_move_down = QAction(icon(MDI6.arrow_down_thin, color=gray), "Move selected row down", self)  # noqa
        # self.act_move_down.triggered.connect(self._move_selected_rows_down)

        self.act_remove_row = QAction(icon(MDI6.close_box_outline, color=red), "Remove selected row", self)  # noqa
        self.act_remove_row.triggered.connect(self._remove_selected)

        self.act_clear = QAction(icon(MDI6.close_box_multiple_outline, color=red), "Remove all rows", self)  # noqa
        self.act_clear.triggered.connect(self._remove_all)
        # fmt: on

        # -------- toolbar --------
        self._toolbar = QToolBar(self)
        self._toolbar.setFloatable(False)
        self._toolbar.setIconSize(QSize(20, 20))

        # add spacer to pin buttons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._toolbar.addWidget(spacer)

        # add actions (makes them QToolButtons)
        self._toolbar.addAction(self.act_add_row)
        self._toolbar.addSeparator()  # ------------
        self._toolbar.addAction(self.act_select_all)
        self._toolbar.addAction(self.act_select_none)
        # self._toolbar.addSeparator()  # ------------
        # self._toolbar.addAction(self.act_move_up)
        # self._toolbar.addAction(self.act_move_down)
        self._toolbar.addSeparator()  # ------------
        self._toolbar.addAction(self.act_remove_row)
        self._toolbar.addAction(self.act_clear)

        # -------- layout --------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._table)

        for i in self.COLUMNS:
            self.addColumn(i)

    # ################ New Public methods ####################

    @property
    def table(self) -> QTableWidget:
        return self._table

    @property
    def toolbar(self) -> QToolBar:
        return self._toolbar

    def columnMeta(self, col: int) -> ColumnMeta | None:
        if header_item := self.table.horizontalHeaderItem(col):
            return cast("ColumnMeta", header_item.data(ColumnMeta._ROLE))
        return None  # pragma: no cover

    def indexOf(self, header: str | ColumnMeta) -> int:
        if isinstance(header, ColumnMeta):
            for col in range(self.columnCount()):
                if (meta := self.columnMeta(col)) and meta.key == header.key:
                    return col
        else:
            for col in range(self.columnCount()):
                header_item = self.table.horizontalHeaderItem(col)
                if header_item and header_item.text() == header:
                    return col
        return -1

    def iterRecords(self, exclude_unchecked: bool = False) -> Iterator[Record]:
        """Return an iterator over the data in the table in records format.

        (Records are a list of dicts mapping {'column header' -> value} for each row.)
        """
        for row in range(self.rowCount()):
            d = self._row_data(row)
            if not (d.pop("checked", None) is False and exclude_unchecked):
                yield d

    def value(self, exclude_unchecked: bool = False) -> T:
        """Return the current value of the table as a list of records."""
        raise NotImplementedError("Must be implemented by subclass")

    def _row_data(self, row: int) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for col in range(self.columnCount()):
            if meta := self.columnMeta(col):
                if meta.type == str:
                    if item := self.table.item(row, col):
                        d[meta.key] = item.text()
                        if meta.checkable:
                            d["checked"] = item.checkState() is Qt.CheckState.Checked
                elif widget_get_set := meta.wdg_get_set():
                    if wdg := self.table.cellWidget(row, col):
                        d[meta.key] = widget_get_set.getter(wdg)
        return d

    # not used yet
    # def _set_row_data(self, row: int, data: dict[str, Any]) -> None:
    #     for col in range(self.columnCount()):
    #         if not (meta := self.columnMeta(col)):
    #             continue
    #         if meta.type == str:
    #             if not (item := self.table.item(row, col)):
    #                 continue
    #             item.setText(data[meta.key])
    #             if meta.checkable:
    #                 item.setCheckState(
    #                     Qt.CheckState.Checked
    #                     if data.get("checked", True)
    #                     else Qt.CheckState.Unchecked
    #                 )
    #         else:
    #             widget_get_set = _get_wdg_get_set(meta.type)
    #             if wdg := self.table.cellWidget(row, col):
    #                 widget_get_set.setter(wdg, data[meta.key])

    # This could possibly be moved back to columnsInserted...
    def addColumn(
        self, column_meta: ColumnMeta, position: int | None = None
    ) -> ColumnMeta:
        """Add a new column to the table.

        The ColumnMeta object is stored in the header item's data and used to populate
        the new column, and new rows that are added later, based on the data type and
        other info in the ColumnMeta object.
        """
        if position is None:
            position = self.columnCount()
        elif position < 0:
            position += self.columnCount() + 1
        self.table.insertColumn(position)

        header_item = QTableWidgetItem(column_meta.header_text())
        header_item.setData(ColumnMeta._ROLE, column_meta)
        self.table.setHorizontalHeaderItem(position, header_item)

        self._populate_new_column(column_meta, col=position)
        if column_meta.hidden:
            self.table.setColumnHidden(position, True)

        return column_meta

    # #################### passed to self.table ####################

    def rowCount(self) -> int:
        return self.table.rowCount()  # type: ignore

    def columnCount(self) -> int:
        return self.table.columnCount()  # type: ignore

    # ####################

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        # when a new row is inserted by any means, populate it with default values
        for row_idx in range(start, end + 1):
            self._populate_new_row(row_idx)

    def _populate_new_row(self, row: int) -> None:
        for col in range(self.columnCount()):
            if column_meta := self.columnMeta(col):
                self._set_cell_default(row, col, column_meta)

    def _populate_new_column(self, column_meta: ColumnMeta, col: int) -> None:
        """Add default values/widgets to a newly created column."""
        for row in range(self.rowCount()):
            self._set_cell_default(row, col, column_meta)

    def _set_cell_default(self, row: int, col: int, column_meta: ColumnMeta) -> None:
        # for strings, use the standard QTableWidgetItem
        default = column_meta.default
        if (wdg_get_set := column_meta.wdg_get_set()) is None:
            # make a new QTableWidgetItem with the default value
            d = default.format(idx=row + 1) if isinstance(default, str) else default
            item = QTableWidgetItem(str(d))
            if (check_state := column_meta.CheckState) is not None:
                # note: it's important to call setCheckState either way
                # otherwise the checkbox will not be visible
                item.setFlags(CHECKABLE)
                item.setCheckState(check_state)
            self.table.setItem(row, col, item)

        # create a new custom CellWidget for other column types
        else:
            new_wdg = wdg_get_set.widget()
            if column_meta.choices and hasattr(new_wdg, "addItems"):
                new_wdg.addItems(column_meta.choices)
            if default is not None:
                wdg_get_set.setter(new_wdg, default)

            if column_meta.minimum is not None and hasattr(new_wdg, "setMinimum"):
                new_wdg.setMinimum(column_meta.minimum)
            if column_meta.maximum is not None and hasattr(new_wdg, "setMaximum"):
                new_wdg.setMaximum(column_meta.maximum)
            if column_meta.alignment and hasattr(new_wdg, "setAlignment"):
                new_wdg.setAlignment(column_meta.alignment)

            header = cast("QHeaderView", self.table.horizontalHeader())
            header.setSectionResizeMode(col, column_meta.resize_mode)
            self.table.setCellWidget(row, col, new_wdg)

    def _add_row(self) -> None:
        """Add a new to the end of the table."""
        self.table.insertRow(self.rowCount())

    def _remove_selected(self) -> None:
        """Remove selected row(s)."""
        for i in self._selected_rows(reverse=True):
            self.table.removeRow(i)

    def _remove_all(self) -> None:
        """Remove all rows."""
        self.table.setRowCount(0)

    def _selected_rows(self, reverse: bool = False) -> list[int]:
        """Return a list of selected row indices."""
        return sorted({i.row() for i in self.table.selectedIndexes()}, reverse=reverse)


class DataTable(_DataTable[list["Record"]]):
    def value(self, exclude_unchecked: bool = False) -> list[Record]:
        """Return the current value of the table as a list of records."""
        return list(self.iterRecords(exclude_unchecked=exclude_unchecked))
