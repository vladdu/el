"""Circuit model: parts (elements and nodes) of a loaded wiring diagram.

Each element type is a subclass of `Element` declaring its terminal names and
how to build itself from a `wire` declaration such as `(r1 370000)`. The
`ELEMENT_TYPES` registry maps the `wire` clause keyword (e.g. `RESISTOR`) to
the class; the loader uses it, so a new element type only needs a class and a
registry entry.
"""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class Terminal:
    """One terminal of one element, written `(#1 r1)` or `(b q1)` in `connect`."""

    element: str
    name: str

    def __str__(self) -> str:
        return f"({self.name} {self.element})"


@dataclass
class Element:
    name: str
    TERMINALS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def declare(cls, name: str, value: float) -> Element:
        """Build from a `wire` declaration `(name value)`."""
        raise NotImplementedError

    def terminals(self) -> list[Terminal]:
        return [Terminal(self.name, t) for t in self.TERMINALS]


@dataclass
class Resistor(Element):
    resistance: float = 0.0
    TERMINALS: ClassVar[tuple[str, ...]] = ("#1", "#2")

    @classmethod
    def declare(cls, name: str, value: float) -> Resistor:
        return cls(name, resistance=float(value))


ELEMENT_TYPES: dict[str, type[Element]] = {
    "RESISTOR": Resistor,
}


@dataclass
class Node:
    """A set of connected terminals. `voltage` is set only for fixed nodes."""

    name: str
    voltage: float | None = None
    terminals: list[Terminal] = field(default_factory=list)


@dataclass
class Circuit:
    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
