from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Iterable, cast

from fonticon_mdi6 import MDI6
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHeaderView,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._column_info import ColumnInfo

if TYPE_CHECKING:
    from typing import Any, Iterator

    ValueWidget = type[QCheckBox | QSpinBox | QDoubleSpinBox | QComboBox]
    from PyQt6.QtGui import QAction

    Record = dict[str, Any]
else:
    from qtpy.QtGui import QAction


class DataTable(QTableWidget):
    valueChanged = Signal()

    COLUMNS: ClassVar[tuple[ColumnInfo, ...]] = ()

    def __init_subclass__(cls) -> None:
        # this isn't covered in tests, because all of our subclasses are from
        # DataTableWidget instead of this class directly
        cls.COLUMNS = tuple(  # pragma: no cover
            i for i in cls.__dict__.values() if isinstance(i, ColumnInfo)
        )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, 0, parent=parent)

        self.verticalHeader().setVisible(False)
        h_header = cast("QHeaderView", self.horizontalHeader())
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # these have been gathered during __init_subclass__
        self.addColumns(getattr(parent, "COLUMNS", self.COLUMNS))

        # when a new row is inserted, populate it with default values
        self.itemChanged.connect(self.valueChanged)
        self.model().rowsInserted.connect(self._on_rows_inserted)
        self.model().rowsRemoved.connect(self.valueChanged)

    def columnInfo(self, col: int) -> ColumnInfo | None:
        if header_item := self.horizontalHeaderItem(col):
            return cast("ColumnInfo", header_item.data(ColumnInfo._ROLE))
        return None  # pragma: no cover

    def addColumns(self, column_info: Iterable[ColumnInfo]) -> None:
        cols = list(column_info)
        if cols:
            with signals_blocked(self):
                for i in column_info:
                    self.addColumn(i)
            self.valueChanged.emit()

    # This could possibly be moved back to columnsInserted...
    def addColumn(self, column_info: ColumnInfo, position: int | None = None) -> None:
        """Add a new column to the table.

        The ColumnInfo object is stored in the header item's data and used to populate
        the new column, and new rows that are added later, based on the data type and
        other info in the ColumnInfo object.
        """
        if position is None:
            col = self.columnCount()
        elif position < 0:
            col = position + self.columnCount() + 1
        else:
            col = int(position)
        self.insertColumn(col)

        header_item = QTableWidgetItem(column_info.header_text())
        header_item.setData(ColumnInfo._ROLE, column_info)
        self.setHorizontalHeaderItem(col, header_item)

        self._populate_new_column(column_info, col=col)
        if column_info.hidden:
            self.setColumnHidden(col, True)

    def indexOf(self, header: str | ColumnInfo) -> int:
        if isinstance(header, ColumnInfo):
            for col in range(self.columnCount()):
                if (info := self.columnInfo(col)) and info.key == header.key:
                    return col
        else:
            for col in range(self.columnCount()):
                header_item = self.horizontalHeaderItem(col)
                if header_item and header_item.text() == header:
                    return col
        return -1

    def iterRecords(
        self, exclude_unchecked: bool = False, exclude_hidden_cols: bool = False
    ) -> Iterator[Record]:
        """Return an iterator over the data in the table in records format.

        (Records are a list of dicts mapping {'column header' -> value} for each row.)
        """
        selector_col = self._get_selector_col() if exclude_unchecked else -1
        for row in range(self.rowCount()):
            if self._is_row_checked(row, selector_col):
                if data := self.rowData(row, exclude_hidden_cols):
                    yield data

    def setValue(self, records: Iterable[Record]) -> None:
        """Set the value of the table."""
        self.setRowCount(0)
        _records = list(records)
        self.setRowCount(len(_records))
        for row, record in enumerate(_records):
            self.setRowData(row, record)

    def checkAllRows(self) -> None:
        self._check_all(Qt.CheckState.Checked)

    def clearChecks(self) -> None:
        self._check_all(Qt.CheckState.Unchecked)

    def rowData(self, row: int, exclude_hidden_cols: bool = False) -> Record:
        d: Record = {}
        for col in range(self.columnCount()):
            if exclude_hidden_cols and self.isColumnHidden(col):
                continue
            if info := self.columnInfo(col):
                d.update(info.get_cell_data(self, row, col))
        return d

    def setRowData(self, row: int, data: Record) -> None:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data)}")  # pragma: no cover

        for col in range(self.columnCount()):
            if info := self.columnInfo(col):
                if info.key in data:
                    info.set_cell_data(self, row, col, data[info.key])

    # ############################## Private #################

    def _is_row_checked(self, row: int, selector_col: int) -> bool:
        if selector_col < 0:
            return True

        if info := self.columnInfo(selector_col):
            return info.isChecked(self, row, selector_col)

        return False  # pragma: no cover

    def _check_all(self, state: Qt.CheckState) -> None:
        if (selector_col := self._get_selector_col()) >= 0:
            for row in range(self.rowCount()):
                if info := self.columnInfo(selector_col):
                    info.setCheckState(self, row, selector_col, state)

                # if item := self.item(row, selector_col):
                #     item.setCheckState(state)

    def _get_selector_col(self) -> int:
        for col in range(self.columnCount()):
            if info := self.columnInfo(col):
                if info.is_row_selector:
                    return col
        return -1  # pragma: no cover

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        # when a new row is inserted by any means, populate it with default values
        # this is connected above in __init_ with self.model().rowsInserted.connect
        with signals_blocked(self):
            for row_idx in range(start, end + 1):
                self._populate_new_row(row_idx)
        self.valueChanged.emit()

    def _populate_new_row(self, row: int) -> None:
        for col in range(self.columnCount()):
            if column_info := self.columnInfo(col):
                column_info.init_cell(self, row, col, self.valueChanged)

    def _populate_new_column(self, column_info: ColumnInfo, col: int) -> None:
        """Add default values/widgets to a newly created column."""
        for row in range(self.rowCount()):
            column_info.init_cell(self, row, col, self.valueChanged)
        self.valueChanged.emit()


class DataTableWidget(QWidget):
    valueChanged = Signal()

    COLUMNS: ClassVar[tuple[ColumnInfo, ...]]

    def __init_subclass__(cls) -> None:
        cols = {}  # use a dict to avoid duplicates
        # superclasses too, but subclasses override superclasses
        for base in reversed(cls.__mro__):
            cols.update(
                {i.key: i for i in base.__dict__.values() if isinstance(i, ColumnInfo)}
            )
        cls.COLUMNS = tuple(cols.values())

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(parent=parent)

        # -------- table --------

        self._table = DataTable(rows, self)
        self._table.valueChanged.connect(self.valueChanged)

        # -------- actions (for toolbar below) --------
        # fmt: off
        red = "#C33"
        green = "#3A3"
        gray = "#666"

        self.act_add_row = QAction(icon(MDI6.plus_thick, color=green), "Add new row", self) # noqa
        self.act_add_row.triggered.connect(self._add_row)

        self.act_check_all = QAction(icon(MDI6.checkbox_multiple_marked_outline, color=gray), "Select all rows", self)  # noqa
        self.act_check_all.triggered.connect(self._check_all)

        self.act_check_none = QAction(icon(MDI6.checkbox_multiple_blank_outline, color=gray), "Clear selection", self)  # noqa
        self.act_check_none.triggered.connect(self._check_none)

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
        self._toolbar.setIconSize(QSize(22, 22))

        # add spacer to pin buttons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._toolbar.addWidget(spacer)

        # add actions (makes them QToolButtons)
        self._toolbar.addAction(self.act_add_row)
        self._toolbar.addSeparator()  # ------------
        self._toolbar.addAction(self.act_check_all)
        self._toolbar.addAction(self.act_check_none)
        # self._toolbar.addSeparator()  # ------------
        # self._toolbar.addAction(self.act_move_up)
        # self._toolbar.addAction(self.act_move_down)
        self._toolbar.addSeparator()  # ------------
        self._toolbar.addAction(self.act_remove_row)
        self._toolbar.addAction(self.act_clear)

        # -------- layout --------
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._table)

    # ################ Public methods ####################

    def table(self) -> DataTable:
        return self._table

    def toolBar(self) -> QToolBar:
        return self._toolbar

    def value(self, exclude_unchecked: bool = True) -> Any:
        """Return a list of dicts of the data in the table."""
        return list(self._table.iterRecords(exclude_unchecked=exclude_unchecked))

    def setValue(self, value: Iterable[Any]) -> None:
        """Set the value of the table."""
        with signals_blocked(self):
            self._table.setValue(value)

    # #################### Private methods ####################

    def _add_row(self) -> None:
        """Add a new to the end of the table."""
        # this method is only called when act_add_row is triggered
        # not anytime a row is added programmatically
        self._table.insertRow(self._table.rowCount())

    def _check_all(self) -> None:
        """Remove all rows."""
        self._table.checkAllRows()

    def _check_none(self) -> None:
        """Remove all rows."""
        self._table.clearChecks()

    def _remove_selected(self) -> None:
        """Remove selected row(s)."""
        for i in self._selected_rows(reverse=True):
            self._table.removeRow(i)

    def _remove_all(self) -> None:
        """Remove all rows."""
        self._table.setRowCount(0)

    def _selected_rows(self, reverse: bool = False) -> list[int]:
        """Return a list of selected row indices."""
        return sorted({i.row() for i in self._table.selectedIndexes()}, reverse=reverse)
