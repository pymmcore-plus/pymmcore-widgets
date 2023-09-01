from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Callable, ClassVar, Generic, Iterable, TypeVar, cast

import pint
from qtpy.QtCore import Qt, Signal, SignalInstance
from qtpy.QtGui import QFocusEvent, QValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

if TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True)
class ColumnInfo:
    # role used to store ColumnMeta in header items
    _ROLE: ClassVar[int] = Qt.ItemDataRole.UserRole + 1

    key: str
    data_type: type | WdgGetSet
    header: str | None = None
    is_row_selector: bool = False
    hidden: bool = False
    default: Any = None

    def header_text(self) -> str:
        return self.header or self.key.title().replace("_", " ")

    def init_cell(
        self, table: QTableWidget, row: int, col: int, change_signal: SignalInstance
    ) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    def get_cell_data(self, table: QTableWidget, row: int, col: int) -> dict[str, Any]:
        raise NotImplementedError("Must be implemented by subclass")

    def set_cell_data(
        self, table: QTableWidget, row: int, col: int, value: Any
    ) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    def isChecked(self, table: QTableWidget, row: int, col: int) -> bool:
        return False

    def setCheckState(
        self, table: QTableWidget, row: int, col: int, checked: bool
    ) -> None:
        pass


CHECKABLE_FLAGS = (
    Qt.ItemFlag.ItemIsUserCheckable
    | Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsEditable
    | Qt.ItemFlag.ItemIsSelectable
)


@dataclass(frozen=True)
class TextColumn(ColumnInfo):
    """Column that will use a standard QTableWidgetItem."""

    key: str
    data_type: type = str
    header: str | None = None
    is_row_selector: bool = False
    hidden: bool = False
    default: str | None = None
    checkable: bool = False
    checked: bool = True

    def init_cell(
        self, table: QTableWidget, row: int, col: int, change_signal: SignalInstance
    ) -> None:
        # make a new QTableWidgetItem with the default value
        # default = self.default.format(idx=row + 1) if self.default else ""
        item = QTableWidgetItem(self.default)

        if self.is_row_selector or self.checkable:
            ch = Qt.CheckState.Checked if self.checked else Qt.CheckState.Unchecked
            item.setFlags(CHECKABLE_FLAGS)
            # note: it's important to call setCheckState either way
            # otherwise the checkbox will not be visible
            item.setCheckState(ch)

        table.setItem(row, col, item)

    def get_cell_data(self, table: QTableWidget, row: int, col: int) -> dict[str, Any]:
        if item := table.item(row, col):
            return {self.key: item.text()}
        return {}

    def set_cell_data(
        self, table: QTableWidget, row: int, col: int, value: Any
    ) -> None:
        if value is not None and (item := table.item(row, col)):
            item.setText(value)
            # Checkstate?

    def isChecked(self, table: QTableWidget, row: int, col: int) -> bool:
        if item := table.item(row, col):
            return bool(item.checkState() == Qt.CheckState.Checked)
        return False

    def setCheckState(
        self, table: QTableWidget, row: int, col: int, state: Qt.CheckState
    ) -> None:
        if item := table.item(row, col):
            item.setCheckState(state)


T = TypeVar("T")
W = TypeVar("W", bound=QWidget)


@dataclass(frozen=True)
class WdgGetSet(Generic[W, T]):
    widget: type[W]
    getter: Callable[[W], T]
    setter: Callable[[W, T], None]
    connect: Callable[[W, Callable[[T], None]], Any]


@dataclass(frozen=True)
class WidgetColumn(ColumnInfo, Generic[W, T]):
    key: str
    data_type: WdgGetSet[W, T]
    header: str | None = None
    is_row_selector: bool = False
    hidden: bool = False

    def _init_widget(self) -> W:
        return self.data_type.widget()  # type: ignore
        # if self.choices and hasattr(new_wdg, "addItems"):
        #     new_wdg.addItems(self.choices)

    def init_cell(
        self, table: QTableWidget, row: int, col: int, change_signal: SignalInstance
    ) -> None:
        new_wdg = self._init_widget()

        if self.default is not None:
            self.data_type.setter(new_wdg, self.default)

        # if self.alignment and hasattr(new_wdg, "setAlignment"):
        #     new_wdg.setAlignment(self.alignment)

        # header = cast("QHeaderView", self.table.horizontalHeader())
        # header.setSectionResizeMode(col, column_info.resize_mode)
        table.setCellWidget(row, col, new_wdg)
        self.data_type.connect(new_wdg, change_signal)

    def get_cell_data(self, table: QTableWidget, row: int, col: int) -> dict[str, Any]:
        if wdg := table.cellWidget(row, col):
            return {self.key: self.data_type.getter(cast(W, wdg))}
        return {}

    def set_cell_data(
        self, table: QTableWidget, row: int, col: int, value: Any
    ) -> None:
        if value is not None and (wdg := table.cellWidget(row, col)):
            self.data_type.setter(cast(W, wdg), value)


# ############################# Booleans ################################


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


TableBoolWidget = WdgGetSet(
    _CenteredCheckBox,
    _CenteredCheckBox.isChecked,
    _CenteredCheckBox.setChecked,
    lambda w, cb: w._checkbox.toggled.connect(cb),
)


@dataclass(frozen=True)
class BoolColumn(WidgetColumn):
    data_type: WdgGetSet = TableBoolWidget


# ############################# NUMBERS ################################


class _TableSpinboxMixin:
    def __init__(self: QDoubleSpinBox | QSpinBox) -> None:
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setKeyboardTracking(False)
        self.setMinimumWidth(70)
        self.setStyleSheet("QAbstractSpinBox { border: none; }")

    def wheelEvent(self, event: Any) -> None:
        # disable mouse wheel scrolling on table spinboxes
        pass  # pragma: no cover


class TableSpinBox(QSpinBox, _TableSpinboxMixin):
    pass


class TableDoubleSpinBox(QDoubleSpinBox, _TableSpinboxMixin):
    pass


TableIntWidget = WdgGetSet(
    TableSpinBox,
    TableSpinBox.value,
    TableSpinBox.setValue,
    lambda w, cb: w.valueChanged.connect(cb),
)


TableFloatWidget = WdgGetSet(
    TableDoubleSpinBox,
    TableDoubleSpinBox.value,
    TableDoubleSpinBox.setValue,
    lambda w, cb: w.valueChanged.connect(cb),
)


@dataclass(frozen=True)
class _RangeColumn(WidgetColumn, Generic[W, T]):
    data_type: WdgGetSet[W, float]
    minimum: float = 0
    maximum: float = 10_000

    def _init_widget(self) -> W:
        wdg = self.data_type.widget()

        if self.minimum is not None and hasattr(wdg, "setMinimum"):
            wdg.setMinimum(self.minimum)
        if self.maximum is not None and hasattr(wdg, "setMaximum"):
            wdg.setMaximum(self.maximum)

        return wdg  # type: ignore


@dataclass(frozen=True)
class IntColumn(_RangeColumn):
    data_type: WdgGetSet = TableIntWidget
    minimum: int = 0
    maximum: int = 10_000


@dataclass(frozen=True)
class FloatColumn(_RangeColumn):
    data_type: WdgGetSet = TableFloatWidget


# ########################  Timepoints  ################################


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
        if self.text_to_quant(a0):
            return (QValidator.State.Acceptable, a0 or "", a1)
        return (QValidator.State.Intermediate, a0 or "", a1)

    def text_to_quant(self, text: str | None) -> pint.Quantity | None:
        if not text:
            return None  # pragma: no cover

        with contextlib.suppress(pint.UndefinedUnitError, AssertionError):
            q = self.ureg.parse_expression(text)
            if self.dimensionality and (
                isinstance(q, pint.Quantity)
                and bool(q.is_compatible_with(self.dimensionality))
            ):
                return q
        # try to parse as timedelta
        with contextlib.suppress(ValueError):
            td = parse_timedelta(text)
            return self.ureg.Quantity(td.total_seconds(), "second")
        return None  # pragma: no cover


pattern = r"(?:(?P<hours>\d+):)?(?:(?P<min>\d+):)?(?P<sec>\d+)([.,](?P<ms>\d+))?"


def parse_timedelta(time_str: str) -> timedelta:
    match = re.match(pattern, time_str)

    if not match:  # pragma: no cover
        raise ValueError(f"Invalid time interval format: {time_str}")

    hours = int(match["hours"]) if match["hours"] else 0
    minutes = int(match["min"]) if match["min"] else 0
    seconds = int(match["sec"])
    ms = int(match["ms"]) if match["ms"] else 0
    return timedelta(hours=hours, minutes=minutes, seconds=seconds, microseconds=ms)


class QQuantityLineEdit(QLineEdit):
    textModified = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._validator = QQuantityValidator(parent=self)
        self.setValidator(self._validator)
        self._last_valid: str = self.text()
        self.editingFinished.connect(self._on_editing_finished)
        self.returnPressed.connect(self.clearFocus)

    def setDimensionality(self, dimensionality: str | None) -> None:
        self._validator.dimensionality = dimensionality

    def setUreg(self, ureg: pint.UnitRegistry) -> None:
        if not isinstance(ureg, pint.UnitRegistry):  # pragma: no cover
            raise TypeError(f"ureg must be a pint.UnitRegistry, not {type(ureg)}")
        self._validator.ureg = ureg

    def focusInEvent(self, event: QFocusEvent | None) -> None:
        if event and event.reason() != Qt.FocusReason.PopupFocusReason:
            self._before = self.text()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent | None) -> None:
        # When the widget loses focus, check if the text is valid
        self._on_editing_finished()
        if (
            event
            and event.reason() != Qt.FocusReason.PopupFocusReason
            and self._before != self.text()
        ):
            self.textModified.emit(self._before, self.text())
        super().focusOutEvent(event)

    def setText(self, value: str | None) -> None:
        if (valid_q := self._validator.text_to_quant(value)) is None:
            raise ValueError(f"Invalid value: {value!r}")  # pragma: no cover
        text = f"{valid_q.to_compact():~P}"  # short pretty format
        super().setText(text)
        self._last_valid = text

    def _on_editing_finished(self) -> None:
        # When the editing is finished, check if the final text is valid
        final_text = self.text()
        if valid_q := self._validator.text_to_quant(final_text):
            text = f"{valid_q:~P}"  # short pretty format
            self._last_valid = text
            self.setText(text)
        else:
            self.setText(self._last_valid)

    def quantity(self) -> pint.Quantity:
        return self._validator.ureg.parse_expression(self.text())


class QTimeLineEdit(QQuantityLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDimensionality("second")
        self.setStyleSheet("QLineEdit { border: none; }")

    def value(self) -> float:
        return self.quantity().to("second").magnitude  # type: ignore

    def setValue(self, value: float) -> None:
        self.setText(str(value))


TableTimeWidget = WdgGetSet(
    QTimeLineEdit,
    QTimeLineEdit.value,
    QTimeLineEdit.setValue,
    lambda w, cb: w.textModified.connect(cb),
)


@dataclass(frozen=True)
class TimeDeltaColumn(WidgetColumn):
    data_type: WdgGetSet[QTimeLineEdit, float] = TableTimeWidget


class CheckableCombo(QWidget):
    currentTextChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._combo = QComboBox()
        self._combo.currentTextChanged.connect(self.currentTextChanged)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.addWidget(self._checkbox)
        layout.addWidget(self._combo)

    def currentText(self) -> str:
        return self._combo.currentText()  # type: ignore

    def setCurrentText(self, value: str) -> None:
        self._combo.setCurrentText(value)

    def addItems(self, items: Iterable[str]) -> None:
        self._combo.addItems(items)

    def clear(self) -> None:
        self._combo.clear()

    def isChecked(self) -> bool:
        return self._checkbox.isChecked()  # type: ignore

    def setCheckState(self, state: Qt.CheckState) -> bool:
        return self._checkbox.setCheckState(state)  # type: ignore


ChoiceWidget = WdgGetSet(
    CheckableCombo,
    CheckableCombo.currentText,
    CheckableCombo.setCurrentText,
    lambda w, cb: w.currentTextChanged.connect(cb),
)


@dataclass(frozen=True)
class ChoiceColumn(WidgetColumn):
    data_type: WdgGetSet[CheckableCombo, str] = ChoiceWidget
    allowed_values: tuple[str, ...] | None = None

    def _init_widget(self) -> CheckableCombo:
        wdg = self.data_type.widget()
        if self.allowed_values:
            wdg.addItems(self.allowed_values)
        else:
            wdg.clear()
        return wdg

    def isChecked(self, table: QTableWidget, row: int, col: int) -> bool:
        wdg = cast("CheckableCombo", table.cellWidget(row, col))
        return wdg.isChecked() if wdg else False

    def setCheckState(
        self, table: QTableWidget, row: int, col: int, state: Qt.CheckState
    ) -> None:
        wdg = cast("CheckableCombo", table.cellWidget(row, col))
        wdg.setCheckState(state)
