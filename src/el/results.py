"""Structured results returned by `Session`.

Every result renders to exactly the text the REPL prints, so rendering lives
here and nowhere else.
"""

from dataclasses import dataclass, field

from el.checks import Problem
from el.circuit import Circuit
from el.quantity import Ref, Value


class Result:
    def render(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class Wired(Result):
    """A wiring diagram loaded successfully."""

    circuit: Circuit

    def render(self) -> str:
        return "DONE"


def render_value(value: Value) -> str:
    """A value as the memo prints it: numbers in [0.1, 1e8) (and zero) plain,
    e.g. `2.59148955`, others as `1.10638307E-3`, in the fewest digits that
    read back exactly."""
    if isinstance(value, int | float):
        x = float(value)
        if x == 0 or 0.1 <= abs(x) < 1e8:
            return repr(x)
        for digits in range(17):
            text = f"{x:.{digits}e}"
            if float(text) == x:
                break
        mantissa, exponent = text.split("e")
        if "." not in mantissa:
            mantissa += ".0"
        return f"{mantissa}E{int(exponent)}"
    return str(value)


@dataclass(frozen=True)
class Fill:
    """One quantity filled by a deduction, named by the ref the law used,
    e.g. `(R3 CURRENT #2 -1.10638304E-3)`."""

    ref: Ref
    value: Value

    def render(self) -> str:
        return f"({' '.join(self.ref.name)} {render_value(self.value)})"


@dataclass(frozen=True)
class Analysis(Result):
    """The outcome of `analyze`: every quantity filled, in fill order."""

    circuit: Circuit
    fills: list[Fill] = field(default_factory=list)

    def render(self) -> str:
        return "\n".join([*(fill.render() for fill in self.fills), "DONE"])


@dataclass(frozen=True)
class Error(Result):
    """A command that could not be carried out."""

    message: str

    def render(self) -> str:
        return f";ERROR: {self.message}"


@dataclass(frozen=True)
class LoadError(Result):
    """A rejected wiring diagram: every problem the load-time checks found.
    `name` is the circuit name, or None if the form had none."""

    name: str | None
    problems: tuple[Problem, ...]

    def render(self) -> str:
        named = f" {self.name}" if self.name else ""
        head = f";ERROR: wiring diagram{named} rejected"
        return "\n".join([head, *(f";  {p.message}" for p in self.problems)])
