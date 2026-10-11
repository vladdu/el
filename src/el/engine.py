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
unsolved formal variable, the check solves for it and fills its VARVAL.

A law may instead fill its target with a fresh formal variable (its solver
returns `FRESH`): that is how a macro-element's demon introduces one.

Each fill records itself as a dependent of every quantity it read, so
`retract` can forget a quantity and, transitively, everything deduced from
it (`change`).
"""

from collections.abc import Callable

from el.circuit import Circuit, Part
from el.expr import Expr, NonLinear, substitute
from el.quantity import FRESH, FormalVariable, Justification, Law, Quantity, Ref, Value
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

    def __init__(self, new_variable: Callable[[], FormalVariable] | None = None) -> None:
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
        """Fill `ref`'s quantity so that reading `ref` gives `value`."""
        quantity = ref.quantity
        quantity.value = ref.sign * value
        quantity.justification = justification
        for antecedent in justification.antecedents:
            antecedent.quantity.dependents.append(quantity)
        self.fills.append(Fill(ref, value))
        for part in reversed(quantity.owners):
            self.wake(part)

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
            scale = max(_magnitude(actual), _magnitude(predicted))
            if abs(difference) > 1e-12 + 1e-9 * scale:
                raise Contradicted(law, self.fills)
            return
        if len(difference.variables) > 1:
            # More than one unsolved variable: a pending equation (ticket 11).
            return
        variable, value = difference.solve()
        antecedents = law.refs + _varvals(used)
        self.fill(Ref(variable), value, Justification(law.name, antecedents))


def _solve(law: Law, target: int, values: list[Value | None]) -> Value | object | None:
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


def _magnitude(value: Value) -> float:
    """Size of a number, or of an expression's largest term, for tolerances."""
    if isinstance(value, Expr):
        return max(abs(value.const), *(abs(c) for c in value.coefs.values()))
    return abs(value)


def _varvals(variables: list[FormalVariable]) -> tuple[Ref, ...]:
    return tuple(Ref(v) for v in variables)


def retract(quantity: Quantity) -> list[Quantity]:
    """Forget `quantity` and, transitively, everything whose fill depended on
    it (quantities and VARVALs alike). Returns the forgotten quantities,
    `quantity` first. A dependent entry is followed only if that dependent's
    current fill still reads the quantity (entries go stale when a quantity
    is retracted and filled again from other antecedents)."""
    retracted, todo = [], [quantity]
    while todo:
        q = todo.pop()
        if any(r is q for r in retracted):
            continue
        todo.extend(d for d in q.dependents if d.depends_on(q))
        q.forget()
        retracted.append(q)
    return retracted


def propagate(circuit: Circuit, engine: Engine | None = None) -> list[Fill]:
    """Wake every part and run local one-step deductions to quiescence;
    return the fills made. Raises `Contradicted` if a law fails its check."""
    engine = engine or Engine()
    for part in reversed(circuit.parts()):
        engine.wake(part)
    return engine.run()
