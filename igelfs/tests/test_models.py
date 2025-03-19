"""Unit tests for all data models."""

from collections.abc import Iterator

import pytest

from igelfs import models
from igelfs.models.base import BaseDataModel

data_models: Iterator[type[BaseDataModel]] = filter(
    lambda cls: issubclass(cls, BaseDataModel),  # type: ignore[arg-type]
    map(models.__dict__.get, models.__all__),
)


@pytest.mark.parametrize("model", data_models)
def test_models_new(model: type[BaseDataModel]) -> None:
    """Test new method of model."""
    instance = model.new()
    assert isinstance(instance, model)
    assert instance.get_actual_size() == model.get_model_size()
    assert model.from_bytes(instance.to_bytes()) == instance
