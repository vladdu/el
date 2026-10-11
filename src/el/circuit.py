"""Circuit model: parts (elements and nodes) of a loaded wiring diagram.

Every part owns quantities and has laws. A part type declares both in one
place: `_quantities()` makes the quantities it owns (premises filled), `ref()`
names them (including aliases), and `make_laws()` builds its laws once the
circuit's topology is known. The engine knows nothing about part types.

Each element type is a subclass of `Element` declaring its terminal names and
how to build itself from a `wire` declaration such as `(r1 370000)`. The
`ELEMENT_TYPES` registry maps the `wire` clause keyword (e.g. `RESISTOR`) to
the class; the loader uses it, so a new element type only needs a class and a
registry entry.

Terminal currents are currents *into* the terminal. A terminal's voltage is
its node's voltage quantity.

A hint such as `(vd r1 r2)` becomes a macro-element: a part with no
terminals whose laws relate quantities of the parts it is made of. A part is
woken whenever a quantity its laws read is filled (it *owns* it), so a
macro-element watches exactly the quantities its laws name, and anything
that wakes the owners of a quantity (a fill, or a retraction) wakes the
macro-elements watching it too. `HINT_TYPES` maps a hint keyword to its
class.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

from el.quantity import ACTIVE, DEFAULT, FRESH, Law, Quantity, Ref, Value


@dataclass(frozen=True)
class Terminal:
    """One terminal of one element, written `(#1 r1)` or `(b q1)` in `connect`."""

    element: str
    name: str

    def __str__(self) -> str:
        return f"({self.name} {self.element})"


@dataclass(eq=False)
class Part:
    """An element or a node. `quantities` maps `(kind, label)` to the
    quantities this part owns; `laws` is filled in by `Circuit.make_laws`."""

    name: str
    quantities: dict[tuple[str, str | None], Quantity] = field(
        init=False, repr=False, default_factory=dict
    )
    laws: list[Law] = field(init=False, repr=False, default_factory=list)

    def __post_init__(self) -> None:
        for q in self._quantities():
            self.quantities[q.kind, q.label] = q

    def _quantities(self) -> list[Quantity]:
        return []

    def ref(self, kind: str, label: str | None = None) -> Ref:
        """The quantity named `(part kind [label])`, as a signed ref.
        Raises KeyError if this part has no such quantity."""
        return Ref(self.quantities[kind, label], label)

    def make_laws(self, circuit: Circuit) -> list[Law]:
        return []


@dataclass(eq=False)
class Element(Part):
    TERMINALS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def declare(cls, name: str, value: float) -> Element:
        """Build from a `wire` declaration `(name value)`."""
        raise NotImplementedError

    def terminals(self) -> list[Terminal]:
        return [Terminal(self.name, t) for t in self.TERMINALS]


def _ohm(target: int, values: list[Value | None]) -> Value | None:
    """v1 - v2 = r * i, where i flows into #1 (and out of #2)."""
    v1, v2, r, i = values
    match target:
        case 0:
            return v2 + r * i
        case 1:
            return v1 - r * i
        case 2:
            return None if i == 0 else (v1 - v2) / i
        case 3:
            return None if r == 0 else (v1 - v2) / r
    return None


@dataclass(eq=False)
class Resistor(Element):
    """`ME` is the current into `#1`; the `#2` current is its negative, so
    the three names share one quantity."""

    resistance: float = 0.0
    TERMINALS: ClassVar[tuple[str, ...]] = ("#1", "#2")

    @classmethod
    def declare(cls, name: str, value: float) -> Resistor:
        return cls(name, resistance=float(value))

    def _quantities(self) -> list[Quantity]:
        resistance = Quantity(self.name, "RESISTANCE")
        resistance.premise(self.resistance)
        return [resistance, Quantity(self.name, "CURRENT", "ME")]

    def ref(self, kind: str, label: str | None = None) -> Ref:
        if kind == "CURRENT":
            current = self.quantities["CURRENT", "ME"]
            match label:
                case "ME" | "#1" | None:
                    return Ref(current, label)
                case "#2":
                    return Ref(current, label, -1)
        return super().ref(kind, label)

    def make_laws(self, circuit: Circuit) -> list[Law]:
        v1, v2 = (circuit.node_at(t).ref("VOLTAGE") for t in self.terminals())
        return [Law("OHM", (v1, v2, self.ref("RESISTANCE"), self.ref("CURRENT", "ME")), _ohm)]


def _be(target: int, values: list[Value | None]) -> Value | None:
    """vb - ve = vbe, in the ACTIVE region only. Never solves for the region."""
    vb, ve, vbe, region = values
    if region != ACTIVE:
        return None
    match target:
        case 0:
            return ve + vbe
        case 1:
            return vb - vbe
        case 2:
            return vb - ve
    return None


def _transistor_currents(target: int, values: list[Value | None]) -> Value | None:
    """Ib + Ie + Ic = 0: the currents into the three terminals."""
    return -sum(v for i, v in enumerate(values) if i != target)


@dataclass(eq=False)
class Transistor(Element):
    """A bipolar transistor in EL's simple model. `vbe` is signed: positive
    for NPN, negative for PNP (.6 silicon, .3 germanium).

    VBE is a Given; the base current is a Default of 0; the operating region
    is a hidden Default of ACTIVE (ADR 0001), read by BE. The three terminal
    currents are separate quantities tied by the transistor current law."""

    vbe: float = 0.0
    TERMINALS: ClassVar[tuple[str, ...]] = ("B", "E", "C")

    @classmethod
    def declare(cls, name: str, value: float) -> Transistor:
        return cls(name, vbe=float(value))

    def _quantities(self) -> list[Quantity]:
        vbe = Quantity(self.name, "VBE")
        vbe.premise(self.vbe)
        base = Quantity(self.name, "CURRENT", "B")
        base.premise(0.0, DEFAULT)
        region = Quantity(self.name, "REGION", hidden=True)
        region.premise(ACTIVE, DEFAULT)
        emitter = Quantity(self.name, "CURRENT", "E")
        collector = Quantity(self.name, "CURRENT", "C")
        return [vbe, region, base, emitter, collector]

    def make_laws(self, circuit: Circuit) -> list[Law]:
        vb, ve = (circuit.node_at(Terminal(self.name, t)).ref("VOLTAGE") for t in ("B", "E"))
        currents = tuple(self.ref("CURRENT", t) for t in ("B", "E", "C"))
        return [
            Law("BE", (vb, ve, self.ref("VBE"), self.ref("REGION")), _be),
            Law("TRANSISTOR", currents, _transistor_currents),
        ]


ELEMENT_TYPES: dict[str, type[Element]] = {
    "RESISTOR": Resistor,
    "TRANSISTOR": Transistor,
}


def _vd_demon(target: int, values: list[Value | None]) -> Value | object | None:
    """Once the resistances and both end voltages are known, the midpoint
    voltage becomes a fresh formal variable, not the divider formula, so a
    divider loaded at its midpoint still comes out right: the variable is
    solved by a consistency check further on."""
    return FRESH if target == 4 else None


@dataclass(eq=False)
class VoltageDivider(Part):
    """The `vd` macro-element: two resistors in series sharing a midpoint
    node. Its law VD-DEMON watches the two resistances and the two end
    voltages, and introduces a formal variable at the midpoint."""

    resistors: tuple[str, str] = ("", "")

    @classmethod
    def from_hint(cls, names: list[str]) -> VoltageDivider:
        top, bottom = names
        return cls(f"VD-{top}-{bottom}", resistors=(top, bottom))

    def make_laws(self, circuit: Circuit) -> list[Law]:
        top_r, bottom_r = (circuit.elements[r] for r in self.resistors)
        top_nodes = [circuit.node_at(t) for t in top_r.terminals()]
        bottom_nodes = [circuit.node_at(t) for t in bottom_r.terminals()]
        [mid] = [n for n in top_nodes if n in bottom_nodes]
        [top] = [n for n in top_nodes if n is not mid]
        [bottom] = [n for n in bottom_nodes if n is not mid]
        refs = (
            top_r.ref("RESISTANCE"),
            bottom_r.ref("RESISTANCE"),
            top.ref("VOLTAGE"),
            bottom.ref("VOLTAGE"),
            mid.ref("VOLTAGE"),
        )
        return [Law("VD-DEMON", refs, _vd_demon)]


# Hint keyword -> builder of its macro-element from the names in the hint.
HINT_TYPES: dict[str, Callable[[list[str]], Part]] = {
    "VD": VoltageDivider.from_hint,
}


def _kcl(target: int, values: list[Value | None]) -> Value | None:
    """The currents into a node sum to zero."""
    return -sum(v for i, v in enumerate(values) if i != target)


@dataclass(eq=False)
class Node(Part):
    """A set of connected terminals. `voltage` is the declared fixed voltage,
    or None; the VOLTAGE quantity holds the voltage EL works with.

    A fixed node stands for a voltage source (supply rail, ground), which
    sources or sinks any current, so KCL applies only to nodes that are not
    fixed."""

    voltage: float | None = None
    terminals: list[Terminal] = field(default_factory=list)

    def _quantities(self) -> list[Quantity]:
        voltage = Quantity(self.name, "VOLTAGE")
        if self.voltage is not None:
            voltage.premise(self.voltage)
        return [voltage]

    def make_laws(self, circuit: Circuit) -> list[Law]:
        if self.voltage is not None:
            return []
        currents = tuple(circuit.elements[t.element].ref("CURRENT", t.name) for t in self.terminals)
        return [Law("KCL", currents, _kcl)]


@dataclass(eq=False)
class Circuit:
    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
    macros: list[Part] = field(default_factory=list)

    def parts(self) -> list[Part]:
        return [*self.nodes.values(), *self.elements.values(), *self.macros]

    def part(self, name: str) -> Part:
        """The node or element called `name`. Raises KeyError."""
        return self.nodes.get(name) or self.elements[name]

    def ref(self, part: str, kind: str, label: str | None = None) -> Ref:
        """The quantity named `(part kind [label])`, e.g. `(R3 CURRENT #2)`."""
        return self.part(part).ref(kind, label)

    def node_at(self, terminal: Terminal) -> Node:
        return next(n for n in self.nodes.values() if terminal in n.terminals)

    def make_laws(self) -> None:
        """Build every part's laws and register each part as an owner of the
        quantities its laws relate. Call once the topology is complete.

        Owners are woken in registration order. A node's voltage is owned
        first by the elements at its terminals, in the order its `connect`
        entry lists them (the node knows who is connected to it), then by
        macro-elements watching it. In Example 1 this is why R1 runs before
        Q1 once INPUT's voltage is filled, so V7 is solved before NODE2's
        voltage is deduced from it, as in the memo."""
        for part in self.parts():
            part.laws = part.make_laws(self)
            for law in part.laws:
                for ref in law.refs:
                    if part not in ref.quantity.owners:
                        ref.quantity.owners.append(part)
        for node in self.nodes.values():
            order = [t.element for t in node.terminals]
            node.quantities["VOLTAGE", None].owners.sort(
                key=lambda p: order.index(p.name) if p.name in order else len(order)
            )
