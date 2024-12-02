"""Unit tests for all data models."""

import pytest

from igelfs import models
from igelfs.models.base import BaseDataModel

data_models = filter(
    lambda cls: issubclass(cls, BaseDataModel), map(models.__dict__.get, models.__all__)
)


@pytest.mark.parametrize("model", data_models)
def test_models_new(model: BaseDataModel) -> None:
    """Test new method of model."""
    instance = model.new()
    assert isinstance(instance, model)
    assert instance.get_actual_size() == model.get_model_size()
    assert model.from_bytes(instance.to_bytes()) == instance
