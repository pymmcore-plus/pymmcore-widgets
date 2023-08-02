from __future__ import annotations

import enum
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Iterator

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHeaderView,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from superqt import QQuantity

if TYPE_CHECKING:
    from ast import Tuple

    ValueWidget = type[QCheckBox | QSpinBox | QDoubleSpinBox | QComboBox]


COLUMN_META_ROLE = Qt.ItemDataRole.UserRole + 1
CHECKABLE = (
    Qt.ItemFlag.ItemIsUserCheckable
    | Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsEditable
)
TYPE_TO_WDG: dict[type, tuple[ValueWidget, str]] = {
    bool: (QCheckBox, "setChecked"),
    int: (QSpinBox, "setValue"),
    float: (QDoubleSpinBox, "setValue"),
    enum.Enum: (QComboBox, "setCurrentText"),
}


@dataclass
class Column:
    key: str
    type: type = str  # todo: make type | tuple[QWidget, str, str]  # wdg, setter, gettr
    default: Any = None
    checkable: bool = False
    checked: bool = True
    hidden: bool = False
    position: int | None = None


class _DataTable(QTableWidget):
    COLUMNS: ClassVar[Tuple[Column, ...]] = ()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setRowCount(3)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for i in self.COLUMNS:
            self.addColumn(**asdict(i))

    def addColumn(
        self,
        key: str,
        type: type = str,
        default: Any = None,
        checkable: bool = False,
        checked: bool = False,
        hidden: bool = False,
        position: int | None = None,
    ) -> None:
        if checkable and type != str:
            raise ValueError("Only string columns can be checkable")

        if position is None:
            position = self.columnCount()
        elif position < 0:
            position = self.columnCount() + position + 1
        self.insertColumn(position)

        # Set the header item/label for the new column and store metadata
        header_item = QTableWidgetItem(key)
        column_metadata = Column(
            key=key,
            type=type,
            default=default,
            checkable=checkable,
            checked=checked,
            position=position,
        )
        header_item.setData(COLUMN_META_ROLE, column_metadata)
        self.setHorizontalHeaderItem(position, header_item)

        self._make_rows(column_metadata)

        if hidden:
            self.setColumnHidden(position, True)

    def _make_rows(self, meta: Column) -> None:
        # inside of addColumn... for each existing row, add a new item
        for row in range(self.rowCount()):
            # make a basic table item for strings
            if meta.type == str:
                if isinstance(meta.default, str):
                    _default = meta.default.format(idx=row + 1)
                else:
                    _default = meta.default
                item = QTableWidgetItem(str(_default))
                if meta.checkable:
                    item.setFlags(CHECKABLE)
                    st = (
                        Qt.CheckState.Checked
                        if meta.checked
                        else Qt.CheckState.Unchecked
                    )
                    item.setCheckState(st)
                self.setItem(row, meta.position, item)
                continue

            # custom widgets for other types
            if issubclass(meta.type, QWidget):
                wdg = type()
                if hasattr(wdg, "setValue"):
                    wdg.setValue(meta.default)
                self.setCellWidget(row, meta.position, wdg)

            for type_, wdg_type in TYPE_TO_WDG.items():
                if issubclass(meta.type, type_):
                    wdg_cls, setter = wdg_type
                    break
            else:
                raise TypeError(f"Unsupported type: {meta.type!r}")
            wdg = wdg_cls()
            if issubclass(meta.type, enum.Enum):
                wdg.addItems([i.value for i in meta.type])
            if meta.default is not None:
                getattr(wdg, setter)(meta.default)
            self.setCellWidget(row, meta.position, wdg)

    def indexOf(self, header: str | Column) -> int:
        if isinstance(header, Column):
            header = header.key
        for col in range(self.columnCount()):
            header_item = self.horizontalHeaderItem(col)
            if header_item and header_item.text() == header:
                return col
        return -1

    def records(self) -> Iterator[dict[str, Any]]:
        _records = []
        for row in range(self.rowCount()):
            d = {}
            for col in range(self.columnCount()):
                if header_item := self.horizontalHeaderItem(col):
                    meta: Column = header_item.data(COLUMN_META_ROLE)
                    if meta.type == str:
                        if meta.checkable:
                            d["checked"] = (
                                self.item(row, col).checkState()
                                is Qt.CheckState.Checked
                            )
                        d[meta.key] = self.item(row, col).text()
                    else:
                        wdg = self.cellWidget(row, col)
                        if issubclass(meta.type, enum.Enum):
                            d[meta.key] = meta.type(wdg.currentText())
                        elif hasattr(wdg, "value"):
                            d[meta.key] = wdg.value()
            _records.append(d)
        return _records

    # ======== THOUGHTS =======

    # def columnMetadata(self, column: int | str) -> ColumnMeta:
    #     if isinstance(column, str):
    #         for col in range(self.columnCount()):
    #             if (header := self.horizontalHeaderItem(col)).text() == column:
    #                 break
    #     else:
    #         header = self.horizontalHeaderItem(column)
    #     return header.data(COLUMN_META_ROLE)


class TimeTable(_DataTable):
    PHASE = Column(key="Phase", checkable=True, default="#{idx}")
    INTERVAL = Column(key="Interval", type=QQuantity, default="1 s")
    DURATION = Column(key="Duration", type=QQuantity, default="1 min")
    LOOPS = Column(key="Loops", type=int, default=1)

    COLUMNS = (PHASE, INTERVAL, DURATION, LOOPS)


class PositionTable(_DataTable):
    POSITION = Column(key="Position", checkable=True, default="#{idx}")
    X = Column(key="X [mm]", type=float, default=0)
    Y = Column(key="Y [mm]", type=float, default=0)
    Z = Column(key="Z [mm]", type=float, default=0)

    COLUMNS = (POSITION, X, Y, Z)


class TPositions(enum.Enum):
    """Enum for the different types of time positions."""

    ALL = "All"
    FIRST = "First"
    EVERY = "Every n-th"


class ChannelTable(_DataTable):
    CONFIG = Column(key="Config", checkable=True, default="#{idx}")
    GROUP = Column(key="Group", default="Channel", hidden=True)
    T_POS = Column(key="T Pos.", type=TPositions)
    DO_Z = Column(key="Do Z", type=bool, default=True)

    COLUMNS = (CONFIG, GROUP, T_POS, DO_Z)


if __name__ == "__main__":
    # app = QApplication([])
    w = PositionTable()
    w.show()
    # app.exec_()
