"""Session: the command interpreter for `wire`, `analyze`, `why`, `change`, `what`.

`Session.run` takes command text (one or more forms) and returns one
structured result per form. Results render to memo text; the REPL is a thin
loop over this.
"""

from collections.abc import Callable

from el import engine
from el.circuit import Circuit
from el.loader import WiringError, load
from el.reader import QUOTE, Datum, ReadError, Symbol, read_all
from el.results import Analysis, Error, LoadError, Result, Unfilled, Why, Wired


class Session:
    def __init__(self) -> None:
        self.circuits: dict[str, Circuit] = {}
        self.current: Circuit | None = None
        self._commands: dict[str, Callable[[list[Datum]], Result]] = {
            "WIRE": self._wire,
            "ANALYZE": self._analyze,
            "WHY": self._why,
        }

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
        return Analysis(circuit, engine.propagate(circuit))

    def _why(self, form: list[Datum]) -> Result:
        """`(why part kind [label])` on the current circuit."""
        match form:
            case [_, Symbol() as part, Symbol() as kind]:
                label = None
            case [_, Symbol() as part, Symbol() as kind, Symbol() as label]:
                pass
            case _:
                return Error("usage: (why part quantity [terminal])")
        circuit = self.current
        if circuit is None:
            return Error("no circuit analyzed yet")
        try:
            ref = circuit.ref(part, kind, label)
        except KeyError:
            name = " ".join(s for s in (part, kind, label) if s)
            return Error(f"{circuit.name} has no quantity ({name})")
        return Why.of(circuit, ref) if ref.filled else Unfilled(ref)
