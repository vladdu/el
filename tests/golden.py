"""Golden comparator: checks EL output against memo-style expected text.

Expected text is parsed with EL's own reader. Each fill line names a quantity
the way the memo prints it, e.g. `(R4 CURRENT ME 1.10638307E-3)` or
`(R3 CURRENT #2 -1.10638304E-3)`. One quantity may be printed under several
names (a resistor's `ME`, `#1` and `#2` currents are one quantity, `#2` with
the opposite sign), so both sides are resolved through the circuit to the
underlying quantity, with its value in canonical sign, before comparing.
Order is ignored; numbers compare with relative tolerance 1e-5.
"""

import math

from el.reader import read_all

REL_TOL = 1e-5
ABS_TOL = 1e-12  # so that the memo's 0.0 matches a float-noise zero


def values_match(expected, actual) -> bool:
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return expected == actual


def _expected_fills(circuit, lines) -> dict:
    expected = {}
    for line in lines:
        match line:
            case [part, kind, label, value]:
                pass
            case [part, kind, value]:
                label = None
            case _:
                raise AssertionError(f"unreadable expected fill {line!r}")
        ref = circuit.ref(part, kind, label)
        assert ref.quantity not in expected, f"expected transcript fills {line!r} twice"
        expected[ref.quantity] = (line, ref.sign * value)
    return expected


def _actual_fills(fills) -> dict:
    actual = {}
    for fill in fills:
        quantity = fill.ref.quantity
        assert quantity not in actual, f"{fill.render()} filled twice"
        actual[quantity] = (fill.render(), fill.ref.sign * fill.value)
    return actual


def assert_fills_match(result, expected_text: str) -> None:
    """Assert `result` (an Analysis) filled exactly the expected quantities,
    in any order, and answered DONE."""
    *lines, done = read_all(expected_text)
    assert done == "DONE", f"expected transcript must end with DONE, got {done!r}"
    expected = _expected_fills(result.circuit, lines)
    actual = _actual_fills(result.fills)
    missing = [line for q, (line, _) in expected.items() if q not in actual]
    extra = [text for q, (text, _) in actual.items() if q not in expected]
    assert not missing and not extra, f"missing fills {missing}, unexpected fills {extra}"
    wrong = [
        (line, actual[q][0])
        for q, (line, want) in expected.items()
        if not values_match(want, actual[q][1])
    ]
    assert not wrong, f"wrong values (expected, actual): {wrong}"
    assert result.render().splitlines()[-1] == "DONE"
