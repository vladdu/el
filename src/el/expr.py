"""Linear expressions in formal variables.

An `Expr` is a constant plus a coefficient per formal variable. Laws compute
with values using +, -, unary -, and * or / by a number, so a quantity's
value may be a plain number or an `Expr` and laws need not care which.
Arithmetic that yields no variables gives back a plain float, so an `Expr`
always has at least one variable. Multiplying or dividing by something that
has variables is not linear and raises `NonLinear`; the engine reads that as
"this law cannot deduce this quantity".

Variables are `FormalVariable`s (`el.quantity`): a `name` (printed form,
e.g. `V3`) and a `value` (its VARVAL: None until solved, then a number).
Several variables per expression are supported, so a later
simultaneous-equation solver can consume pending equations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from el.quantity import FormalVariable

# Variable coefficients that cancel to within this fraction of the terms that
# produced them are dropped, so float noise cannot leave a spurious variable
# in a consistency check (which would then "solve" it to garbage).
CANCEL = 1e-12


class NonLinear(ArithmeticError):
    """An operation whose result is not linear in the formal variables."""


class Expr:
    __slots__ = ("const", "coefs")

    def __init__(self, const: float, coefs: dict[FormalVariable, float]) -> None:
        self.const = const
        self.coefs = coefs

    @staticmethod
    def variable(var: FormalVariable) -> Expr:
        return Expr(0.0, {var: 1.0})

    @staticmethod
    def make(const: float, coefs: dict[FormalVariable, float]) -> float | Expr:
        coefs = {v: c for v, c in coefs.items() if c != 0.0}
        return Expr(const, coefs) if coefs else float(const)

    @property
    def variables(self) -> list[FormalVariable]:
        return list(self.coefs)

    # Arithmetic. `other` is a number or an Expr.

    def __add__(self, other: object) -> float | Expr:
        if isinstance(other, Expr):
            coefs = dict(self.coefs)
            for v, c in other.coefs.items():
                a = coefs.get(v, 0.0)
                s = a + c
                coefs[v] = 0.0 if abs(s) <= CANCEL * max(abs(a), abs(c)) else s
            return Expr.make(self.const + other.const, coefs)
        if isinstance(other, int | float):
            return Expr.make(self.const + other, self.coefs)
        return NotImplemented

    __radd__ = __add__

    def __neg__(self) -> Expr:
        return Expr(-self.const, {v: -c for v, c in self.coefs.items()})

    def __sub__(self, other: object) -> float | Expr:
        if isinstance(other, Expr | int | float):
            return self + -other
        return NotImplemented

    def __rsub__(self, other: object) -> float | Expr:
        return -self + other

    def __mul__(self, other: object) -> float | Expr:
        if isinstance(other, Expr):
            raise NonLinear("product of two expressions")
        if isinstance(other, int | float):
            return Expr.make(self.const * other, {v: c * other for v, c in self.coefs.items()})
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other: object) -> float | Expr:
        if isinstance(other, Expr):
            raise NonLinear("division by an expression")
        if isinstance(other, int | float):
            return self * (1.0 / other)
        return NotImplemented

    def __rtruediv__(self, other: object) -> float | Expr:
        raise NonLinear("division by an expression")

    def __eq__(self, other: object) -> bool:
        # A law comparing a value with a number (OHM: `i == 0`) asks whether
        # it is that number, which an expression with variables never is.
        if isinstance(other, Expr):
            return self.const == other.const and self.coefs == other.coefs
        return False

    __hash__ = None  # type: ignore[assignment]

    def substitute(self) -> tuple[float | Expr, list[FormalVariable]]:
        """This expression with every solved variable replaced by its value,
        and the solved variables used, in order. Does not modify self."""
        used = [v for v in self.coefs if v.value is not None]
        if not used:
            return self, []
        const = self.const + sum(self.coefs[v] * v.value for v in used)
        rest = {v: c for v, c in self.coefs.items() if v.value is None}
        return Expr.make(const, rest), used

    def solve(self) -> tuple[FormalVariable, float]:
        """For an expression in exactly one variable, the variable and the
        value that makes the expression zero."""
        [(var, coef)] = self.coefs.items()
        return var, -self.const / coef

    def __repr__(self) -> str:
        terms = " + ".join(f"{c}*{v.name}" for v, c in self.coefs.items())
        return f"Expr({self.const} + {terms})"


def substitute(value: object) -> tuple[object, list[FormalVariable]]:
    """`value` with known formal-variable values substituted in, and the
    variables used. Non-expressions come back unchanged."""
    if isinstance(value, Expr):
        return value.substitute()
    return value, []
