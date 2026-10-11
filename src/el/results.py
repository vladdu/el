"""Structured results returned by `Session`.

Every result renders to exactly the text the REPL prints, so rendering lives
here and nowhere else. The data in a result (fills, `why` steps, conflicts,
pending equations) is built by the domain modules (`el.quantity`,
`el.engine`); this module only renders it.
"""

from dataclasses import dataclass, field

from el.checks import Problem
from el.circuit import Circuit
from el.expr import Expr
from el.quantity import (
    Conflict,
    Fill,
    Ref,
    ReportedEquation,
    Step,
    Undone,
    Value,
    printed_antecedents,
)


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
        x = float(value) + 0.0  # -0.0 prints as 0.0, as in the memo
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


def render_fill(fill: Fill) -> str:
    """e.g. `(R3 CURRENT #2 -1.10638304E-3)`."""
    return f"({' '.join(fill.ref.name)} {render_value(fill.value)})"


@dataclass(frozen=True)
class Analysis(Result):
    """The outcome of `analyze`: every quantity filled, in fill order."""

    circuit: Circuit
    fills: list[Fill] = field(default_factory=list)

    def render(self) -> str:
        return "\n".join([*map(render_fill, self.fills), "DONE"])


def _render_equation(equation: ReportedEquation) -> str:
    """e.g. `((&+ ...) = 0 - OHM)`."""
    return f"({render_value(equation.expr)} = 0 - {equation.law})"


@dataclass(frozen=True)
class Answer(Result):
    """The outcome of `what`: the quantity's value, with known formal
    variables substituted, after the fills (if any) made to find it. The
    fills include the new formal variable and its VARVAL once solved. If the
    value is still an expression, `pending` are the pending equations in its
    variables, listed after it."""

    circuit: Circuit
    value: Value
    fills: list[Fill] = field(default_factory=list)
    pending: tuple[ReportedEquation, ...] = ()

    def render(self) -> str:
        answer = [render_value(self.value), *map(_render_equation, self.pending)]
        if not self.fills:
            return "\n".join(answer)
        return "\n".join([*map(render_fill, self.fills), "", *answer])


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


def _render_name(ref: Ref) -> str:
    return f"({' '.join(ref.name)})"


def _render_step(step: Step) -> str:
    """A premise or a supposition shows only its law, e.g.
    `((R1 RESISTANCE) GIVEN)` or `((OUTPUT VOLTAGE) WHAT)`; a deduction shows
    its antecedents, even none: `((R5 CURRENT ME) <= () - KCL)`."""
    name, law = _render_name(step.ref), step.justification.law
    if step.justification.is_premise or step.justification.is_supposition:
        return f"({name} {law})"
    antecedents = " ".join(_render_name(a) for a in printed_antecedents(step.justification))
    return f"({name} <= ({antecedents}) - {law})"


@dataclass(frozen=True)
class Why(Result):
    """The justification tree of a filled quantity, as it was when asked:
    one step per quantity, breadth first from `steps[0]` (the quantity asked
    about; see `quantity.why_steps`)."""

    circuit: Circuit
    steps: tuple[Step, ...]

    def render(self) -> str:
        return "\n".join([*map(_render_step, self.steps), "QED"])


@dataclass(frozen=True)
class Unfilled(Result):
    """`why` asked about a quantity that has no value."""

    ref: Ref

    def render(self) -> str:
        return f"{_render_name(self.ref)} has no value"


@dataclass(frozen=True)
class Contradiction(Result):
    """A law whose filled quantities disagree stopped propagation. `conflicts`
    are its quantities (hidden ones, ADR 0001, left out), each with its value
    and `why` tree at the failed check; `fills` are the fills made before it.
    `undone` is set when the command was a `change` or `what` that was
    undone. Renders the fills, then each conflicting quantity's value
    followed by its `why` tree, indented."""

    circuit: Circuit
    fills: list[Fill]
    law: str
    conflicts: tuple[Conflict, ...]
    undone: Undone | None = None

    def render(self) -> str:
        lines = [*map(render_fill, self.fills)]
        lines.append(f";CONTRADICTION: law {self.law} does not hold")
        for conflict in self.conflicts:
            lines.append(render_fill(conflict.fill))
            lines.extend(f"  {_render_step(step)}" for step in conflict.why)
        if self.undone is not None:
            name = _render_name(self.undone.ref)
            value = self.undone.value
            now = "has no value" if value is None else f"is still {render_value(value)}"
            lines.append(f";{self.undone.command} UNDONE: {name} {now}")
        return "\n".join(lines)
