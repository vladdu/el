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
"""

from collections.abc import Callable

from el.circuit import Circuit, Part
from el.expr import Expr, NonLinear, substitute
from el.quantity import FormalVariable, Justification, Law, Ref, Value
from el.results import Fill


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
        antecedents = law.refs[:target] + law.refs[target + 1 :] + _varvals(used)
        self.fill(law.refs[target], value, Justification(law.name, antecedents))

    def _check(self, law: Law, values: list[Value | None], used: list[FormalVariable]) -> None:
        """Consistency check of a law whose refs are all filled."""
        residual = _residual(law, values)
        if not isinstance(residual, Expr):
            # A numeric residual should be zero; contradictions are ticket 10.
            return
        if len(residual.variables) > 1:
            # More than one unsolved variable: a pending equation (ticket 11).
            return
        variable, value = residual.solve()
        antecedents = law.refs + _varvals(used)
        self.fill(Ref(variable), value, Justification(law.name, antecedents))


def _solve(law: Law, target: int, values: list[Value | None]) -> Value | None:
    """What `law` deduces for refs[target] from `values` (None at target),
    or None if it cannot, including when that would not be linear."""
    try:
        return law.solve(target, values)
    except NonLinear:
        return None


def _residual(law: Law, values: list[Value | None]) -> Value | None:
    """A ref's value minus what `law` predicts for it from the others, for
    the first numeric ref the law can predict; None if there is none."""
    for k, actual in enumerate(values):
        if not isinstance(actual, int | float | Expr):
            continue
        predicted = _solve(law, k, [None if i == k else v for i, v in enumerate(values)])
        if predicted is not None:
            return actual - predicted
    return None


def _varvals(variables: list[FormalVariable]) -> tuple[Ref, ...]:
    return tuple(Ref(v) for v in variables)


def propagate(circuit: Circuit, engine: Engine | None = None) -> list[Fill]:
    """Wake every part and run local one-step deductions to quiescence;
    return the fills made."""
    engine = engine or Engine()
    for part in reversed(circuit.parts()):
        engine.wake(part)
    return engine.run()
