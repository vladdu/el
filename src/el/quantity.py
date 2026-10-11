"""Quantities, the names they are read and written under, and justifications.

A `Quantity` is one value cell of one part (NODE2's voltage, R4's current).
A `Ref` is a signed name for a quantity: a resistor owns a single current
quantity, named `ME`, which is also its `#1` current, and its `#2` current is
the same quantity with the opposite sign. Laws read and fill quantities
through refs, and fills and justifications remember which ref was used, so
output can name a quantity the way the law that touched it saw it, as the
memo does (`(R4 CURRENT ME ...)` from OHM, `(R3 CURRENT #2 ...)` from KCL).
"""

from dataclasses import dataclass, field

# A quantity's value. Numbers for now; linear expressions in formal variables
# later (ticket 05). Laws only use +, -, unary -, and * or / by numbers on
# values, so a value type supporting those plugs in unchanged.
type Value = float

GIVEN = "GIVEN"
DEFAULT = "DEFAULT"


@dataclass(frozen=True)
class Justification:
    """How a quantity was filled: by `law` from `antecedents`, or as a
    premise (law GIVEN or DEFAULT, no antecedents)."""

    law: str
    antecedents: tuple[Ref, ...] = ()

    @property
    def is_premise(self) -> bool:
        return not self.antecedents and self.law in (GIVEN, DEFAULT)


@dataclass(eq=False)
class Quantity:
    """One value cell of one part, named canonically `(part kind [label])`.

    Identity matters: two quantities are equal only if they are the same
    object. `consequences` lists the quantities whose justifications read this
    one, for retraction."""

    part: str
    kind: str
    label: str | None = None
    value: Value | None = None
    justification: Justification | None = None
    consequences: list[Quantity] = field(default_factory=list)

    @property
    def filled(self) -> bool:
        return self.value is not None

    def __repr__(self) -> str:
        return f"Quantity({self.part} {self.kind}{f' {self.label}' if self.label else ''})"


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
