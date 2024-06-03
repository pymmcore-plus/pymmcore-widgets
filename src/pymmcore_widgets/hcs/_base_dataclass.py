from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True)
class BaseDataclass:
    """Base class for dataclasses."""

    # using "BaseDataclass" instead of give some type errors
    def replace(self, **kwargs: Any) -> Any:
        """Return a new plate with the given attributes replaced."""
        attrs = {f.name: getattr(self, f.name) for f in fields(self)}
        attrs.update(kwargs)
        return self.__class__(**attrs)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the BaseDataclass."""
        return asdict(self)
