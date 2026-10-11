import re
from pathlib import Path

import pytest

MEMO = Path(__file__).parent / "memo"
COMMAND = re.compile(r"\((wire|analyze|why|change|what)\b", re.IGNORECASE)


def transcript(name: str) -> list[tuple[str, str]]:
    """A memo transcript as (input text, expected output text) pairs.

    Fixture files hold the memo's blocks verbatim, separated by blank lines.
    A block that starts with a command form (`(wire ...`, `(what ...`) is
    input; the blocks after it, up to the next input, are its output, joined
    back with their blank lines (`what` prints a blank line before its answer).
    """
    text = (MEMO / name).read_text()
    blocks = [b.strip("\n") for b in text.split("\n\n") if b.strip()]
    pairs: list[tuple[str, list[str]]] = []
    for block in blocks:
        if COMMAND.match(block):
            pairs.append((block, []))
        else:
            assert pairs, f"{name}: output before any command"
            pairs[-1][1].append(block)
    assert all(out for _, out in pairs), f"{name}: command without output"
    return [(cmd, "\n\n".join(out)) for cmd, out in pairs]


@pytest.fixture
def ladder() -> list[tuple[str, str]]:
    return transcript("example3_ladder.el")
