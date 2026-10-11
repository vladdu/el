"""Propagation engine: local one-step deductions over an explicit agenda.

Filling a quantity wakes every part that owns it (has a law over it). A woken
part runs each of its laws; a law with exactly one unfilled ref fills it and
records a justification: the law plus the refs it read. Propagation runs
until the agenda is empty.

The agenda is a stack, not a FIFO queue: the most recently woken part runs
first (a part woken again moves to the top), and a fill's owners run in
their registration order. This follows each new fact's consequences
depth-first, which is the order the memo's transcripts show. It matters
when a quantity can be deduced two ways: in Example 3, KCL at NODE1 must
fill R2's current before R2's own OHM does, or R2's current gets a
different (equally valid) expression and the consistency check moves to
NODE1. With FIFO, R2 would run first.

The engine knows nothing about part types: parts bring their own laws (`el.circuit`).

Values may be linear expressions in formal variables (`el.expr`). When a law
reads a quantity, the values of solved formal variables are substituted in
and each one used becomes an antecedent `(V<n> VARVAL)`; the stored
expression is left as it is. A law whose refs are all filled runs a
consistency check: the difference between a ref's value and what the law
predicts for it must vanish. If that difference still has exactly one
unsolved formal variable, the check solves for it and fills its VARVAL. If
it has more, it is kept as a pending equation, retried whenever one of its
variables is solved; it solves the last one when all others are.

A law may instead fill its target with a fresh formal variable (its solver
returns `FRESH`): that is how a macro-element law such as VD-DEMON
introduces one.

The interface is one function per command, each one transaction:
`analyze`, `what` and `change`. The engine is the only code that writes
quantity state during a command, and every write goes through a trail.
Each fill records itself as a dependent of every quantity it read, so
`change` can retract a premise and, transitively, everything deduced from
it. A `change` or `what` that ends in a contradiction is undone by replaying
the trail backwards, after the contradiction report has captured the state
at the failed check; `analyze` keeps what it filled before the check.
"""

from collections.abc import Callable
from typing import Any

from el.circuit import Circuit, Part
from el.expr import Expr, NonLinear, substitute
from el.quantity import (
    FRESH,
    GIVEN,
    REGION,
    WHAT,
    Conflict,
    Fill,
    FormalVariable,
    Justification,
    Law,
    PendingEquation,
    Quantity,
    Ref,
    ReportedEquation,
    Solved,
    Undone,
    Value,
    why_steps,
)

type NewVariable = Callable[[], FormalVariable]


class Contradicted(Exception):
    """A law whose refs are all filled does not hold. `fills` are the fills
    made before it; `conflicts` are the law's quantities (hidden ones, ADR
    0001, left out), each with its value and `why` tree at the failed check.
    Nothing is filled by the failed check. After `analyze` the circuit keeps
    the state it had just before it; after `change` or `what` the command is
    undone, and `undone` says what it was."""

    def __init__(self, fills: list[Fill], law: str, conflicts: tuple[Conflict, ...]) -> None:
        super().__init__(law)
        self.fills = fills
        self.law = law
        self.conflicts = conflicts
        self.undone: Undone | None = None


class Refused(Exception):
    """`change` on a quantity that may not change. `ref` is the quantity."""

    def __init__(self, ref: Ref) -> None:
        super().__init__(ref)
        self.ref = ref


class NotAPremise(Refused):
    """Only premises may change. `law` is the law that deduced the
    quantity, or None if it has no value."""

    def __init__(self, ref: Ref, law: str | None) -> None:
        super().__init__(ref)
        self.law = law


class OperatingRegion(Refused):
    """Switching transistor models is not supported (ADR 0001)."""


class _Trail:
    """Every write a command makes to quantity state, so it can be undone."""

    def __init__(self) -> None:
        self._undo: list[Callable[[], None]] = []

    def set(self, obj: object, attr: str, value: Any) -> None:
        old = getattr(obj, attr)
        self._undo.append(lambda: setattr(obj, attr, old))
        setattr(obj, attr, value)

    def append(self, items: list, item: object) -> None:
        items.append(item)
        self._undo.append(items.pop)

    def remove(self, items: list, item: object) -> None:
        i = next(i for i, x in enumerate(items) if x is item)
        del items[i]
        self._undo.append(lambda: items.insert(i, item))

    def undo(self) -> None:
        while self._undo:
            self._undo.pop()()


class _Run:
    """One command's propagation. Collects the fills it makes, in order."""

    def __init__(self, new_variable: NewVariable) -> None:
        self.new_variable = new_variable
        self.trail = _Trail()
        self._agenda: list[Part] = []
        self._queued: set[int] = set()
        self.fills: list[Fill] = []

    def wake(self, part: Part) -> None:
        """Put `part` on top of the agenda (moving it if already there)."""
        if id(part) in self._queued:
            self._agenda.remove(part)
        self._queued.add(id(part))
        self._agenda.append(part)

    def fill(self, ref: Ref, value: Value, justification: Justification) -> None:
        """Fill `ref`'s quantity so that reading `ref` gives `value`. A
        hidden quantity (a complementary pair's offset) is filled like any
        other but not listed in `fills`, so it is never printed."""
        quantity = ref.quantity
        self.trail.set(quantity, "value", ref.sign * value)
        self.trail.set(quantity, "justification", justification)
        for antecedent in justification.antecedents:
            self.trail.append(antecedent.quantity.dependents, quantity)
        if not quantity.hidden:
            self.fills.append(Fill(ref, value))
        for part in reversed(quantity.owners):
            self.wake(part)
        if isinstance(quantity, FormalVariable):
            for equation in list(quantity.pending):
                self._retry(equation)

    def run(self) -> list[Fill]:
        """Propagate until the agenda is empty. Raises `Contradicted`."""
        while self._agenda:
            part = self._agenda.pop()
            self._queued.discard(id(part))
            for law in part.laws:
                self._apply(law)
        return self.fills

    def run_or_undo(self, undone: Undone) -> list[Fill]:
        """`run`, but undo every write of this command if it raises
        `Contradicted`, recording `undone` on it."""
        try:
            return self.run()
        except Contradicted as c:
            self.trail.undo()
            c.undone = undone
            raise

    def _contradicted(self, law: Law) -> Contradicted:
        conflicts = tuple(
            Conflict(Fill(r, r.value), why_steps(r)) for r in law.refs if not r.quantity.hidden
        )
        return Contradicted(self.fills, law.name, conflicts)

    def retract(self, quantity: Quantity) -> list[Quantity | PendingEquation]:
        """Forget `quantity` and, transitively, everything whose fill
        depended on it (quantities and VARVALs alike). Returns the forgotten
        quantities, `quantity` first, and the pending equations they
        supported. A dependent entry is followed only if that dependent's
        current fill still reads the quantity (entries go stale when a
        quantity is retracted and filled again from other antecedents)."""
        retracted: list[Quantity | PendingEquation] = []
        todo: list[Quantity | PendingEquation] = [quantity]
        while todo:
            q = todo.pop()
            if any(r is q for r in retracted):
                continue
            if isinstance(q, Quantity):
                todo.extend(d for d in q.dependents if d.justification and d.justification.reads(q))
                self.trail.set(q, "value", None)
                self.trail.set(q, "dependents", [])
            else:
                for variable in q.expr.variables:
                    self.trail.remove(variable.pending, q)
            self.trail.set(q, "justification", None)
            retracted.append(q)
        return retracted

    def _apply(self, law: Law) -> None:
        unfilled = [i for i, ref in enumerate(law.refs) if not ref.filled]
        if len(unfilled) > 1:
            return
        values: list[Value | None] = []
        used: list[FormalVariable] = []
        for ref in law.refs:
            value, variables = substitute(ref.value)
            values.append(value)
            used += [v for v in variables if v not in used]
        if not unfilled:
            self._check(law, values, used)
            return
        [target] = unfilled
        value = _solve(law, target, values)
        if value is None:
            return
        if value is FRESH:
            value = Expr.variable(self.new_variable())
        antecedents = law.refs[:target] + law.refs[target + 1 :] + _varvals(used)
        self.fill(law.refs[target], value, Justification(law.name, antecedents))

    def _check(self, law: Law, values: list[Value | None], used: list[FormalVariable]) -> None:
        """Consistency check of a law whose refs are all filled: raise
        `Contradicted` if it fails, solve its one unsolved formal variable if
        it has exactly one. A law that can predict none of its refs (BE
        outside the ACTIVE region) checks nothing."""
        residual = _residual(law, values)
        if residual is None:
            return
        actual, predicted = residual
        difference = actual - predicted
        if not isinstance(difference, Expr):
            if _differs(difference, max(_magnitude(actual), _magnitude(predicted))):
                raise self._contradicted(law)
            return
        justification = Justification(law.name, law.refs + _varvals(used))
        if len(difference.variables) == 1:
            variable, value = difference.solve()
            self.fill(Ref(variable), value, justification)
            return
        if any(e.law is law for e in difference.variables[0].pending):
            return  # this check is already pending
        equation = PendingEquation(law, difference, justification)
        for variable in difference.variables:
            self.trail.append(variable.pending, equation)
        for antecedent in justification.antecedents:
            self.trail.append(antecedent.quantity.dependents, equation)

    def _retry(self, equation: PendingEquation) -> None:
        """Retry a pending equation after one of its variables was solved:
        solve its last unsolved variable, or, if none is left, check it."""
        assert equation.justification is not None
        value, used = substitute(equation.expr)
        if not isinstance(value, Expr):
            e = equation.expr
            scale = max(abs(e.const), *(abs(c * v.value) for v, c in e.coefs.items()))
            if _differs(value, scale):
                raise self._contradicted(equation.law)
            return
        if len(value.variables) > 1:
            return
        variable, root = value.solve()
        # The variables substituted now were unsolved when the equation was
        # stored, so they are not among its antecedents yet.
        antecedents = equation.justification.antecedents + _varvals(used)
        self.fill(Ref(variable), root, Justification(equation.law.name, antecedents))


def _solve(law: Law, target: int, values: list[Value | None]) -> Solved:
    """What `law` deduces for refs[target] from `values` (None at target):
    a value, FRESH, or None if it cannot, including when that would not be
    linear."""
    try:
        return law.solve(target, values)
    except NonLinear:
        return None


def _residual(law: Law, values: list[Value | None]) -> tuple[Value, Value] | None:
    """(a ref's value, what `law` predicts for it from the others), for the
    first numeric ref the law can predict; None if there is none."""
    for k, actual in enumerate(values):
        if not isinstance(actual, int | float | Expr):
            continue
        predicted = _solve(law, k, [None if i == k else v for i, v in enumerate(values)])
        if predicted is not None and predicted is not FRESH:
            return actual, predicted
    return None


def _differs(difference: float, scale: float) -> bool:
    """Whether a check's residual is too large to be float rounding."""
    return abs(difference) > 1e-12 + 1e-9 * scale


def _magnitude(value: Value) -> float:
    """Size of a number, or of an expression's largest term, for tolerances."""
    if isinstance(value, Expr):
        return max(abs(value.const), *(abs(c) for c in value.coefs.values()))
    return abs(value)


def _varvals(variables: list[FormalVariable]) -> tuple[Ref, ...]:
    return tuple(Ref(v) for v in variables)


def analyze(circuit: Circuit, new_variable: NewVariable) -> list[Fill]:
    """Wake every part and run local one-step deductions to quiescence;
    return the fills made. Raises `Contradicted` if a law fails its check,
    keeping the fills made before it."""
    run = _Run(new_variable)
    for part in reversed(circuit.parts()):
        run.wake(part)
    return run.run()


def what(
    ref: Ref, new_variable: NewVariable
) -> tuple[Value, list[Fill], tuple[ReportedEquation, ...]]:
    """`ref`'s value, with known formal variables substituted, after the
    fills (if any) made to find it, and, if it is still an expression, the
    pending equations in its variables. An unfilled quantity is filled with
    a fresh formal variable (wishful thinking) and propagated. Raises
    `Contradicted`, with the `what` undone."""
    fills: list[Fill] = []
    if not ref.filled:
        run = _Run(new_variable)
        run.fill(ref, Expr.variable(new_variable()), Justification(WHAT))
        fills = run.run_or_undo(Undone(WHAT, ref, None))
    value, _ = substitute(ref.value)
    return value, fills, _pending(value)


def change(ref: Ref, value: Value, new_variable: NewVariable) -> list[Fill]:
    """Replace the premise `ref` with the Given `value`: retract it and
    everything deduced from it, wake every part that owned a retracted
    quantity, fill the new value and propagate. Returns the fills made,
    the new premise first. Raises `Refused` for a quantity that is not a
    premise, or is an operating region; raises `Contradicted`, with the
    change undone."""
    quantity = ref.quantity
    if quantity.kind == REGION:
        raise OperatingRegion(ref)
    justification = quantity.justification
    if justification is None or not justification.is_premise:
        raise NotAPremise(ref, None if justification is None else justification.law)
    old = ref.value
    run = _Run(new_variable)
    for retracted in reversed(run.retract(quantity)):
        if isinstance(retracted, Quantity):
            for owner in reversed(retracted.owners):
                run.wake(owner)
    run.fill(ref, value, Justification(GIVEN))
    return run.run_or_undo(Undone("CHANGE", ref, old))


def _pending(value: object) -> tuple[ReportedEquation, ...]:
    """The pending equations in `value`'s unsolved variables that still have
    more than one unsolved variable, each once, substituted."""
    if not isinstance(value, Expr):
        return ()
    equations: list[PendingEquation] = []
    for variable in value.variables:
        equations += [e for e in variable.pending if e not in equations]
    pending = []
    for equation in equations:
        expr, _ = substitute(equation.expr)
        if isinstance(expr, Expr) and len(expr.variables) > 1:
            pending.append(ReportedEquation(expr, equation.law.name))
    return tuple(pending)
