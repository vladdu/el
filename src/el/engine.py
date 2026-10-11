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

Each fill records itself as a dependent of every quantity it read, so
`retract` can forget a quantity and, transitively, everything deduced from
it (`change`). A change that ends in a contradiction is undone: `snapshot`
records the state before it, and restoring puts every quantity, formal
variable and pending equation back as it was.
"""

from collections.abc import Callable

from el.circuit import Circuit, Part
from el.expr import Expr, NonLinear, substitute
from el.quantity import (
    FRESH,
    GIVEN,
    FormalVariable,
    Justification,
    Law,
    PendingEquation,
    Quantity,
    Ref,
    Solved,
    Value,
)
from el.results import Fill


class Contradicted(Exception):
    """A law whose refs are all filled does not hold. Raised out of `run`;
    nothing is filled by the failed check, so the circuit keeps the state it
    had just before it. `fills` are the fills made before it."""

    def __init__(self, law: Law, fills: list[Fill]) -> None:
        super().__init__(law.name)
        self.law = law
        self.fills = fills


class Engine:
    """One propagation run. Collects the fills it makes, in order.
    `new_variable` makes a fresh formal variable (numbered per session)."""

    def __init__(self, new_variable: Callable[[], FormalVariable]) -> None:
        self.new_variable = new_variable
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
        quantity.value = ref.sign * value
        quantity.justification = justification
        for antecedent in justification.antecedents:
            antecedent.quantity.dependents.append(quantity)
        if not quantity.hidden:
            self.fills.append(Fill(ref, value))
        for part in reversed(quantity.owners):
            self.wake(part)
        if isinstance(quantity, FormalVariable):
            for equation in list(quantity.pending):
                self._retry(equation)

    def run(self) -> list[Fill]:
        while self._agenda:
            part = self._agenda.pop()
            self._queued.discard(id(part))
            for law in part.laws:
                self._apply(law)
        return self.fills

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
                raise Contradicted(law, self.fills)
            return
        justification = Justification(law.name, law.refs + _varvals(used))
        if len(difference.variables) == 1:
            variable, value = difference.solve()
            self.fill(Ref(variable), value, justification)
            return
        if any(e.law is law for e in difference.variables[0].pending):
            return  # this check is already pending
        equation = PendingEquation(law, difference, justification)
        for antecedent in justification.antecedents:
            antecedent.quantity.dependents.append(equation)

    def _retry(self, equation: PendingEquation) -> None:
        """Retry a pending equation after one of its variables was solved:
        solve its last unsolved variable, or, if none is left, check it."""
        assert equation.justification is not None
        value, used = substitute(equation.expr)
        if not isinstance(value, Expr):
            e = equation.expr
            scale = max(abs(e.const), *(abs(c * v.value) for v, c in e.coefs.items()))
            if _differs(value, scale):
                raise Contradicted(equation.law, self.fills)
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


def retract(quantity: Quantity) -> list[Quantity | PendingEquation]:
    """Forget `quantity` and, transitively, everything whose fill depended on
    it (quantities and VARVALs alike). Returns the forgotten quantities,
    `quantity` first, and the pending equations they supported. A dependent
    entry is followed only if that dependent's current fill still reads the
    quantity (entries go stale when a quantity is retracted and filled again
    from other antecedents)."""
    retracted: list[Quantity | PendingEquation] = []
    todo: list[Quantity | PendingEquation] = [quantity]
    while todo:
        q = todo.pop()
        if any(r is q for r in retracted):
            continue
        if isinstance(q, Quantity):
            todo.extend(d for d in q.dependents if d.justification and d.justification.reads(q))
        q.forget()
        retracted.append(q)
    return retracted


def change(engine: Engine, ref: Ref, value: Value) -> list[Fill]:
    """Replace the premise `ref` with the Given `value`: retract it and
    everything deduced from it, wake every part that owned a retracted
    quantity, fill the new value and propagate. Raises `Contradicted`, leaving
    the circuit as the failed check found it (see `snapshot`)."""
    for retracted in reversed(retract(ref.quantity)):
        if isinstance(retracted, Quantity):
            for owner in reversed(retracted.owners):
                engine.wake(owner)
    engine.fill(ref, value, Justification(GIVEN))
    return engine.run()


def snapshot(circuit: Circuit) -> Callable[[], None]:
    """Record the state of every quantity of `circuit` and of every formal
    variable and pending equation reachable from them. Returns a function
    that restores exactly that state (undoing a `change`)."""
    quantities: dict[int, tuple] = {}
    equations: dict[int, tuple] = {}
    todo: list[Quantity | PendingEquation] = [
        q for part in circuit.parts() for q in part.quantities.values()
    ]
    while todo:
        item = todo.pop()
        if id(item) in quantities or id(item) in equations:
            continue
        if item.justification is not None:
            todo += [a.quantity for a in item.justification.antecedents]
        if isinstance(item, PendingEquation):
            equations[id(item)] = (item, item.justification)
            todo += item.expr.variables
            continue
        pending = list(item.pending) if isinstance(item, FormalVariable) else []
        quantities[id(item)] = (
            item,
            item.value,
            item.justification,
            list(item.dependents),
            pending,
        )
        todo += item.dependents + pending
        if isinstance(item.value, Expr):
            todo += item.value.variables

    def restore() -> None:
        for equation, justification in equations.values():
            equation.justification = justification
        for quantity, value, justification, dependents, pending in quantities.values():
            quantity.value, quantity.justification = value, justification
            quantity.dependents = list(dependents)
            if isinstance(quantity, FormalVariable):
                quantity.pending = list(pending)

    return restore


def propagate(circuit: Circuit, engine: Engine) -> list[Fill]:
    """Wake every part and run local one-step deductions to quiescence;
    return the fills made. Raises `Contradicted` if a law fails its check."""
    for part in reversed(circuit.parts()):
        engine.wake(part)
    return engine.run()
