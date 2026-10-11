"""Golden comparator: checks EL output against memo-style expected text.

Both the expected text and EL's rendered output are parsed with EL's own
reader. Each fill line names a quantity the way the memo prints it, e.g.
`(R4 CURRENT ME 1.10638307E-3)` or `(R3 CURRENT #2 -1.10638304E-3)`. One
quantity may be printed under several names (a resistor's `ME`, `#1` and `#2`
currents are one quantity, `#2` with the opposite sign), so both sides are
resolved through the circuit to the underlying quantity, with the value in
canonical sign, before comparing. Order is ignored; numbers compare with
relative tolerance 1e-5.
"""

import math

from el.reader import read_all

REL_TOL = 1e-5
ABS_TOL = 1e-12  # so that the memo's 0.0 matches a float-noise zero


def values_match(expected, actual) -> bool:
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return expected == actual


def _text(datum) -> str:
    if isinstance(datum, list):
        return f"({' '.join(_text(d) for d in datum)})"
    return str(datum)


def _fills(circuit, text: str, side: str) -> dict:
    """Parse a transcript of fill lines ending in DONE into
    {quantity: (line text, value in canonical sign)}."""
    *lines, done = read_all(text)
    assert done == "DONE", f"{side} transcript must end with DONE, got {_text(done)}"
    fills = {}
    for line in lines:
        match line:
            case [part, kind, label, value]:
                pass
            case [part, kind, value]:
                label = None
            case _:
                raise AssertionError(f"{side}: unreadable fill {_text(line)}")
        ref = circuit.ref(part, kind, label)
        assert ref.quantity not in fills, f"{side} fills {_text(line)} twice"
        fills[ref.quantity] = (_text(line), ref.sign * value)
    return fills


def assert_fills_match(result, expected_text: str) -> None:
    """Assert `result` (an Analysis) printed exactly the expected fills, in
    any order, and answered DONE."""
    expected = _fills(result.circuit, expected_text, "expected")
    actual = _fills(result.circuit, result.render(), "actual")
    missing = [line for q, (line, _) in expected.items() if q not in actual]
    extra = [line for q, (line, _) in actual.items() if q not in expected]
    assert not missing and not extra, f"missing fills {missing}, unexpected fills {extra}"
    wrong = [
        f"expected {line}, got {actual[q][0]}"
        for q, (line, want) in expected.items()
        if not values_match(want, actual[q][1])
    ]
    assert not wrong, "wrong values: " + "; ".join(wrong)
