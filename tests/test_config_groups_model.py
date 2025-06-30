import pytest
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup

from pymmcore_widgets.config_presets._qmodel._config_model import QConfigGroupsModel


@pytest.fixture
def model() -> QConfigGroupsModel:
    """Fixture to create a QConfigGroupsModel instance."""
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QConfigGroupsModel.create_from_core(core)
    return model


def test_model_initialization() -> None:
    """Test the initialization of the QConfigGroupsModel."""
    # not using the fixture here, as we want to test the model creation directly
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    python_info = ConfigGroup.all_config_groups(core)
    model = QConfigGroupsModel(python_info.values())

    assert isinstance(model, QConfigGroupsModel)
    assert model.rowCount() > 0
    assert model.columnCount() == 3

    # original data is recovered intact
    assert model.python_object() == python_info

    # we can also index deeper
    for row, value in enumerate(python_info.values()):
        assert model.python_object(model.index(row)) == value

    assert not model.parent(model.index(3)).isValid()
