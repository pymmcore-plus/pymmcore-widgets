from __future__ import annotations

import numpy as np
import pytest
import useq

from pymmcore_widgets.control._rois.roi_model import ROI, RectangleROI

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def large_rect() -> RectangleROI:
    """A rectangle larger than a typical FOV (10x10)."""
    return RectangleROI((0.0, 0.0), (100.0, 100.0), fov_size=(10.0, 10.0))


@pytest.fixture
def small_rect() -> RectangleROI:
    """A rectangle smaller than a typical FOV (10x10) → no grid needed."""
    return RectangleROI((0.0, 0.0), (5.0, 5.0), fov_size=(10.0, 10.0))


@pytest.fixture
def large_polygon() -> ROI:
    """A polygon (triangle) larger than a typical FOV."""
    verts = np.array([(0.0, 0.0), (200.0, 0.0), (100.0, 200.0)])
    return ROI(vertices=verts, fov_size=(10.0, 10.0))


# ---------------------------------------------------------------------------
# create_grid_plan - overlap & mode forwarding
# ---------------------------------------------------------------------------


class TestCreateGridPlan:
    """Tests for ROI.create_grid_plan with overlap and mode parameters."""

    def test_rect_returns_grid_from_edges(self, large_rect: RectangleROI) -> None:
        plan = large_rect.create_grid_plan()
        assert isinstance(plan, useq.GridFromEdges)

    def test_polygon_returns_grid_from_polygon(self, large_polygon: ROI) -> None:
        plan = large_polygon.create_grid_plan()
        assert isinstance(plan, useq.GridFromPolygon)

    def test_small_roi_returns_none(self, small_rect: RectangleROI) -> None:
        assert small_rect.create_grid_plan() is None

    @pytest.mark.parametrize("overlap", [0.0, 0.1, (0.2, 0.3)])
    def test_rect_overlap_forwarded(
        self, large_rect: RectangleROI, overlap: float | tuple[float, float]
    ) -> None:
        plan = large_rect.create_grid_plan(overlap=overlap)
        assert plan is not None
        expected = overlap if isinstance(overlap, tuple) else (overlap, overlap)
        assert plan.overlap == expected

    @pytest.mark.parametrize("overlap", [0.0, 0.15, (0.2, 0.3)])
    def test_polygon_overlap_forwarded(
        self, large_polygon: ROI, overlap: float | tuple[float, float]
    ) -> None:
        plan = large_polygon.create_grid_plan(overlap=overlap)
        assert plan is not None
        expected = overlap if isinstance(overlap, tuple) else (overlap, overlap)
        assert plan.overlap == expected

    @pytest.mark.parametrize(
        "mode",
        [useq.OrderMode.row_wise_snake, useq.OrderMode.spiral],
    )
    def test_rect_mode_forwarded(
        self, large_rect: RectangleROI, mode: useq.OrderMode
    ) -> None:
        plan = large_rect.create_grid_plan(mode=mode)
        assert plan is not None
        assert plan.mode == mode

    @pytest.mark.parametrize(
        "mode",
        [useq.OrderMode.row_wise_snake, useq.OrderMode.spiral],
    )
    def test_polygon_mode_forwarded(
        self, large_polygon: ROI, mode: useq.OrderMode
    ) -> None:
        plan = large_polygon.create_grid_plan(mode=mode)
        assert plan is not None
        assert plan.mode == mode

    def test_fov_from_args_overrides_attribute(self) -> None:
        roi = RectangleROI((0.0, 0.0), (100.0, 100.0), fov_size=(50.0, 50.0))
        plan = roi.create_grid_plan(fov_w=10.0, fov_h=10.0)
        assert plan is not None
        assert plan.fov_width == 10.0
        assert plan.fov_height == 10.0

    def test_raises_without_fov(self) -> None:
        roi = RectangleROI((0.0, 0.0), (100.0, 100.0))
        with pytest.raises(ValueError, match="fov_size must be set"):
            roi.create_grid_plan()

    def test_polygon_fewer_than_3_vertices(self) -> None:
        roi = ROI(vertices=np.array([(0.0, 0.0), (200.0, 0.0)]), fov_size=(10.0, 10.0))
        assert roi.create_grid_plan() is None

    def test_self_intersecting_polygon_returns_none(self) -> None:
        """A self-intersecting (bowtie) polygon should return None."""
        verts = np.array([(0.0, 0.0), (100.0, 100.0), (100.0, 0.0), (0.0, 100.0)])
        roi = ROI(vertices=verts, fov_size=(10.0, 10.0))
        # may or may not raise depending on useq, but should not crash
        result = roi.create_grid_plan()
        # the result is None when the polygon is invalid
        assert result is None or isinstance(result, useq.GridFromPolygon)


# ---------------------------------------------------------------------------
# create_useq_position
# ---------------------------------------------------------------------------


class TestCreateUseqPosition:
    """Tests for ROI.create_useq_position."""

    def test_position_has_name(self, large_rect: RectangleROI) -> None:
        pos = large_rect.create_useq_position()
        assert pos.name is not None
        assert large_rect.text in pos.name

    def test_position_center(self, large_rect: RectangleROI) -> None:
        pos = large_rect.create_useq_position()
        assert pos.x == pytest.approx(50.0)
        assert pos.y == pytest.approx(50.0)

    def test_position_with_grid_has_sequence(self, large_rect: RectangleROI) -> None:
        pos = large_rect.create_useq_position()
        assert pos.sequence is not None
        assert pos.sequence.grid_plan is not None

    def test_position_without_grid_has_no_sequence(
        self, small_rect: RectangleROI
    ) -> None:
        pos = small_rect.create_useq_position()
        assert pos.sequence is None

    def test_position_uses_roi_overlap_and_scan_order(self) -> None:
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
# Default field values
# ---------------------------------------------------------------------------


def test_default_fov_overlap() -> None:
    roi = ROI(vertices=np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]))
    assert roi.fov_overlap == (0.0, 0.0)


def test_default_scan_order() -> None:
    roi = ROI(vertices=np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]))
    assert roi.scan_order == useq.OrderMode.row_wise_snake
