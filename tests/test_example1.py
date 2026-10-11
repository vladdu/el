"""Example 1 of the memo: the four-transistor amplifier (4T-AMP) with its
`(vd r1 r2)` hint. Golden tests against the memo's transcript."""

from golden import assert_fills_match, assert_why_matches

from el import Session
from el.results import Wired


def test_example1_wiring_diagram_with_vd_hint_loads(four_t_amp):
    command, expected = four_t_amp[0]
    [result] = Session().run(command)
    assert isinstance(result, Wired), result.render()
    assert result.render() == expected


def test_example1_analyze_matches_the_memo(four_t_amp):
    session = Session()
    session.run(four_t_amp[0][0])
    command, expected = four_t_amp[1]
    [result] = session.run(command)
    assert_fills_match(result, expected, collapse_transistor_currents=True)


def test_example1_why_r3_current_matches_the_memo(four_t_amp):
    """Our transistor currents are separate quantities tied by the transistor
    law; the memo aliases E and C. So where the memo has
    `(Q2 CURRENT C) <= ((R4 CURRENT #1)) - KCL`, we have
    `(Q2 CURRENT E) <= ((R4 CURRENT #1)) - KCL` plus a TRANSISTOR step to
    `(Q2 CURRENT C)`, which the comparator collapses (spec Testing
    Decisions). Every other line matches as printed: no derivation choices
    differ."""
    session = Session()
    for command, _ in four_t_amp[:2]:
        session.run(command)
    command, expected = four_t_amp[2]
    [result] = session.run(command)
    assert_why_matches(result, expected, collapse_transistor_currents=True)


def test_example1_prints_q1s_zero_currents_as_the_memo_does(four_t_amp):
    """Q1 feeds Q2's Default zero base current, so its currents are exactly
    zero (spec Further Notes). KCL computes them as a negated sum, which is
    -0.0 in floating point; the memo prints 0.0."""
    session = Session()
    session.run(four_t_amp[0][0])
    [result] = session.run(four_t_amp[1][0])
    lines = result.render().splitlines()
    assert lines[0] == "(Q1 CURRENT E 0.0)"
    assert "(Q1 CURRENT C 0.0)" in lines
