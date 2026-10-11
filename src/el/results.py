"""Structured results returned by `Session`.

Every result renders to exactly the text the REPL prints, so rendering lives
here and nowhere else.
"""

from dataclasses import dataclass, field

from el.circuit import Circuit


class Result:
    def render(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class Wired(Result):
    """A wiring diagram loaded successfully."""

    circuit: Circuit

    def render(self) -> str:
        return "DONE"


@dataclass(frozen=True)
class Analysis(Result):
    """The outcome of `analyze`: every quantity filled, in fill order."""

    circuit: Circuit
    fills: list = field(default_factory=list)

    def render(self) -> str:
        return "\n".join([*(fill.render() for fill in self.fills), "DONE"])


@dataclass(frozen=True)
class Error(Result):
    """A command that could not be carried out."""

    message: str

    def render(self) -> str:
        return f";ERROR: {self.message}"
