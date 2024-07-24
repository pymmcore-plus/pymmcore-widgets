from __future__ import annotations

from typing import Iterable

import numpy as np


def find_circle_center(
    coords: Iterable[tuple[float, float]],
) -> tuple[float, float, float]:
    """Calculate the center of a circle passing through three or more points.

    This function uses the least squares method to find the center of a circle
    that passes through the given coordinates. The input coordinates should be
    an iterable of 2D points (x, y).

    Returns
    -------
    tuple : (x, y, radius)
        The center of the circle and the radius of the circle.
    """
    points = np.array(coords)
    if points.ndim != 2 or points.shape[1] != 2:  # pragma: no cover
        raise ValueError("Invalid input coordinates")
    if len(points) < 3:  # pragma: no cover
        raise ValueError("At least 3 points are required")

    # Prepare the matrices for least squares
    A = np.hstack((points, np.ones((points.shape[0], 1))))
    B = np.sum(points**2, axis=1).reshape(-1, 1)

    # Solve the least squares problem
    params, _residuals, rank, s = np.linalg.lstsq(A, B, rcond=None)

    if rank < 3:  # pragma: no cover
        raise ValueError("The points are collinear or nearly collinear")

    # Extract the circle parameters
    x = params[0][0] / 2
    y = params[1][0] / 2

    # radius, if needed
    r_squared = params[2][0] + x**2 + y**2
    radius = np.sqrt(r_squared)

    return (x, y, radius)


def find_rectangle_center(
    coords: Iterable[tuple[float, float]],
) -> tuple[float, float, float, float]:
    """Find the center of a rectangle/square well from 2 or more points.

    Returns
    -------
    tuple : (x, y, width, height)
        The center of the rectangle, width, and height.
    """
    points = np.array(coords)

    if points.ndim != 2 or points.shape[1] != 2:  # pragma: no cover
        raise ValueError("Invalid input coordinates")
    if len(points) < 2:  # pragma: no cover
        raise ValueError("At least 2 points are required")

    # Find the min and max x and y values
    x_min, y_min = points.min(axis=0)
    x_max, y_max = points.max(axis=0)

    # Calculate the center of the rectangle
    x = (x_min + x_max) / 2
    y = (y_min + y_max) / 2

    # Calculate the width and height of the rectangle
    width = x_max - x_min
    height = y_max - y_min
    return (x, y, width, height)
