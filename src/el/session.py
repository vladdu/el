"""Session: the command interpreter for `wire`, `analyze`, `why`, `change`, `what`.

`Session.run` takes command text (one or more forms) and returns one
structured result per form. Results render to memo text; the REPL is a thin
loop over this. The work of `analyze`, `what` and `change` is done by
`el.engine`; a session parses commands, words the engine's refusals and
builds results.
"""

import itertools
from collections.abc import Callable

from el import engine
from el.circuit import Circuit
from el.loader import WiringError, load
from el.quantity import FormalVariable, Ref, why_steps
from el.reader import QUOTE, Datum, ReadError, Symbol, read_all
from el.results import (
    Analysis,
    Answer,
    Contradiction,
    Error,
    LoadError,
    Result,
    Unfilled,
    Why,
    Wired,
)


class Session:
    def __init__(self) -> None:
        self.circuits: dict[str, Circuit] = {}
        self.current: Circuit | None = None
        self._variable_numbers = itertools.count(1)
        self._commands: dict[str, Callable[[list[Datum]], Result]] = {
            "WIRE": self._wire,
            "ANALYZE": self._analyze,
            "WHAT": self._what,
            "WHY": self._why,
            "CHANGE": self._change,
        }

    def new_variable(self) -> FormalVariable:
        """A fresh formal variable, V1, V2, ... in this session."""
        return FormalVariable(f"V{next(self._variable_numbers)}")

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
        try:
            fills = engine.analyze(circuit, self.new_variable)
        except engine.Contradicted as c:
            return _contradiction(circuit, c)
        return Analysis(circuit, fills)

    def _quantity(self, args: list[Datum], usage: str) -> tuple[Circuit, Ref] | Error:
        """The current circuit and the quantity named by `args`, which are
        `part kind [label]`; or the Error to report."""
        match args:
            case [Symbol() as part, Symbol() as kind]:
                label = None
            case [Symbol() as part, Symbol() as kind, Symbol() as label]:
                pass
            case _:
                return Error(f"usage: {usage}")
        circuit = self.current
        if circuit is None:
            return Error("no circuit analyzed yet")
        try:
            return circuit, circuit.ref(part, kind, label)
        except KeyError:
            name = " ".join(s for s in (part, kind, label) if s)
            return Error(f"{circuit.name} has no quantity ({name})")

    def _what(self, form: list[Datum]) -> Result:
        """`(what part kind [label])`: the quantity's value. If it is not
        filled, wishful thinking: fill it with a fresh formal variable,
        propagate, and answer with whatever that leads to."""
        found = self._quantity(form[1:], "(what part kind [label])")
        if isinstance(found, Error):
            return found
        circuit, ref = found
        try:
            value, fills, pending = engine.what(ref, self.new_variable)
        except engine.Contradicted as c:
            return _contradiction(circuit, c)
        return Answer(circuit, value, fills, pending)

    def _why(self, form: list[Datum]) -> Result:
        """`(why part kind [label])` on the current circuit."""
        found = self._quantity(form[1:], "(why part kind [label])")
        if isinstance(found, Error):
            return found
        circuit, ref = found
        return Why(circuit, why_steps(ref)) if ref.filled else Unfilled(ref)

    def _change(self, form: list[Datum]) -> Result:
        """`(change part kind [label] value)`: replace a premise's value
        (`engine.change`). Reports the new premise and the quantities filled
        again. A change that leads to a contradiction is undone."""
        usage = "(change part kind [label] value)"
        match form:
            case [_, *args, int() | float() as value]:
                found = self._quantity(args, usage)
            case _:
                return Error(f"usage: {usage}")
        if isinstance(found, Error):
            return found
        circuit, ref = found
        try:
            fills = engine.change(ref, float(value), self.new_variable)
        except engine.Refused as r:
            return _refusal(r)
        except engine.Contradicted as c:
            return _contradiction(circuit, c)
        return Analysis(circuit, fills)


def _refusal(refused: engine.Refused) -> Error:
    name = f"({' '.join(refused.ref.name)})"
    if isinstance(refused, engine.OperatingRegion):
        return Error(f"{name} is an operating region; switching transistor models is not supported")
    assert isinstance(refused, engine.NotAPremise)
    how = "has no value" if refused.law is None else f"is deduced by {refused.law}"
    return Error(f"{name} is not a premise: it {how}; only Givens and Defaults can change")


def _contradiction(circuit: Circuit, c: engine.Contradicted) -> Contradiction:
    return Contradiction(circuit, c.fills, c.law, c.conflicts, c.undone)
