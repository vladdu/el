"""Structured results returned by `Session`.

Every result renders to exactly the text the REPL prints, so rendering lives
here and nowhere else.
"""

from dataclasses import dataclass, field

from el.checks import Problem
from el.circuit import Circuit
from el.expr import Expr
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
    read back exactly. Expressions as `V3`, `(&* -2.0 V3)`,
    `(&+ 1.0 (&* -4.0 V3))`."""
    if isinstance(value, Expr):
        return _render_expr(value)
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


def _render_expr(expr: Expr) -> str:
    terms = [render_value(expr.const)] if expr.const != 0 else []
    for var, coef in expr.coefs.items():
        terms.append(var.name if coef == 1 else f"(&* {render_value(coef)} {var.name})")
    return terms[0] if len(terms) == 1 else f"(&+ {' '.join(terms)})"


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
class Answer(Result):
    """The outcome of `what`: the quantity's value, with known formal
    variables substituted, after the fills (if any) made to find it. The
    fills include the new formal variable and its VARVAL once solved."""

    circuit: Circuit
    value: Value
    fills: list[Fill] = field(default_factory=list)

    def render(self) -> str:
        answer = render_value(self.value)
        if not self.fills:
            return answer
        return "\n".join([*(fill.render() for fill in self.fills), "", answer])


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
