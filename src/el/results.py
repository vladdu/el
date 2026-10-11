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
class Equation:
    """A pending equation `expr = 0` from a check of law `law`, with known
    formal variables substituted. Renders `((&+ ...) = 0 - OHM)`."""

    expr: Value
    law: str

    def render(self) -> str:
        return f"({render_value(self.expr)} = 0 - {self.law})"


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
    pending: tuple[Equation, ...] = ()

    def render(self) -> str:
        answer = [render_value(self.value), *(e.render() for e in self.pending)]
        if not self.fills:
            return "\n".join(answer)
        return "\n".join([*(fill.render() for fill in self.fills), "", *answer])


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


def _name(ref: Ref) -> str:
    return f"({' '.join(ref.name)})"


def _shown(ref: Ref) -> tuple[Ref, ...]:
    """The antecedents of `ref`'s fill that `why` prints: hidden quantities (a
    transistor's operating region, ADR 0001) are recorded but not shown."""
    justification = ref.quantity.justification
    assert justification is not None, f"{ref} is not filled"
    return tuple(a for a in justification.antecedents if not a.quantity.hidden)


def _step(ref: Ref) -> str:
    justification = ref.quantity.justification
    assert justification is not None, f"{ref} is not filled"
    if justification.is_premise:
        return f"({_name(ref)} {justification.law})"
    antecedents = " ".join(_name(a) for a in _shown(ref))
    return f"({_name(ref)} <= ({antecedents}) - {justification.law})"


@dataclass(frozen=True)
class Why(Result):
    """The justification tree of a filled quantity: one step per quantity,
    breadth first from `steps[0]` (the quantity asked about), each quantity
    once, named as the first law that read it named it. Each step's
    justification is `step.quantity.justification`."""

    circuit: Circuit
    steps: tuple[Ref, ...]

    @classmethod
    def of(cls, circuit: Circuit, root: Ref) -> Why:
        steps, seen = [root], {id(root.quantity)}
        for ref in steps:  # `steps` grows while iterating: breadth first
            for antecedent in _shown(ref):
                if id(antecedent.quantity) not in seen:
                    seen.add(id(antecedent.quantity))
                    steps.append(antecedent)
        return cls(circuit, tuple(steps))

    def render(self) -> str:
        return "\n".join([*(_step(ref) for ref in self.steps), "QED"])


@dataclass(frozen=True)
class Unfilled(Result):
    """`why` asked about a quantity that has no value."""

    ref: Ref

    def render(self) -> str:
        return f"{_name(self.ref)} has no value"


@dataclass(frozen=True)
class Contradiction(Result):
    """`analyze` stopped because the filled quantities of law `law` disagree.
    `refs` are the conflicting quantities (hidden ones, ADR 0001, left out),
    each with its justification in `ref.quantity.justification`; `fills` are
    the fills made before the failed check. Renders the fills, then each
    conflicting quantity's value followed by its `why` tree, indented."""

    circuit: Circuit
    fills: list[Fill]
    law: str
    refs: tuple[Ref, ...]

    def render(self) -> str:
        lines = [fill.render() for fill in self.fills]
        lines.append(f";CONTRADICTION: law {self.law} does not hold")
        for ref in self.refs:
            lines.append(Fill(ref, ref.value).render())
            lines.extend(f"  {_step(step)}" for step in Why.of(self.circuit, ref).steps)
        return "\n".join(lines)
