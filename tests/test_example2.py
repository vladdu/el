"""Example 2 of the memo: the GR-58 amplifier's bias circuit with its
`(vd r130 r131)` and `(cp q107 q108)` hints. Golden tests against the memo's
transcript. The memo's prose swaps NODE3 and NODE4; the transcript is right
(NODE4, Q107's base, is OUTPUT + V10), and the tests follow it."""

from golden import assert_fills_match, assert_why_matches

from el import Session
from el.results import Wired


def test_example2_wiring_diagram_with_cp_hint_loads(gr_58):
    command, expected = gr_58[0]
    [result] = Session().run(command)
    assert isinstance(result, Wired), result.render()
    assert result.render() == expected


def test_example2_analyze_matches_the_memo(gr_58):
    session = Session()
    session.run(gr_58[0][0])
    command, expected = gr_58[1]
    [result] = session.run(command)
    assert_fills_match(result, expected, collapse_transistor_currents=True)


def test_example2_why_output_voltage_matches_the_memo(gr_58):
    """As in Example 1, only the memo's aliasing of transistor E and C
    currents differs (`(Q105 CURRENT E) <= ((Q106 CURRENT B)
    (R132 CURRENT #1)) - KCL` is our KCL step to Q105's C current plus a
    TRANSISTOR step), which the comparator collapses. No derivation choices
    differ: OUTPUT's tree does not reach the complementary pair."""
    session = Session()
    for command, _ in gr_58[:2]:
        session.run(command)
    command, expected = gr_58[2]
    [result] = session.run(command)
    assert_why_matches(result, expected, collapse_transistor_currents=True)
