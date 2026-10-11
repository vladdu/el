"""Quantities, the names they are read and written under, justifications, laws.

A `Quantity` is one value of one part (NODE2's voltage, R4's current). A
`Ref` is a signed name for a quantity: a resistor owns a single current
quantity, named `ME`, which is also its `#1` current, and its `#2` current is
the same quantity with the opposite sign. Laws read and fill quantities
through refs, and fills and justifications remember which ref was used, so
output names a quantity the way the law that touched it saw it, as the memo
does (`(R4 CURRENT ME ...)` from OHM, `(R3 CURRENT #2 ...)` from KCL).

A `Law` is an equation over refs, given as a solver for each of them. A law
whose refs are all filled but one fills that one (if its solver can).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from el.circuit import Part
    from el.expr import Expr

# A quantity's value: a number or a linear expression in formal variables
# (`el.expr`). Laws only use +, -, unary -, and * or / by numbers on values,
# so they work on both. Non-numeric values (e.g. an operating region, ADR
# 0001) are fine too: laws that read them just compare them.
type Value = float | Expr

GIVEN = "GIVEN"
DEFAULT = "DEFAULT"

# Operating region values (ADR 0001). A region-dependent law solves only when
# its region quantity reads ACTIVE.
ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class Justification:
    """How a quantity was filled: by `law` from `antecedents` (the refs it
    read), or as a premise (law GIVEN or DEFAULT, no antecedents)."""

    law: str
    antecedents: tuple[Ref, ...] = ()

    @property
    def is_premise(self) -> bool:
        return self.law in (GIVEN, DEFAULT)


@dataclass(eq=False)
class Quantity:
    """One value of one part, named canonically `(part kind [label])`.

    Identity matters: two quantities are equal only if they are the same
    object. `owners` are the parts with a law over this quantity; filling it
    wakes them. `dependents` are the quantities whose fills read this one
    (recorded by the engine; may be stale after a retraction, so check their
    justification before trusting an entry). A `hidden` quantity (a
    transistor's operating region, ADR 0001) is recorded as an antecedent
    like any other but left out of `why` output."""

    part: str
    kind: str
    label: str | None = None
    value: Value | None = None
    justification: Justification | None = None
    owners: list[Part] = field(default_factory=list)
    hidden: bool = False
    dependents: list[Quantity] = field(default_factory=list)

    def depends_on(self, quantity: Quantity) -> bool:
        """Whether this quantity's current fill read `quantity`."""
        j = self.justification
        return j is not None and any(a.quantity is quantity for a in j.antecedents)

    def forget(self) -> None:
        """Drop the value and justification (retraction)."""
        self.value = None
        self.justification = None
        self.dependents = []

    @property
    def filled(self) -> bool:
        return self.value is not None

    def premise(self, value: Value, law: str = GIVEN) -> None:
        """Fill as a premise (used when a circuit is built)."""
        self.value = value
        self.justification = Justification(law)

    def __repr__(self) -> str:
        return f"Quantity({' '.join(canonical_ref(self).name)})"


@dataclass(eq=False)
class FormalVariable(Quantity):
    """A formal variable `V<n>`, introduced as the value of a quantity whose
    value is not known. It is itself a quantity, `(V<n> VARVAL)`, filled with
    a number when a consistency check solves for it; its justification is
    that check. `pending` are the pending equations it appears in."""

    kind: str = "VARVAL"
    pending: list[PendingEquation] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.part


@dataclass(eq=False)
class PendingEquation:
    """`expr = 0`, from a consistency check of `law` that left more than one
    formal variable unsolved. Kept on each of its variables and retried
    whenever one of them is solved; it solves the last one when all others
    are. Its justification is the check (the law's refs plus the VARVALs
    substituted into it), so retracting any of those retracts it, like a
    quantity (`el.engine.retract`). It has no owners: nothing is woken when it
    goes."""

    law: Law
    expr: Expr
    justification: Justification | None
    owners: list[Part] = field(default_factory=list)
    dependents: list[Quantity] = field(default_factory=list)

    def __post_init__(self) -> None:
        for variable in self.expr.variables:
            variable.pending.append(self)

    def depends_on(self, quantity: Quantity) -> bool:
        j = self.justification
        return j is not None and any(a.quantity is quantity for a in j.antecedents)

    def forget(self) -> None:
        """Drop the equation (retraction)."""
        self.justification = None
        for variable in self.expr.variables:
            variable.pending.remove(self)

    def __repr__(self) -> str:
        return f"PendingEquation({self.expr!r} = 0 - {self.law.name})"


@dataclass(frozen=True)
class Ref:
    """A signed name for a quantity: reading it gives `sign * value`."""

    quantity: Quantity
    label: str | None = None
    sign: int = 1

    @property
    def name(self) -> tuple[str, ...]:
        q = self.quantity
        return (q.part, q.kind) if self.label is None else (q.part, q.kind, self.label)

    @property
    def filled(self) -> bool:
        return self.quantity.filled

    @property
    def value(self) -> Value | None:
        v = self.quantity.value
        return None if v is None else self.sign * v

    def __repr__(self) -> str:
        return f"Ref({' '.join(self.name)})"


def canonical_ref(quantity: Quantity) -> Ref:
    return Ref(quantity, quantity.label, 1)


class _Fresh:
    def __repr__(self) -> str:
        return "FRESH"


# What a solver returns to fill its target with a fresh formal variable
# instead of a value: a macro-element's demon law (VD-DEMON) does this. The
# engine makes the variable. Such a law states no equation, so it is never
# used for a consistency check.
FRESH = _Fresh()


# solve(target, values): the value of refs[target] given `values`, the values
# of all refs in order (values[target] is None), or None if this law cannot
# deduce that ref (e.g. OHM cannot find a resistance from zero current), or
# FRESH.
type Solver = Callable[[int, list[Value | None]], Value | _Fresh | None]


@dataclass(eq=False)
class Law:
    """A relation among quantities, owned by one part, named as in `why`
    output (OHM, KCL, ...)."""

    name: str
    refs: tuple[Ref, ...]
    solve: Solver
