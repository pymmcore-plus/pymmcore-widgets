from typing import cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimerEvent
from qtpy.QtWidgets import (
    QAction,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from ._stage_viewer import StageViewer

red = "#C33"
green = "#3A3"
gray = "#666"
RESET = "Auto Reset View"
SNAP = "Auto Snap on Double Click"
FLIP_H = "Flip Images Horizontally"
FLIP_V = "Flip Images Vertically"
POLL_STAGE = "Poll Stage Position"


class StageExplorer(QWidget):
    """A stage positions explorer widget.

    It is a top-level widget that contains a
    [`StageViewer`][pymmcore_widgets.control.StageViewer].

    This widget provides a visual representation of the stage positions. The user can
    interact with the stage positions by panning and zooming the view. The user can also
    move the stage to a specific position (and optiionally snap an image) by
    double-clicking on the view.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmc : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].

    Properties
    ----------
    auto_reset_view : bool
        A boolean property that controls whether to automatically reset the view when an
        image is added to the scene.
    snap_on_double_click : bool
        A boolean property that controls whether to snap an image when the user
        double-clicks on the view.
    flip_horizontal : bool
        A boolean property that controls whether to flip images horizontally.
    flip_vertical : bool
        A boolean property that controls whether to flip images vertically.
    poll_stage_position : bool
        A boolean property that controls whether to poll the stage position.
        If True, the widget will poll the stage position every 100 ms and display
        the current X and Y position in the status bar. If False, the widget will
        stop polling the stage position.
    """

    def __init__(self, parent: QWidget | None = None, mmc: CMMCorePlus | None = None):
        super().__init__(parent)
        self.setWindowTitle("Stage Explorer")

        self._mmc = mmc or CMMCorePlus.instance()

        self._stage_viewer = StageViewer(mmc=self._mmc)

        # timer for polling stage position
        self._timer_id: int | None = None

        # properties
        self._poll_stage_position: bool = False
        self._timer_id = None

        # toolbar ---------------------------------------------------------------------
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.layout().setContentsMargins(0, 0, 10, 0)
        # reset view action
        self._act_reset = QAction(
            icon(MDI6.fullscreen, color=green), "Reset View", self
        )
        self._act_reset.triggered.connect(self._stage_viewer.reset_view)
        toolbar.addAction(self._act_reset)
        # clear action
        self._act_clear = QAction(icon(MDI6.close, color=red), "Clear View", self)
        self._act_clear.triggered.connect(self._stage_viewer.clear_scene)
        toolbar.addAction(self._act_clear)
        # settings button and context menu for settings
        self._settings_btn = QToolButton()
        self._settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._settings_btn.setToolTip("Settings Menu")
        self._settings_btn.setIcon(icon(MDI6.cog_outline, color=gray))
        # context menu
        menu = QMenu(self)
        self._settings_btn.setMenu(menu)
        # create actions for checkboxes
        self._auto_reset_act = QAction(RESET, self, checkable=True)
        self._auto_reset_act.setChecked(self._stage_viewer.auto_reset_view)
        self._auto_snap_act = QAction(SNAP, self, checkable=True)
        self._auto_snap_act.setChecked(self._stage_viewer.snap_on_double_click)
        self._flip_h_act = QAction(FLIP_H, self, checkable=True)
        self._flip_h_act.setChecked(self._stage_viewer.flip_h)
        self._flip_v_act = QAction(FLIP_V, self, checkable=True)
        self._flip_v_act.setChecked(self._stage_viewer.flip_v)
        self._poll_stage_act = QAction(POLL_STAGE, self, checkable=True)
        # add actions to the menu
        menu.addAction(self._auto_reset_act)
        menu.addAction(self._auto_snap_act)
        menu.addAction(self._flip_h_act)
        menu.addAction(self._flip_v_act)
        menu.addAction(self._poll_stage_act)
        # settings connections
        self._auto_reset_act.triggered.connect(self._on_reset_view)
        self._auto_snap_act.triggered.connect(self._on_setting_checked)
        self._flip_h_act.triggered.connect(self._on_setting_checked)
        self._flip_v_act.triggered.connect(self._on_setting_checked)
        self._poll_stage_act.triggered.connect(self._on_poll_stage)

        # stage pos label
        self._stage_pos_label = QLabel()

        toolbar.addWidget(self._settings_btn)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(spacer)
        toolbar.addWidget(self._stage_pos_label)
        # ----------------------------------------------------------------------------

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(toolbar, 0)
        main_layout.addWidget(self._stage_viewer, 1)

    # -----------------------------PUBLIC METHODS-------------------------------------

    @property
    def auto_reset_view(self) -> bool:
        """Return the auto reset view property."""
        return self._stage_viewer.auto_reset_view

    @auto_reset_view.setter
    def auto_reset_view(self, value: bool) -> None:
        """Set the auto reset view property."""
        self._stage_viewer.auto_reset_view = value
        self._auto_reset_act.setChecked(value)
        self._on_reset_view(value)

    @property
    def snap_on_double_click(self) -> bool:
        """Return the snap on double click property."""
        return self._stage_viewer.snap_on_double_click

    @snap_on_double_click.setter
    def snap_on_double_click(self, value: bool) -> None:
        """Set the snap on double click property."""
        self._stage_viewer.snap_on_double_click = value
        self._auto_snap_act.setChecked(value)

    @property
    def flip_horizontal(self) -> bool:
        """Return the flip horizontal property."""
        return self._stage_viewer.flip_h

    @flip_horizontal.setter
    def flip_horizontal(self, value: bool) -> None:
        """Set the flip horizontal property."""
        self._stage_viewer.flip_h = value
        self._flip_h_act.setChecked(value)

    @property
    def flip_vertical(self) -> bool:
        """Return the flip vertical property."""
        return self._stage_viewer.flip_v

    @flip_vertical.setter
    def flip_vertical(self, value: bool) -> None:
        """Set the flip vertical property."""
        self._stage_viewer.flip_v = value
        self._flip_v_act.setChecked(value)

    @property
    def poll_stage_position(self) -> bool:
        """Return the poll stage position property."""
        return self._poll_stage_position

    @poll_stage_position.setter
    def poll_stage_position(self, value: bool) -> None:
        """Set the poll stage position property."""
        self._poll_stage_position = value
        self._poll_stage_act.setChecked(value)
        self._on_poll_stage(value)

    # -----------------------------PRIVATE METHODS------------------------------------

    def _on_reset_view(self, checked: bool) -> None:
        """Set the auto reset view property based on the state of the action."""
        self._stage_viewer.auto_reset_view = checked
        if checked:
            self._stage_viewer.reset_view()

    def _on_setting_checked(self, checked: bool) -> None:
        """Update the stage viewer settings based on the state of the action."""
        action_map = {
            SNAP: "snap_on_double_click",
            FLIP_H: "flip_horizontal",
            FLIP_V: "flip_vertical",
        }
        sender = cast(QAction, self.sender()).text()
        if value := action_map.get(sender):
            setattr(self._stage_viewer, value, checked)

    def _on_poll_stage(self, checked: bool) -> None:
        """Set the poll stage position property based on the state of the action."""
        if checked:
            self._timer_id = self.startTimer(100)
        elif self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
            self._stage_pos_label.setText("")

    def timerEvent(self, event: QTimerEvent) -> None:
        """Poll the stage position."""
        x, y = self._mmc.getXYPosition()
        self._stage_pos_label.setText(f"X: {x:.2f} Y: {y:.2f}")
