"""Load-time checks on a parsed wiring diagram.

The loader parses a `wire` form into a `Diagram` (declarations and
connections, nothing built yet) and runs every function in `CHECKS` on it.
Each check yields `Problem`s; any problem rejects the whole diagram.

To add a check, write `def check_x(diagram) -> Iterator[Problem]` and append
it to `CHECKS`. Checks see every declared element (whatever its type, via its
`terminals()`) so new element types are covered without changes here; hint
checks (vd, cp) can read whatever the loader adds to `Diagram`.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from el.circuit import Element, Node, Resistor, Terminal


@dataclass(frozen=True)
class Problem:
    """One reason a wiring diagram was rejected. `kind` is a stable tag such
    as `UNDECLARED-PART`; `message` is the readable text."""

    kind: str
    message: str


@dataclass
class Connection:
    """One `connect` entry: a named node (or None for an anonymous one) and
    the terminals listed in it."""

    node: str | None
    terminals: list[Terminal]


@dataclass
class Diagram:
    """A parsed wiring diagram, before it is checked and built."""

    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
    connections: list[Connection] = field(default_factory=list)
    hints: list[Hint] = field(default_factory=list)


@dataclass
class Hint:
    """One hint, e.g. `(vd r1 r2)`: its keyword and the part names it lists."""

    kind: str
    names: list[str]


def check_undeclared_parts(diagram: Diagram) -> Iterator[Problem]:
    for connection in diagram.connections:
        if connection.node is not None and connection.node not in diagram.nodes:
            yield Problem("UNDECLARED-PART", f"connection names undeclared node {connection.node}")
        for terminal in connection.terminals:
            element = diagram.elements.get(terminal.element)
            if element is None:
                yield Problem(
                    "UNDECLARED-PART",
                    f"{terminal} names undeclared element {terminal.element}",
                )
            elif terminal not in element.terminals():
                yield Problem(
                    "UNKNOWN-TERMINAL",
                    f"{terminal}: {element.name} has no terminal {terminal.name}",
                )


def check_unconnected_parts(diagram: Diagram) -> Iterator[Problem]:
    connected_nodes = {c.node for c in diagram.connections}
    connected_elements = {t.element for c in diagram.connections for t in c.terminals}
    for name in diagram.nodes:
        if name not in connected_nodes:
            yield Problem("UNCONNECTED-PART", f"node {name} is declared but never connected")
    for name in diagram.elements:
        if name not in connected_elements:
            yield Problem("UNCONNECTED-PART", f"element {name} is declared but never connected")


def check_terminals_connected_once(diagram: Diagram) -> Iterator[Problem]:
    seen: dict[Terminal, list[str]] = {}
    for node, connection in zip(node_names(diagram), diagram.connections, strict=True):
        for terminal in connection.terminals:
            seen.setdefault(terminal, []).append(node)
    for terminal, nodes in seen.items():
        if len(nodes) > 1:
            yield Problem(
                "TERMINAL-CONNECTED-TWICE",
                f"{terminal} is connected to both {' and '.join(nodes)}",
            )


def check_terminals_connected(diagram: Diagram) -> Iterator[Problem]:
    """Every terminal of a connected element is connected. (An element with
    no connected terminal at all is reported by `check_unconnected_parts`.)"""
    connected = {t for c in diagram.connections for t in c.terminals}
    for element in diagram.elements.values():
        terminals = element.terminals()
        if any(t in connected for t in terminals):
            for terminal in terminals:
                if terminal not in connected:
                    yield Problem("UNCONNECTED-TERMINAL", f"{terminal} is not connected")


def check_vd_hints(diagram: Diagram) -> Iterator[Problem]:
    """A `vd` hint names two resistors that share exactly one node."""
    nodes_of: dict[Terminal, str] = {}
    for node, connection in zip(node_names(diagram), diagram.connections, strict=True):
        for terminal in connection.terminals:
            nodes_of[terminal] = node
    for hint in diagram.hints:
        if hint.kind != "VD":
            continue
        text = f"(VD {' '.join(hint.names)})"
        resistors = [diagram.elements.get(n) for n in hint.names]
        if len(resistors) != 2 or not all(isinstance(r, Resistor) for r in resistors):
            yield Problem("BAD-HINT", f"{text} must name two resistors")
            continue
        top, bottom = ({nodes_of.get(t) for t in r.terminals()} - {None} for r in resistors)
        if len(top & bottom) != 1 or len(top | bottom) != 3:
            yield Problem("BAD-HINT", f"{text}: the resistors must share exactly one node")


def node_names(diagram: Diagram) -> list[str]:
    """The node name of each connection, numbering anonymous ones NODE1, NODE2,
    ... in `connect` order (the loader names them the same way)."""
    names, anonymous = [], 0
    for connection in diagram.connections:
        if connection.node is None:
            anonymous += 1
            names.append(f"NODE{anonymous}")
        else:
            names.append(connection.node)
    return names


CHECKS: list[Callable[[Diagram], Iterator[Problem]]] = [
    check_undeclared_parts,
    check_unconnected_parts,
    check_terminals_connected_once,
    check_terminals_connected,
    check_vd_hints,
]


def check(diagram: Diagram) -> list[Problem]:
    return [problem for c in CHECKS for problem in c(diagram)]
