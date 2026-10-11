"""Propagation engine: local one-step deductions over an explicit FIFO queue.

Filling a quantity wakes every part that owns it (has a law over it). A woken
part runs each of its laws; a law with exactly one unfilled ref fills it and
records a justification: the law plus the refs it read. Propagation runs
until the queue is empty. The engine knows nothing about part types: parts
bring their own laws (`el.circuit`).
"""

import math
from collections import deque

from el.circuit import Circuit, Part
from el.quantity import Justification, Law, Ref, Value
from el.results import Fill


class Contradicted(Exception):
    """A law whose refs are all filled does not hold. Raised out of `run`;
    nothing is filled by the failed check, so the circuit keeps the state it
    had just before it. `fills` are the fills made before it."""

    def __init__(self, law: Law, fills: list[Fill]) -> None:
        super().__init__(law.name)
        self.law = law
        self.fills = fills


def _holds(law: Law) -> bool:
    """Whether a law whose refs are all filled holds: solving for the first
    ref the law can solve reproduces its value. A law that can solve for none
    of them (BE outside the ACTIVE region) checks nothing."""
    values = [ref.value for ref in law.refs]
    for k, actual in enumerate(values):
        expected = law.solve(k, values[:k] + [None] + values[k + 1 :])
        if expected is not None:
            return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
    return True


class Engine:
    """One propagation run. Collects the fills it makes, in order."""

    def __init__(self) -> None:
        self._queue: deque[Part] = deque()
        self._queued: set[int] = set()
        self.fills: list[Fill] = []

    def wake(self, part: Part) -> None:
        if id(part) not in self._queued:
            self._queued.add(id(part))
            self._queue.append(part)

    def fill(self, ref: Ref, value: Value, justification: Justification) -> None:
        """Fill `ref`'s quantity so that reading `ref` gives `value`."""
        quantity = ref.quantity
        quantity.value = ref.sign * value
        quantity.justification = justification
        self.fills.append(Fill(ref, value))
        for part in quantity.owners:
            self.wake(part)

    def run(self) -> list[Fill]:
        while self._queue:
            part = self._queue.popleft()
            self._queued.discard(id(part))
            for law in part.laws:
                self._apply(law)
        return self.fills

    def _apply(self, law: Law) -> None:
        unfilled = [i for i, ref in enumerate(law.refs) if not ref.filled]
        if not unfilled:
            if not _holds(law):
                raise Contradicted(law, self.fills)
            return
        if len(unfilled) != 1:
            return
        [target] = unfilled
        value = law.solve(target, [ref.value for ref in law.refs])
        if value is None:
            return
        antecedents = law.refs[:target] + law.refs[target + 1 :]
        self.fill(law.refs[target], value, Justification(law.name, antecedents))


def propagate(circuit: Circuit) -> list[Fill]:
    """Wake every part and run local one-step deductions to quiescence;
    return the fills made. Raises `Contradicted` if a law fails its check."""
    engine = Engine()
    for part in circuit.parts():
        engine.wake(part)
    return engine.run()
