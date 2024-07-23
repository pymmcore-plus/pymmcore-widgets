from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from useq import WellPlate

    from pymmcore_widgets.hcs._graphics_items import Well


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


def get_plate_rotation_angle(
    xy_well_1: tuple[float, float], xy_well_2: tuple[float, float]
) -> float:
    """Get the rotation angle to align the plate."""
    x1, y1 = xy_well_1
    x2, y2 = xy_well_2

    try:
        m = (y2 - y1) / (x2 - x1)  # slope from y = mx + q
        plate_angle_rad = np.arctan(m)
        return float(np.rad2deg(plate_angle_rad))
    except ZeroDivisionError:
        return 0.0


def get_random_circle_edge_point(
    xc: float, yc: float, radius: float
) -> tuple[float, float]:
    """Get random edge point of a circle.

    ...with center (xc, yc) and radius `radius`.
    """
    # random angle
    angle = 2 * math.pi * np.random.random()
    # coordinates of the edge point using trigonometry
    x = radius * math.cos(angle) + xc
    y = radius * math.sin(angle) + yc

    return x, y


def get_random_rectangle_edge_point(
    xc: float, yc: float, well_size_x: float, well_size_y: float
) -> tuple[float, float]:
    """Get random edge point of a rectangle.

    ...with center (xc, yc) and size (well_size_x, well_size_y).
    """
    x_left, y_top = xc - (well_size_x / 2), yc + (well_size_y / 2)
    x_right, y_bottom = xc + (well_size_x / 2), yc - (well_size_y / 2)

    # random 4 edge points
    edge_points = [
        (x_left, np.random.uniform(y_top, y_bottom)),  # left
        (np.random.uniform(x_left, x_right), y_top),  # top
        (x_right, np.random.uniform(y_top, y_bottom)),  # right
        (np.random.uniform(x_left, x_right), y_bottom),  # bottom
    ]
    return edge_points[np.random.randint(0, 4)]


def get_well_center(
    plate: WellPlate, well: Well, a1_center_x: float, a1_center_y: float
) -> tuple[float, float]:
    """Calculate the x, y stage coordinates of a well."""
    a1_x, a1_y = (a1_center_x, a1_center_y)
    well_spacing_x, well_spacing_y = plate.well_spacing
    spacing_x = well_spacing_x * 1000  # µm
    spacing_y = well_spacing_y * 1000  # µm

    if well.name == "A1":
        x, y = (a1_x, a1_y)
    else:
        x = a1_x + (spacing_x * well.column)
        y = a1_y - (spacing_y * well.row)
    return x, y


def apply_rotation_matrix(
    rotation_matrix: np.ndarray,
    a1_center_x: float,
    a1_center_y: float,
    new_x: float,
    new_y: float,
) -> tuple[float, float]:
    """Apply rotation matrix to x, y coordinates."""
    center = np.array([[a1_center_x], [a1_center_y]])
    coords = [[new_x], [new_y]]
    transformed = np.linalg.inv(rotation_matrix).dot(coords - center) + center
    x_rotated, y_rotated = transformed
    return x_rotated[0], y_rotated[0]
