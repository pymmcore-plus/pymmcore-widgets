import sys
from itertools import cycle

import numpy as np
from OpenGL.GL import *  # noqa
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication, QMainWindow, QOpenGLWidget

shape = (1024, 1024)
images = cycle((np.random.rand(100, *shape, 3) * 255).astype(np.uint8))


class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.image_data = next(images)

    def initializeGL(self) -> None:
        glClearColor(0, 0, 0, 1)
        glEnable(GL_TEXTURE_2D)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        # Set unpack alignment to 1 (important for images with width not multiple of 4)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGB,
            *shape,
            0,
            GL_RGB,
            GL_UNSIGNED_BYTE,
            self.image_data,
        )

        # Calculate aspect ratio of the window
        width = self.width()
        height = self.height()
        aspect_ratio = width / height

        # Adjust vertices to maintain 1:1 aspect ratio in the center of the viewport
        if aspect_ratio > 1:
            # Wider than tall: limit width to match height
            scale = height / width
            x0, x1 = -scale, scale
            y0, y1 = -1, 1
        else:
            # Taller than wide: limit height to match width
            scale = width / height
            x0, x1 = -1, 1
            y0, y1 = -scale, scale

        glBegin(GL_QUADS)
        glTexCoord2f(0, 0)
        glVertex2f(x0, y0)
        glTexCoord2f(1, 0)
        glVertex2f(x1, y0)
        glTexCoord2f(1, 1)
        glVertex2f(x1, y1)
        glTexCoord2f(0, 1)
        glVertex2f(x0, y1)
        glEnd()

    def update_image(self, new_image: np.ndarray) -> None:
        self.image_data = new_image
        self.update()  # Request a repaint


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.gl_widget = GLWidget(self)
        self.setCentralWidget(self.gl_widget)
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(1)  # Update image every 100 ms

    def on_timer(self) -> None:
        # Generate a new random image
        new_image = (next(images)).astype(np.uint8)
        self.gl_widget.update_image(new_image)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
