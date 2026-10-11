from pathlib import Path

import pytest

MEMO = Path(__file__).parent / "memo"


def transcript(name: str) -> list[tuple[str, str]]:
    """A memo transcript as (input text, expected output text) pairs.

    Fixture files hold the memo's blocks verbatim, separated by blank lines,
    alternating user input and EL output.
    """
    text = (MEMO / name).read_text()
    blocks = [b.strip("\n") for b in text.split("\n\n") if b.strip()]
    assert len(blocks) % 2 == 0, f"{name}: odd number of blocks"
    return list(zip(blocks[::2], blocks[1::2], strict=True))


@pytest.fixture
def ladder() -> list[tuple[str, str]]:
    return transcript("example3_ladder.el")
