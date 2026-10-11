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


# Why trees. Each line justifies one quantity: `((Q) <= ((A) (B) ...) - LAW)`
# or, for a premise, `((Q) GIVEN)` / `((Q) DEFAULT)`; the tree ends in QED.
# Lines are keyed by the underlying quantity (so `(R4 CURRENT #1)` is the same
# line as `(R4 CURRENT ME)`) and compared as law plus antecedent set; order is
# ignored. DEFAULT counts as GIVEN. Formal variables, `(Vn VARVAL)`, have no
# quantity in the circuit; the two sides' variables are paired by their own
# VARVAL lines, and the pairing must be consistent across the whole tree.

PREMISE = "PREMISE"  # GIVEN or DEFAULT


def _why_key(circuit, name):
    match name:
        case [var, "VARVAL"]:
            return ("VARVAL", str(var))
        case [part, kind]:
            return circuit.ref(part, kind).quantity
        case [part, kind, label]:
            return circuit.ref(part, kind, label).quantity
    raise AssertionError(f"unreadable quantity {_text(name)}")


def _why_lines(circuit, text: str, side: str) -> dict:
    """Parse a why tree ending in QED into {key: (line text, law, frozenset of
    antecedent keys)}."""
    *lines, qed = read_all(text)
    assert qed == "QED", f"{side} why tree must end with QED, got {_text(qed)}"
    tree = {}
    for line in lines:
        match line:
            case [name, "<=", list(antecedents), "-", law]:
                ants = frozenset(_why_key(circuit, a) for a in antecedents)
            case [name, "GIVEN" | "DEFAULT"]:
                law, ants = PREMISE, frozenset()
            case _:
                raise AssertionError(f"{side}: unreadable why line {_text(line)}")
        key = _why_key(circuit, name)
        assert key not in tree, f"{side} justifies {_text(name)} twice"
        tree[key] = (_text(line), str(law), ants)
    return tree


def _is_var(key) -> bool:
    return isinstance(key, tuple) and key[0] == "VARVAL"


def _pair_variables(expected: dict, actual: dict) -> dict:
    """Map expected formal variables to actual ones whose VARVAL lines agree
    (same law, same antecedents once already-paired variables are renamed).
    Repeats until no more pairs are found; ambiguous ones stay unpaired."""
    renaming: dict = {}
    while True:
        found = False
        for e in [k for k in expected if _is_var(k) and k not in renaming]:
            _, law, ants = expected[e]
            if any(_is_var(a) and a not in renaming for a in ants):
                continue
            want = frozenset(renaming.get(a, a) for a in ants)
            taken = set(renaming.values())
            candidates = [
                a for a in actual if _is_var(a) and a not in taken and actual[a][1:] == (law, want)
            ]
            if len(candidates) == 1:
                renaming[e] = candidates[0]
                found = True
        if not found:
            return renaming


def assert_why_texts_match(circuit, expected_text: str, actual_text: str) -> None:
    expected = _why_lines(circuit, expected_text, "expected")
    actual = _why_lines(circuit, actual_text, "actual")
    renaming = _pair_variables(expected, actual)

    def rename(key):
        return renaming.get(key, key)

    expected = {
        rename(k): (line, law, frozenset(map(rename, ants)))
        for k, (line, law, ants) in expected.items()
    }
    missing = [line for k, (line, _, _) in expected.items() if k not in actual]
    extra = [line for k, (line, _, _) in actual.items() if k not in expected]
    assert not missing and not extra, f"missing why lines {missing}, unexpected {extra}"
    wrong = [
        f"expected {line}, got {actual[k][0]}"
        for k, (line, law, ants) in expected.items()
        if actual[k][1:] != (law, ants)
    ]
    assert not wrong, "wrong justifications: " + "; ".join(wrong)


def assert_why_matches(result, expected_text: str) -> None:
    """Assert `result` (a Why) printed the expected tree, line for line up to
    order, naming, DEFAULT/GIVEN and formal-variable numbering."""
    assert_why_texts_match(result.circuit, expected_text, result.render())
