from __future__ import annotations

from qtpy.QtWidgets import QMessageBox, QWidget


def find_circle_center(
    point1: tuple[float, float],
    point2: tuple[float, float],
    point3: tuple[float, float],
) -> tuple[float, float]:
    """
    Calculate the center of a circle passing through three given points.

    The function uses the formula for the circumcenter of a triangle to find
    the center of the circle that passes through the given points.
    """
    x1, y1 = point1
    x2, y2 = point2
    x3, y3 = point3

    # Calculate determinant D
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    # Calculate x and y coordinates of the circle's center
    x = (
        ((x1**2 + y1**2) * (y2 - y3))
        + ((x2**2 + y2**2) * (y3 - y1))
        + ((x3**2 + y3**2) * (y1 - y2))
    ) / D
    y = (
        ((x1**2 + y1**2) * (x3 - x2))
        + ((x2**2 + y2**2) * (x1 - x3))
        + ((x3**2 + y3**2) * (x2 - x1))
    ) / D

    return x, y


def find_rectangle_center(*args: tuple[float, ...]) -> tuple[float, float]:
    """
    Find the center of a rectangle/square well.

    ...given two opposite verices coordinates or 4 points on the edges.
    """
    x_list, y_list = list(zip(*args))

    if len(args) == 4:
        # get corner x and y coordinates
        x_list = (max(x_list), min(x_list))
        y_list = (max(y_list), min(y_list))

    # get center coordinates
    x = sum(x_list) / 2
    y = sum(y_list) / 2
    return x, y


def show_critical_message(parent: QWidget, title: str, message: str) -> None:
    """Show a critical message dialog."""
    QMessageBox.critical(parent, title, message, QMessageBox.StandardButton.Ok)
