from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from useq import RelativePosition


def nearest_neighbor(
    points: list[RelativePosition], top_x: float, top_y: float
) -> list[RelativePosition]:
    """Find the nearest neighbor path for a list of points.

    The starting point is the closest to (top_x, top_y).
    """
    first_point: RelativePosition | None = _top_left(points, top_x, top_y)

    if first_point is None:
        return []

    n = len(points)
    visited: dict[int, bool] = {i: False for i in range(n)}
    path_indices: list[int] = [points.index(first_point)]
    visited[path_indices[0]] = True

    for _ in range(n - 1):
        current_point = path_indices[-1]
        nearest_point = None
        min_distance = float("inf")

        for i in range(n):
            if not visited[i]:
                distance = _calculate_distance(points[current_point], points[i])
                if distance < min_distance:
                    min_distance = distance
                    nearest_point = i

        if nearest_point is not None:
            path_indices.append(nearest_point)
            visited[nearest_point] = True

    return [points[i] for i in path_indices]


def _calculate_distance(point1: RelativePosition, point2: RelativePosition) -> float:
    """Calculate the Euclidean distance between two points."""
    return math.sqrt((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2)


def _top_left(
    points: list[RelativePosition], top_x: float, top_y: float
) -> RelativePosition:
    """Find the top left point in respect to (top_x, top_y)."""
    return sorted(
        points,
        key=lambda coord: math.sqrt(
            ((coord.x - top_x) ** 2) + ((coord.y - top_y) ** 2)
        ),
    )[0]
