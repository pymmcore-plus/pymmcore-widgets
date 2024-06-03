from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

# same as in useq FrozenModel
_T = TypeVar("_T", bound="FrozenModel")


class FrozenModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", frozen=True)

    """A frozen Pydantic model."""

    def replace(self: _T, **kwargs: Any) -> _T:
        """Return a new instance replacing specified kwargs with new values.

        This model is immutable, so this method is useful for creating a new
        sequence with only a few fields changed.  The uid of the new sequence will
        be different from the original.

        The difference between this and `self.copy(update={...})` is that this method
        will perform validation and casting on the new values, whereas `copy` assumes
        that all objects are valid and will not perform any validation or casting.
        """
        state = self.model_dump()
        return type(self)(**{**state, **kwargs})
