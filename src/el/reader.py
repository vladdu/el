"""S-expression reader for the memo's command syntax.

Symbols are case-folded to upper case (the memo prints them that way), `;`
starts a comment running to end of line, `'x` reads as `(QUOTE X)`, and
numbers are read in the memo's forms (`.6`, `-.6`, `370000`, `2.7`, `0.0`,
`1.10638307E-3`). Integers read as `int`, everything else numeric as `float`.
"""

import re
from collections.abc import Iterator

type Datum = Symbol | int | float | list[Datum]


class Symbol(str):
    """An upper-cased Lisp symbol. Compares equal to its plain-string name."""

    __slots__ = ()

    def __new__(cls, name: str) -> Symbol:
        return super().__new__(cls, name.upper())

    def __repr__(self) -> str:
        return f"Symbol({str(self)!r})"


QUOTE = Symbol("QUOTE")


class ReadError(Exception):
    """Malformed input text."""


class IncompleteInput(ReadError):
    """Input ends inside an unfinished form; more text may complete it."""


_TOKEN = re.compile(r"""\s+|;[^\n]*|(?P<tok>[()']|[^\s()';]+)""")
_INT = re.compile(r"[+-]?\d+")
_FLOAT = re.compile(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?")


def _tokens(text: str) -> Iterator[str]:
    for m in _TOKEN.finditer(text):
        if m["tok"] is not None:
            yield m["tok"]


def _atom(token: str) -> Datum:
    if _INT.fullmatch(token):
        return int(token)
    if _FLOAT.fullmatch(token):
        return float(token)
    return Symbol(token)


def read_all(text: str) -> list[Datum]:
    """Read every top-level form in `text`."""
    stack: list[list[Datum]] = [[]]
    quotes: list[int] = [0]  # pending `'` count per open list

    def emit(datum: Datum) -> None:
        while quotes[-1]:
            quotes[-1] -= 1
            datum = [QUOTE, datum]
        stack[-1].append(datum)

    for token in _tokens(text):
        if token == "(":
            stack.append([])
            quotes.append(0)
        elif token == ")":
            if len(stack) == 1:
                raise ReadError("unexpected ')'")
            if quotes[-1]:
                raise ReadError("quote before ')'")
            quotes.pop()
            emit(stack.pop())
        elif token == "'":
            quotes[-1] += 1
        else:
            emit(_atom(token))
    if len(stack) > 1 or quotes[-1]:
        raise IncompleteInput("input ends inside a form")
    return stack[0]
