"""Session: the command interpreter for `wire`, `analyze`, `why`, `change`, `what`.

`Session.run` takes command text (one or more forms) and returns one
structured result per form. Results render to memo text; the REPL is a thin
loop over this.
"""

import itertools
from collections.abc import Callable

from el import engine
from el.circuit import Circuit
from el.expr import Expr, substitute
from el.loader import WiringError, load
from el.quantity import FormalVariable, Justification
from el.reader import QUOTE, Datum, ReadError, Symbol, read_all
from el.results import Analysis, Answer, Error, LoadError, Result, Wired

# The law recorded for a formal variable introduced by `what`.
WHAT = "WHAT"


class Session:
    def __init__(self) -> None:
        self.circuits: dict[str, Circuit] = {}
        self.current: Circuit | None = None
        self._variable_numbers = itertools.count(1)
        self._commands: dict[str, Callable[[list[Datum]], Result]] = {
            "WIRE": self._wire,
            "ANALYZE": self._analyze,
            "WHAT": self._what,
        }

    def new_variable(self) -> FormalVariable:
        """A fresh formal variable, V1, V2, ... in this session."""
        return FormalVariable(f"V{next(self._variable_numbers)}")

    def _engine(self) -> engine.Engine:
        return engine.Engine(self.new_variable)

    def run(self, text: str) -> list[Result]:
        try:
            forms = read_all(text)
        except ReadError as e:
            return [Error(str(e))]
        return [self._eval(form) for form in forms]

    def _eval(self, form: Datum) -> Result:
        if not (isinstance(form, list) and form and isinstance(form[0], Symbol)):
            return Error(f"not a command: {form!r}")
        command = self._commands.get(form[0])
        if command is None:
            return Error(f"unknown command {form[0]}")
        return command(form)

    def _wire(self, form: list[Datum]) -> Result:
        try:
            circuit = load(form)
        except WiringError as e:
            return LoadError(e.name, tuple(e.problems))
        self.circuits[circuit.name] = circuit
        return Wired(circuit)

    def _analyze(self, form: list[Datum]) -> Result:
        match form:
            case [_, [Symbol() as q, Symbol() as name]] if q == QUOTE:
                pass
            case [_, Symbol() as name]:
                pass
            case _:
                return Error("usage: (analyze 'name)")
        circuit = self.circuits.get(name)
        if circuit is None:
            return Error(f"no circuit named {name}")
        self.current = circuit
        return Analysis(circuit, engine.propagate(circuit, self._engine()))

    def _what(self, form: list[Datum]) -> Result:
        """`(what part kind [label])`: the quantity's value. If it is not
        filled, wishful thinking: fill it with a fresh formal variable,
        propagate, and answer with whatever that leads to."""
        match form:
            case [_, Symbol() as part, Symbol() as kind]:
                label = None
            case [_, Symbol() as part, Symbol() as kind, Symbol() as label]:
                pass
            case _:
                return Error("usage: (what part kind [label])")
        circuit = self.current
        if circuit is None:
            return Error("no circuit analyzed yet")
        try:
            ref = circuit.ref(part, kind, label)
        except KeyError:
            return Error(f"no quantity {part} {kind}{f' {label}' if label else ''}")
        fills = []
        if not ref.filled:
            run = self._engine()
            run.fill(ref, Expr.variable(self.new_variable()), Justification(WHAT))
            fills = run.run()
        value, _ = substitute(ref.value)
        return Answer(circuit, value, fills)
