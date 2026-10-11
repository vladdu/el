"""Golden comparator: checks EL output against memo-style expected text.

Both the expected text and EL's rendered output are parsed with EL's own
reader. Each fill line names a quantity the way the memo prints it, e.g.
`(R4 CURRENT ME 1.10638307E-3)` or `(R3 CURRENT #2 -1.10638304E-3)`. One
quantity may be printed under several names (a resistor's `ME`, `#1` and `#2`
currents are one quantity, `#2` with the opposite sign), so both sides are
resolved through the circuit to the underlying quantity, with the value in
canonical sign, before comparing. Order is ignored; numbers compare with
relative tolerance 1e-5.

Values may be expressions in formal variables, in the memo's form `V3`,
`(&* -2.0 V3)`, `(&+ 1.0 (&* -4.0 V3))`; they compare coefficient by
coefficient. A formal variable's solution prints as `(V3 VARVAL 0.125)`.
Formal-variable names on the two sides are equal up to a consistent renaming
(the memo's numbering is not reproduced).
"""

import itertools
import math

from el.reader import read_all

REL_TOL = 1e-5
ABS_TOL = 1e-12  # so that the memo's 0.0 matches a float-noise zero

# A parsed value: a number, a non-numeric symbol (e.g. ACTIVE), or a linear
# expression as (constant, {variable name: coefficient}).


def _linear(datum):
    """`datum` as (constant, {var: coef}), or None if it isn't numeric."""
    match datum:
        case int() | float():
            return float(datum), {}
        case str() if _is_var(datum):
            return 0.0, {str(datum): 1.0}
        case ["&*", int() | float() as c, str() as var] if _is_var(var):
            return 0.0, {str(var): float(c)}
        case ["&+", *terms]:
            const, coefs = 0.0, {}
            for term in terms:
                parsed = _linear(term)
                if parsed is None:
                    return None
                const += parsed[0]
                for var, c in parsed[1].items():
                    coefs[var] = coefs.get(var, 0.0) + c
            return const, coefs
    return None


def _is_var(datum) -> bool:
    return isinstance(datum, str) and datum[:1] == "V" and datum[1:].isdigit()


def _scale(value, sign):
    if isinstance(value, tuple):
        const, coefs = value
        return sign * const, {v: sign * c for v, c in coefs.items()}
    return value


def _rename(value, names):
    if isinstance(value, tuple):
        const, coefs = value
        return const, {names.get(v, v): c for v, c in coefs.items()}
    return value


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def values_match(expected, actual) -> bool:
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return _close(expected, actual)
    if isinstance(expected, tuple) and isinstance(actual, tuple):
        (c1, v1), (c2, v2) = expected, actual
        if not _close(c1, c2):
            return False
        return all(_close(v1.get(v, 0.0), v2.get(v, 0.0)) for v in v1.keys() | v2.keys())
    return expected == actual


def _text(datum) -> str:
    if isinstance(datum, list):
        return f"({' '.join(_text(d) for d in datum)})"
    return str(datum)


def _value(datum):
    parsed = _linear(datum)
    return datum if parsed is None else parsed


def _variables(value) -> set[str]:
    return set(value[1]) if isinstance(value, tuple) else set()


def _parse(circuit, text: str, side: str):
    """Parse a transcript of fill lines followed by a final answer into
    ({key: (line text, value in canonical sign)}, answer, variable names).
    A key is the filled quantity, or ("VARVAL", name) for a VARVAL line."""
    *lines, answer = read_all(text)
    fills = {}
    names: set[str] = set()
    for line in lines:
        match line:
            case [var, "VARVAL", value] if _is_var(var):
                key, sign = ("VARVAL", str(var)), 1
                names.add(str(var))
            case [part, kind, label, value]:
                ref = circuit.ref(part, kind, label)
                key, sign = ref.quantity, ref.sign
            case [part, kind, value]:
                ref = circuit.ref(part, kind, None)
                key, sign = ref.quantity, ref.sign
            case _:
                raise AssertionError(f"{side}: unreadable fill {_text(line)}")
        assert key not in fills, f"{side} fills {_text(line)} twice"
        parsed = _scale(_value(value), sign)
        names |= _variables(parsed)
        fills[key] = (_text(line), parsed)
    answer = _value(answer)
    return fills, answer, names | _variables(answer)


def _differences(expected, actual, names) -> list[str]:
    """Mismatches between parsed transcripts, with expected variable names
    renamed by `names`."""

    def key(k):
        return ("VARVAL", names.get(k[1], k[1])) if isinstance(k, tuple) else k

    want = {key(k): (line, _rename(v, names)) for k, (line, v) in expected[0].items()}
    got = actual[0]
    missing = [line for k, (line, _) in want.items() if k not in got]
    extra = [line for k, (line, _) in got.items() if k not in want]
    if missing or extra:
        return [f"missing fills {missing}, unexpected fills {extra}"]
    diffs = [
        f"expected {line}, got {got[k][0]}"
        for k, (line, value) in want.items()
        if not values_match(value, got[k][1])
    ]
    expected_answer = _rename(expected[1], names)
    if not values_match(expected_answer, actual[1]):
        diffs.append(f"expected answer {expected[1]}, got {actual[1]}")
    return diffs


def _assert_match(expected, actual) -> None:
    """Assert the parsed transcripts agree under some consistent renaming
    of the expected side's formal variables to the actual side's."""
    want_names, got_names = sorted(expected[2]), sorted(actual[2])
    assert len(want_names) == len(got_names), (
        f"expected formal variables {want_names}, got {got_names}"
    )
    first = None
    for perm in itertools.permutations(got_names):
        diffs = _differences(expected, actual, dict(zip(want_names, perm, strict=True)))
        if not diffs:
            return
        first = first or diffs
    raise AssertionError("; ".join(first or []))


def assert_fills_match(result, expected_text: str) -> None:
    """Assert `result` (an Analysis) printed exactly the expected fills, in
    any order, and answered DONE."""
    expected = _parse(result.circuit, expected_text, "expected")
    actual = _parse(result.circuit, result.render(), "actual")
    assert expected[1] == "DONE", f"expected transcript must end with DONE, got {expected[1]}"
    _assert_match(expected, actual)


def assert_answer_matches(result, expected_text: str) -> None:
    """Assert `result` (a `what` Answer) printed the expected fills, in any
    order, and the expected answer."""
    expected = _parse(result.circuit, expected_text, "expected")
    actual = _parse(result.circuit, result.render(), "actual")
    _assert_match(expected, actual)
