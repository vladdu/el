"""Wiring-diagram loader: turns a read `wire` form into a `Circuit`.

The circuit is built completely before it is returned, so a rejected wiring
diagram never replaces an existing circuit.
"""

from el.circuit import ELEMENT_TYPES, Circuit, Node, Terminal
from el.reader import Datum, Symbol


class WiringError(Exception):
    """A wiring diagram that cannot be loaded."""


def load(form: list[Datum]) -> Circuit:
    """Load a read `(wire NAME clause...)` form."""
    if len(form) < 2 or not isinstance(form[1], Symbol):
        raise WiringError("WIRE needs a circuit name")
    circuit = Circuit(form[1])
    connects: list[list[Datum]] = []
    for clause in form[2:]:
        if not (isinstance(clause, list) and clause and isinstance(clause[0], Symbol)):
            raise WiringError(f"malformed clause: {clause!r}")
        keyword, entries = clause[0], clause[1:]
        if keyword == "NODE":
            for entry in entries:
                node = _node_declaration(entry)
                circuit.nodes[node.name] = node
        elif keyword == "CONNECT":
            connects.extend(entries)
        elif keyword in ELEMENT_TYPES:
            for entry in entries:
                name, value = _name_value(entry)
                circuit.elements[name] = ELEMENT_TYPES[keyword].declare(name, value)
        else:
            raise WiringError(f"unknown clause {keyword}")
    _connect(circuit, connects)
    return circuit


def _name_value(entry: Datum) -> tuple[Symbol, float]:
    match entry:
        case [Symbol() as name, int() | float() as value]:
            return name, value
    raise WiringError(f"expected (name value), got {entry!r}")


def _node_declaration(entry: Datum) -> Node:
    if isinstance(entry, Symbol):
        return Node(entry)
    name, voltage = _name_value(entry)
    return Node(name, voltage=float(voltage))


def _terminal(datum: Datum) -> Terminal:
    match datum:
        case [Symbol() as terminal, Symbol() as element]:
            return Terminal(element, terminal)
    raise WiringError(f"expected (terminal element), got {datum!r}")


def _connect(circuit: Circuit, connects: list[Datum]) -> None:
    """Attach each connection's terminals to its node, naming anonymous nodes
    NODE1, NODE2, ... in `connect` order."""
    anonymous = 0
    for connection in connects:
        if not isinstance(connection, list) or not connection:
            raise WiringError(f"malformed connection: {connection!r}")
        head, *rest = connection
        if isinstance(head, Symbol):
            node = circuit.nodes.get(head)
            if node is None:
                raise WiringError(f"undeclared node {head}")
        else:
            anonymous += 1
            node = Node(Symbol(f"NODE{anonymous}"))
            circuit.nodes[node.name] = node
            rest = connection
        node.terminals.extend(_terminal(t) for t in rest)
