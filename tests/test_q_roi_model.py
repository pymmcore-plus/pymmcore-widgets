from __future__ import annotations

import numpy as np
import pytest

from pymmcore_widgets.control._rois.q_roi_model import QROIModel
from pymmcore_widgets.control._rois.roi_model import ROI


@pytest.fixture
def model() -> QROIModel:
    return QROIModel()


def _make_roi(text: str = "ROI") -> ROI:
    return ROI(vertices=np.array([(0, 0), (10, 0), (10, 10)]), text=text)


def test_get_roi_valid_index(model: QROIModel) -> None:
    roi = _make_roi("A")
    model.addROI(roi)
    assert model.getRoi(0) is roi


def test_get_roi_multiple(model: QROIModel) -> None:
    rois = [_make_roi(c) for c in "ABC"]
    for r in rois:
        model.addROI(r)
    for i, r in enumerate(rois):
        assert model.getRoi(i) is r


@pytest.mark.parametrize("index", [-1, 0, 5])
def test_get_roi_out_of_bounds(model: QROIModel, index: int) -> None:
    with pytest.raises(IndexError, match="Index out of bounds"):
        model.getRoi(index)


def test_get_roi_after_remove(model: QROIModel) -> None:
    roi_a = _make_roi("A")
    roi_b = _make_roi("B")
    model.addROI(roi_a)
    model.addROI(roi_b)
    model.removeROI(roi_a)
    assert model.getRoi(0) is roi_b


def test_data_roi_role(model: QROIModel) -> None:
    roi = _make_roi()
    model.addROI(roi)
    idx = model.index(0)
    assert idx.data(QROIModel.ROI_ROLE) is roi
