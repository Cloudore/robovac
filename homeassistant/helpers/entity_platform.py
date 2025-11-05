"""Entity platform helper stubs."""

from typing import Callable, Iterable, Protocol


class Entity(Protocol):
    async def async_update(self) -> None: ...


AddEntitiesCallback = Callable[[Iterable[Entity], bool], None]
