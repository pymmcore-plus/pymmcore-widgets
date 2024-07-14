from typing import DefaultDict, cast

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import QEvent
from qtpy.QtCore import QPoint, QRect, QSize, Qt
from qtpy.QtGui import QFont, QMouseEvent, QPainter
from qtpy.QtWidgets import (
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from pymmcore_widgets import PropertyWidget


class ClickableHeaderView(QHeaderView):
    # use `headerDataChanged` to detect changes in the header text

    def __init__(
        self, orientation: Qt.Orientation, parent: QWidget | None = None
    ) -> None:
        super().__init__(orientation, parent)
        self._is_editable: bool = True

        # stores the mouse position on hover
        self._mouse_pos = QPoint(-1, -1)
        # stores the mouse position on press
        self._press_pos = QPoint(-1, -1)
        # stores the section currently being edited
        self._sectionedit: int = 0
        # whether the last column/row is reserved for adding a new column/row
        self._last_section_adds = True

        self._show_x: bool = True
        self._x_on_right: bool = True

        # line edit for editing header
        self._line_edit = QLineEdit(parent=self.viewport())
        self._line_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._line_edit.setHidden(True)
        self._line_edit.editingFinished.connect(self._on_header_edited)

        # Connects to double click
        self.sectionDoubleClicked.connect(self._on_header_double_clicked)

    def _is_last_section(self, logicalIndex: int) -> bool:
        if model := self.model():
            if self.orientation() == Qt.Orientation.Horizontal:
                return logicalIndex == model.columnCount() - 1
            return logicalIndex == model.rowCount() - 1
        return False

    def _on_header_double_clicked(self, logicalIndex: int) -> None:
        # This block sets up the geometry for the line edit
        if not self._is_editable:
            return

        if self._last_section_adds and self._is_last_section(logicalIndex):
            return

        rect = self.geometry()
        if self.orientation() == Qt.Orientation.Horizontal:
            rect.setWidth(self.sectionSize(logicalIndex))
            rect.moveLeft(self.sectionViewportPosition(logicalIndex))
        else:
            rect.setHeight(self.sectionSize(logicalIndex))
            rect.moveTop(self.sectionViewportPosition(logicalIndex))

        if self._show_x and self._is_mouse_on(self._edge_rect(rect)):
            # double click on the right edge of the header does nothing
            # there will be an X button there to remove the column
            return

        self._line_edit.setGeometry(rect)
        self._line_edit.setHidden(False)
        self._line_edit.setFocus()
        if m := self.model():
            if txt := m.headerData(logicalIndex, self.orientation()):
                self._line_edit.setText(txt)
        self._sectionedit = logicalIndex

    def _on_header_edited(self) -> None:
        if (new_text := self._line_edit.text()) and (model := self.model()):
            model.setHeaderData(self._sectionedit, self.orientation(), new_text)
        self._line_edit.setHidden(True)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None:
            self._mouse_pos = event.pos()
            self.resizeEvent(None)  # force repaint
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None:
            self._press_pos = event.pos()
        return super().mousePressEvent(event)

    def _add_section(self) -> None:
        if model := self.model():
            if self.orientation() == Qt.Orientation.Horizontal:
                model.insertColumn(model.columnCount())
            else:
                model.insertRow(model.rowCount())
            self.resizeEvent(None)

    def _remove_section(self, logicalIndex: int) -> None:
        if model := self.model():
            if self.orientation() == Qt.Orientation.Horizontal:
                model.removeColumn(logicalIndex)
            else:
                model.removeRow(logicalIndex)
            self.resizeEvent(None)

    def mouseReleaseEvent(self, e: QMouseEvent | None) -> None:
        if e and e.pos() == self._press_pos and (model := self.model()):
            # click event

            # check if the click was in the last column
            # and if the last column is reserved for adding new columns
            # then add a new column
            logicalIndex = self.logicalIndexAt(e.pos())
            if self._is_last_section(logicalIndex):
                self._add_section()
                return

            # if the click was on the right edge of the header
            # and if _show_x is True, then remove the column
            if self._show_x:
                rect = self.geometry()
                rect.setWidth(self.sectionSize(logicalIndex))
                rect.moveLeft(self.sectionViewportPosition(logicalIndex))
                if self._is_mouse_on(self._edge_rect(rect)):
                    self._remove_section(logicalIndex)
                    return

        return super().mouseReleaseEvent(e)

    def leaveEvent(self, event: QEvent | None) -> None:
        self._mouse_pos = QPoint(-1, -1)
        self.resizeEvent(None)  # force repaint
        return super().leaveEvent(event)

    def paintSection(
        self, painter: QPainter | None, rect: QRect, logicalIndex: int
    ) -> None:
        if not painter:
            return

        pen = painter.pen()
        is_hovering = self._is_mouse_on(rect)
        big_font = QFont("Arial", 20)
        big_font.setBold(True)

        # Draw a plus sign on the last column, instead of the usual header text
        if (
            self._last_section_adds
            and (model := self.model())
            and logicalIndex == model.columnCount() - 1
        ):
            painter.setFont(big_font)
            pen.setColor(
                Qt.GlobalColor.green if is_hovering else Qt.GlobalColor.darkGreen
            )
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "+")
            return

        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        if self._show_x:
            # Draw a cross on the right side of the header
            # only if we're currently hovering over the header
            edge_rect = self._edge_rect(rect)
            if edge_rect.contains(self._mouse_pos):
                pen.setColor(Qt.GlobalColor.red)
            elif is_hovering:
                pen.setColor(Qt.GlobalColor.gray)
            else:
                pen.setColor(Qt.GlobalColor.lightGray)
            painter.setFont(big_font)
            painter.setPen(pen)
            painter.drawText(edge_rect, Qt.AlignmentFlag.AlignCenter, "\u00d7")

    def _is_mouse_on(self, rect: QRect) -> bool:
        return rect.contains(self._mouse_pos)

    def _edge_rect(self, rect: QRect) -> QRect:
        if self._x_on_right:
            return rect.adjusted(rect.width() - 40, 0, 0, 0)
        return rect.adjusted(0, 0, 40 - rect.width(), 0)


class ConfigPresetTable(QTableWidget):
    def __init__(
        self, parent: QWidget | None = None, core: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._core = core or CMMCorePlus.instance()
        self.setHorizontalHeader(ClickableHeaderView(Qt.Orientation.Horizontal, self))
        vh = ClickableHeaderView(Qt.Orientation.Vertical, self)
        vh._show_x = False
        vh._is_editable = False
        self.setVerticalHeader(vh)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.Stretch)
        if model := self.model():
            model.columnsInserted.connect(self._on_columns_changed)
            model.columnsRemoved.connect(self._on_columns_changed)

    def _on_columns_changed(self) -> None:
        ncols = self.columnCount()
        self.setColumnWidth(ncols - 1, 40)
        self.horizontalHeader().setSectionResizeMode(
            ncols - 1, QHeaderView.ResizeMode.Fixed
        )

    def _on_rows_changed(self) -> None:
        nrows = self.rowCount()
        self.verticalHeader().setSectionResizeMode(
            nrows - 1, QHeaderView.ResizeMode.Fixed
        )

    def sizeHint(self) -> QSize:
        return QSize(1000, 200)

    def loadGroup(self, group: str) -> None:
        self._rebuild_table(group)

    def _rebuild_table(self, group: str) -> None:
        # Get all presets and their properties
        # Mapping {preset -> {(dev, prop) -> val}}
        preset2props: DefaultDict[str, dict[tuple[str, str], str]] = DefaultDict(dict)
        for preset in self._core.getAvailableConfigs(group):
            for dev, prop, _val in self._core.getConfigData(group, preset):
                preset2props[preset][(dev, prop)] = _val

        all_props = set.union(*[set(props.keys()) for props in preset2props.values()])
        ncols = len(preset2props) + 1
        self.setColumnCount(ncols)
        self.setRowCount(len(all_props) + 1)

        # store which device/property is in which row
        ROWS: dict[tuple[str, str], int] = {}

        for row, (dev, prop) in enumerate(sorted(all_props)):
            ROWS[(dev, prop)] = row
            name = "Active" if dev == "Core" else dev
            self.setVerticalHeaderItem(row, QTableWidgetItem(f"{name}-{prop}"))

        for col, (preset, props) in enumerate(preset2props.items()):
            item = QTableWidgetItem(preset)
            item.setFlags(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled)
            self.setHorizontalHeaderItem(col, item)
            for (dev, prop), val in props.items():
                wdg = PropertyWidget(dev, prop, mmcore=self._core, connect_core=False)
                wdg._preset = preset
                wdg.setValue(val)
                wdg.valueChanged.connect(self._on_value_changed)
                self.setCellWidget(ROWS[(dev, prop)], col, wdg)

    def _on_value_changed(self, val) -> None:
        wdg = cast("PropertyWidget", self.sender())
        print("preset", wdg._preset, "changed", wdg._dp, "to", val)
