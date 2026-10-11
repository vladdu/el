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

The memo aliases a transistor's emitter and collector currents; EL keeps
them separate, tied by the transistor current law (spec Implementation
Decisions). Memo goldens pass `collapse_transistor_currents=True`: a
transistor's `C` current is then read as its `E` current with the opposite
sign (exact while the base current is the Default 0). A side that fills
both counts once, provided they agree; in a why tree the TRANSISTOR step
between them is dropped, as is any line no longer reachable from the root.
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
        case str() if _is_var_name(datum):
            return 0.0, {str(datum): 1.0}
        case ["&*", int() | float() as c, str() as var] if _is_var_name(var):
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


def _is_var_name(datum) -> bool:
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


TRANSISTOR = "TRANSISTOR"


def _resolve(circuit, name: list, collapse: bool):
    """(quantity, sign) named by `(part kind [label])`; with `collapse`, a
    transistor's C current is its E current with the opposite sign."""
    ref = circuit.ref(*name)
    match name:
        case [part, "CURRENT", "E" | "C" as label] if collapse:
            emitter = circuit.ref(part, "CURRENT", "E")
            return emitter.quantity, ref.sign if label == "E" else -ref.sign
    return ref.quantity, ref.sign


def _parse(circuit, text: str, side: str, collapse: bool = False):
    """Parse a transcript of fill lines followed by a final answer into
    ({key: (line text, value in canonical sign)}, answer, variable names).
    A key is the filled quantity, or ("VARVAL", name) for a VARVAL line."""
    *lines, answer = read_all(text)
    fills = {}
    names: set[str] = set()
    for line in lines:
        match line:
            case [var, "VARVAL", value] if _is_var_name(var):
                key, sign = ("VARVAL", str(var)), 1
                names.add(str(var))
            case [part, kind, label, value]:
                key, sign = _resolve(circuit, [part, kind, label], collapse)
            case [part, kind, value]:
                key, sign = _resolve(circuit, [part, kind, None], collapse)
            case _:
                raise AssertionError(f"{side}: unreadable fill {_text(line)}")
        parsed = _scale(_value(value), sign)
        if collapse and key in fills:
            first = fills[key][0]
            assert values_match(fills[key][1], parsed), (
                f"{side}: aliased fills {first} and {_text(line)} disagree"
            )
            continue
        assert key not in fills, f"{side} fills {_text(line)} twice"
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


def assert_fills_match(
    result, expected_text: str, *, collapse_transistor_currents: bool = False
) -> None:
    """Assert `result` (an Analysis) printed exactly the expected fills, in
    any order, and answered DONE."""
    collapse = collapse_transistor_currents
    expected = _parse(result.circuit, expected_text, "expected", collapse)
    actual = _parse(result.circuit, result.render(), "actual", collapse)
    assert expected[1] == "DONE", f"expected transcript must end with DONE, got {expected[1]}"
    _assert_match(expected, actual)


def assert_answer_matches(result, expected_text: str) -> None:
    """Assert `result` (a `what` Answer) printed the expected fills, in any
    order, and the expected answer."""
    expected = _parse(result.circuit, expected_text, "expected")
    actual = _parse(result.circuit, result.render(), "actual")
    _assert_match(expected, actual)


# Why trees. Each line justifies one quantity: `((Q) <= ((A) (B) ...) - LAW)`
# or, for a premise, `((Q) GIVEN)` / `((Q) DEFAULT)`, or for a supposition
# `((Q) WHAT)`; the tree ends in QED.
# Lines are keyed by the underlying quantity (so `(R4 CURRENT #1)` is the same
# line as `(R4 CURRENT ME)`) and compared as law plus antecedent set; order is
# ignored. DEFAULT counts as GIVEN. Formal variables, `(Vn VARVAL)`, have no
# quantity in the circuit; the two sides' variables are paired by their own
# VARVAL lines, and the pairing must be consistent across the whole tree.

PREMISE = "PREMISE"  # GIVEN or DEFAULT


def _why_key(circuit, name, collapse: bool = False):
    match name:
        case [var, "VARVAL"]:
            return ("VARVAL", str(var))
        case [_, _] | [_, _, _]:
            return _resolve(circuit, name, collapse)[0]
    raise AssertionError(f"unreadable quantity {_text(name)}")


def _why_lines(circuit, text: str, side: str, collapse: bool = False) -> dict:
    """Parse a why tree ending in QED into {key: (line text, law, frozenset of
    antecedent keys)}."""
    *lines, qed = read_all(text)
    assert qed == "QED", f"{side} why tree must end with QED, got {_text(qed)}"
    tree = {}
    for line in lines:
        match line:
            case [name, "<=", list(antecedents), "-", law]:
                ants = frozenset(_why_key(circuit, a, collapse) for a in antecedents)
            case [name, "GIVEN" | "DEFAULT"]:
                law, ants = PREMISE, frozenset()
            case [name, "WHAT" as law]:
                ants = frozenset()
            case _:
                raise AssertionError(f"{side}: unreadable why line {_text(line)}")
        key = _why_key(circuit, name, collapse)
        entry = (_text(line), str(law), ants - {key})
        if collapse and key in tree and TRANSISTOR in (law, tree[key][1]):
            if law != TRANSISTOR:
                tree[key] = entry
            continue
        assert key not in tree, f"{side} justifies {_text(name)} twice"
        tree[key] = entry
    return _reachable(tree, _why_key(circuit, lines[0][0], collapse)) if collapse else tree


def _reachable(tree: dict, root) -> dict:
    """The lines of `tree` reachable from `root` through antecedents."""
    keep, todo = set(), [root]
    while todo:
        key = todo.pop()
        if key in keep or key not in tree:
            continue
        keep.add(key)
        todo.extend(tree[key][2])
    return {k: v for k, v in tree.items() if k in keep}


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


def assert_why_texts_match(
    circuit, expected_text: str, actual_text: str, collapse: bool = False
) -> None:
    expected = _why_lines(circuit, expected_text, "expected", collapse)
    actual = _why_lines(circuit, actual_text, "actual", collapse)
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


def assert_why_matches(
    result, expected_text: str, *, collapse_transistor_currents: bool = False
) -> None:
    """Assert `result` (a Why) printed the expected tree, line for line up to
    order, naming, DEFAULT/GIVEN and formal-variable numbering."""
    assert_why_texts_match(
        result.circuit, expected_text, result.render(), collapse_transistor_currents
    )
