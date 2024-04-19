import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.experimental import StackViewer

app = QApplication([])

# _canvas = scene.SceneCanvas(size=(512, 512),keys="interactive")
# _canvas._send_hover_events = True
# camera = scene.PanZoomCamera(aspect=1)
# view = _canvas.central_widget.add_view(camera=camera)
# _canvas.show()

# sys.exit()
sequence = useq.MDASequence(
    channels=[{"config": "DAPI", "exposure": 10}, {"config": "FITC", "exposure": 10}],
    time_plan={"interval": 0.2, "loops": 3},
    grid_plan={"rows": 2, "columns": 2, "fov_height": 512, "fov_width": 512},
    axis_order="tpcz",
)

mmcore = CMMCorePlus.instance()

canvas = StackViewer(mmcore=mmcore)
canvas.show()
# with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
# mmcore.mda.run(sequence)
# # qapp.processEvents()
# # qtbot.wait(1000)

# # canvas.view_rect = ((0, 0), (512, 512))
# canvas.resize(700, 700)
# canvas._collapse_view()
# canvas._canvas.update()

# # outside canvas
# event = SceneMouseEvent(MouseEvent("mouse_move"), None)
# event._pos = [-10, 100]
# canvas.on_mouse_move(event)
# assert canvas.info_bar.text()[-1] == "]"

# # outside image
# event._pos = [1000, 100]
# canvas.on_mouse_move(event)
# assert canvas.info_bar.text()[-1] == "]"

# event._pos = [100, 100]
# # canvas.on_mouse_move(event)
# qtbot.wait(100)
# qtbot.mouseMove(canvas, canvas.rect().center() - QtCore.QPoint(10, 10))
# qtbot.wait(100)
# qtbot.mouseMove(canvas, canvas.rect().center())
# qapp.processEvents()
# qtbot.wait(100)
# canvas._canvas.app.process_events()
# # There should be a number there as this is on the image
# assert canvas.info_bar.text()[-1] != "]"

# canvas.sliders["t"].setValue(1)
# canvas.sliders["t"].lock_btn.setChecked(True)
# event = MDAEvent(index={"t": 0, "c": 0, "g": 0})
# canvas.frameReady(event)
# assert canvas.sliders["t"].value() == 1

# canvas.on_clim_timer()
# color_selected = 2
# canvas.channel_row.boxes[0].color_choice.setCurrentIndex(color_selected)
# assert (
#     canvas.images[tuple({"c": 0, "g": 0}.items())].cmap.colors[-1].RGB
#     == try_cast_colormap(CMAPS[color_selected]).to_vispy().colors[-1].RGB
# ).all

# canvas.channel_row.boxes[0].autoscale_chbx.setChecked(False)
# canvas.channel_row.boxes[0].slider.setValue((0, 255))
# canvas.channel_row.boxes[0].show_channel.setChecked(False)
# # should be current channel
# canvas.current_channel = 1
# canvas.channel_row.boxes[1].show_channel.setChecked(False)
# canvas._canvas.update()
# # Should have been set as all channels are deselected now
# assert canvas.channel_row.boxes[0].show_channel.isChecked()
