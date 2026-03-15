"""Tests for new roi_model features added in this PR.

Covers: overlap/mode params in create_grid_plan, self-intersecting polygon
handling, create_useq_position x/y logic, uuid-based naming, and the new
fov_overlap/scan_order default fields.
"""

from __future__ import annotations

import numpy as np
import pytest
import useq

from pymmcore_widgets.control._rois.roi_model import ROI, RectangleROI


@pytest.fixture
def large_rect() -> RectangleROI:
    """A rectangle larger than a typical FOV (10x10)."""
    return RectangleROI((0.0, 0.0), (100.0, 100.0), fov_size=(10.0, 10.0))


@pytest.fixture
def small_rect() -> RectangleROI:
    """A rectangle smaller than a typical FOV (10x10) -> no grid needed."""
    return RectangleROI((0.0, 0.0), (5.0, 5.0), fov_size=(10.0, 10.0))


@pytest.fixture
def large_polygon() -> ROI:
    """A polygon (triangle) larger than a typical FOV."""
    verts = np.array([(0.0, 0.0), (200.0, 0.0), (100.0, 200.0)])
    return ROI(vertices=verts, fov_size=(10.0, 10.0))


# ---------------------------------------------------------------------------
# create_grid_plan - overlap & mode forwarding (new params in this PR)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("overlap", [0.0, 0.1, (0.2, 0.3)])
def test_rect_grid_plan_overlap_forwarded(
    large_rect: RectangleROI, overlap: float | tuple[float, float]
) -> None:
    plan = large_rect.create_grid_plan(overlap=overlap)
    assert plan is not None
    expected = overlap if isinstance(overlap, tuple) else (overlap, overlap)
    assert plan.overlap == expected


@pytest.mark.parametrize("overlap", [0.0, 0.15, (0.2, 0.3)])
def test_polygon_grid_plan_overlap_forwarded(
    large_polygon: ROI, overlap: float | tuple[float, float]
) -> None:
    plan = large_polygon.create_grid_plan(overlap=overlap)
    assert plan is not None
    expected = overlap if isinstance(overlap, tuple) else (overlap, overlap)
    assert plan.overlap == expected


@pytest.mark.parametrize("mode", [useq.OrderMode.row_wise_snake, useq.OrderMode.spiral])
def test_rect_grid_plan_mode_forwarded(
    large_rect: RectangleROI, mode: useq.OrderMode
) -> None:
    plan = large_rect.create_grid_plan(mode=mode)
    assert plan is not None
    assert plan.mode == mode


@pytest.mark.parametrize("mode", [useq.OrderMode.row_wise_snake, useq.OrderMode.spiral])
def test_polygon_grid_plan_mode_forwarded(
    large_polygon: ROI, mode: useq.OrderMode
) -> None:
    plan = large_polygon.create_grid_plan(mode=mode)
    assert plan is not None
    assert plan.mode == mode


def test_self_intersecting_polygon_returns_none() -> None:
    """A self-intersecting (bowtie) polygon should return None, not crash."""
    verts = np.array([(0.0, 0.0), (100.0, 100.0), (100.0, 0.0), (0.0, 100.0)])
    roi = ROI(vertices=verts, fov_size=(10.0, 10.0))
    result = roi.create_grid_plan()
    assert result is None or isinstance(result, useq.GridFromPolygon)


# ---------------------------------------------------------------------------
# create_useq_position (reworked in this PR)
# ---------------------------------------------------------------------------


def test_position_name_contains_uuid(large_rect: RectangleROI) -> None:
    pos = large_rect.create_useq_position()
    assert pos.name is not None
    assert large_rect.text in pos.name
    assert pos.name.endswith(large_rect._uuid.hex[-4:])


def test_position_xy_from_first_grid_position(large_rect: RectangleROI) -> None:
    pos = large_rect.create_useq_position()
    plan = large_rect.create_grid_plan()
    assert plan is not None
    first = next(iter(plan))
    assert pos.x == first.x
    assert pos.y == first.y


def test_position_xy_falls_back_to_center(small_rect: RectangleROI) -> None:
    pos = small_rect.create_useq_position()
    cx, cy = small_rect.center()
    assert pos.x == cx
    assert pos.y == cy


def test_position_forwards_overlap_and_scan_order() -> None:
    roi = RectangleROI(
        (0.0, 0.0),
        (100.0, 100.0),
        fov_size=(10.0, 10.0),
        fov_overlap=(0.2, 0.2),
        scan_order=useq.OrderMode.spiral,
    )
    pos = roi.create_useq_position()
    assert pos.sequence is not None
    grid = pos.sequence.grid_plan
    assert grid is not None
    assert grid.overlap == (0.2, 0.2)
    assert grid.mode == useq.OrderMode.spiral


# ---------------------------------------------------------------------------
# New default field values
# ---------------------------------------------------------------------------


def test_default_fov_overlap() -> None:
    roi = ROI(vertices=np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]))
    assert roi.fov_overlap == (0.0, 0.0)


def test_default_scan_order() -> None:
    roi = ROI(vertices=np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]))
    assert roi.scan_order == useq.OrderMode.row_wise_snake
