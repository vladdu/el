"""Wiring-diagram loader: turns a read `wire` form into a `Circuit`.

Loading has three steps: parse the form into a `Diagram`, run every load-time
check on it (`el.checks`), then build the `Circuit`. Nothing is built unless
every check passes, so a rejected wiring diagram never replaces an existing
circuit.
"""

from el.checks import Connection, Diagram, Problem, check, node_names
from el.circuit import ELEMENT_TYPES, Circuit, Node, Terminal
from el.reader import Datum, Symbol


class WiringError(Exception):
    """A wiring diagram that cannot be loaded, with every problem found."""

    def __init__(self, name: str | None, problems: list[Problem]) -> None:
        super().__init__("; ".join(p.message for p in problems))
        self.name = name
        self.problems = problems


class _Malformed(Exception):
    pass


def load(form: list[Datum]) -> Circuit:
    """Load a read `(wire NAME clause...)` form."""
    if len(form) < 2 or not isinstance(form[1], Symbol):
        raise WiringError(None, [Problem("MALFORMED", "WIRE needs a circuit name")])
    try:
        diagram = _parse(form[1], form[2:])
    except _Malformed as e:
        raise WiringError(form[1], [Problem("MALFORMED", str(e))]) from None
    problems = check(diagram)
    if problems:
        raise WiringError(diagram.name, problems)
    return _build(diagram)


def _parse(name: Symbol, clauses: list[Datum]) -> Diagram:
    diagram = Diagram(name)
    for clause in clauses:
        if not (isinstance(clause, list) and clause and isinstance(clause[0], Symbol)):
            raise _Malformed(f"malformed clause: {clause!r}")
        keyword, entries = clause[0], clause[1:]
        if keyword == "NODE":
            for entry in entries:
                node = _node_declaration(entry)
                diagram.nodes[node.name] = node
        elif keyword == "CONNECT":
            diagram.connections.extend(_connection(entry) for entry in entries)
        elif keyword in ELEMENT_TYPES:
            for entry in entries:
                element_name, value = _name_value(entry)
                diagram.elements[element_name] = ELEMENT_TYPES[keyword].declare(element_name, value)
        else:
            raise _Malformed(f"unknown clause {keyword}")
    return diagram


def _name_value(entry: Datum) -> tuple[Symbol, float]:
    match entry:
        case [Symbol() as name, int() | float() as value]:
            return name, value
    raise _Malformed(f"expected (name value), got {entry!r}")


def _node_declaration(entry: Datum) -> Node:
    if isinstance(entry, Symbol):
        return Node(entry)
    name, voltage = _name_value(entry)
    return Node(name, voltage=float(voltage))


def _terminal(datum: Datum) -> Terminal:
    match datum:
        case [Symbol() as terminal, Symbol() as element]:
            return Terminal(element, terminal)
    raise _Malformed(f"expected (terminal element), got {datum!r}")


def _connection(entry: Datum) -> Connection:
    if not isinstance(entry, list) or not entry:
        raise _Malformed(f"malformed connection: {entry!r}")
    head, *rest = entry
    if isinstance(head, Symbol):
        return Connection(head, [_terminal(t) for t in rest])
    return Connection(None, [_terminal(t) for t in entry])


def _build(diagram: Diagram) -> Circuit:
    """Attach each connection's terminals to its node, naming anonymous nodes
    NODE1, NODE2, ... in `connect` order."""
    circuit = Circuit(diagram.name, dict(diagram.nodes), dict(diagram.elements))
    for name, connection in zip(node_names(diagram), diagram.connections, strict=True):
        if connection.node is None:
            circuit.nodes[name] = Node(Symbol(name))
        circuit.nodes[name].terminals.extend(connection.terminals)
    return circuit
