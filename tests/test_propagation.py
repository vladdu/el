import pytest
from golden import assert_fills_match

from el import Session
from el.results import Analysis

# Three resistors between fixed nodes, then a chain R4-R5 hanging off MID that
# ends at an open node. R3 is wired backwards (its #1 is at GND), so its ME
# current is negative. Every quantity follows by one-step deductions:
#   R1: (12 - 8) / 1000 = 4 mA; R2: (8 - 0) / 2000 = 4 mA; R3: (0 - 8) / 4000 = -2 mA
#   NODE2 has only R5's #1, so KCL makes R5's current 0; KCL at NODE1 passes
#   that on to R4; OHM then carries MID's 8 V to NODE1 and NODE2.
CHAIN = """
(wire chain
  (node (top 12) (mid 8) (gnd 0))
  (resistor (r1 1000) (r2 2000) (r3 4000) (r4 500) (r5 250))
  (connect
    (top (#1 r1))
    (mid (#2 r1) (#1 r2) (#2 r3) (#1 r4))
    (gnd (#2 r2) (#1 r3))
    ((#2 r4) (#2 r5))            ;NODE1
    ((#1 r5))))                  ;NODE2
"""

CHAIN_ANALYSIS = """
(R1 CURRENT ME 4.0E-3)
(R2 CURRENT ME 4.0E-3)
(R3 CURRENT ME -2.0E-3)
(R5 CURRENT #1 0.0)
(R4 CURRENT #2 0.0)
(NODE1 VOLTAGE 8.0)
(NODE2 VOLTAGE 8.0)
DONE
"""


def analyze(wire_text, name):
    session = Session()
    session.run(wire_text)
    [result] = session.run(f"(analyze '{name})")
    assert isinstance(result, Analysis), result.render()
    return result


def test_ohm_fills_the_current_through_a_resistor_between_fixed_nodes():
    result = analyze(
        """(wire one (node (top 12) (gnd 0)) (resistor (r1 3000))
             (connect (top (#1 r1)) (gnd (#2 r1))))""",
        "one",
    )
    assert result.render() == "(R1 CURRENT ME 4.0E-3)\nDONE"


def analyze_chain():
    session = Session()
    session.run(CHAIN)
    [result] = session.run("(analyze 'chain)")
    assert isinstance(result, Analysis), result.render()
    return result


def test_resistor_chain_between_fixed_nodes_analyzes_fully():
    assert_fills_match(analyze_chain(), CHAIN_ANALYSIS)


# The golden comparator itself: it must accept the memo's way of writing the
# same result and reject a wrong one, or golden tests prove nothing.
CHAIN_ANALYSIS_REWRITTEN = """
(NODE2 VOLTAGE 8.00004)
(R3 CURRENT #2 2.0E-3)
(R4 CURRENT ME 0.0)
(R1 CURRENT #1 4.0E-3)
(NODE1 VOLTAGE 8.0)
(R2 CURRENT #2 -4.0E-3)
(R5 CURRENT ME 0.0)
DONE
"""


def test_golden_comparator_ignores_order_and_naming_and_tolerates_rounding():
    assert_fills_match(analyze_chain(), CHAIN_ANALYSIS_REWRITTEN)


def test_golden_comparator_rejects_a_wrong_value():
    wrong = CHAIN_ANALYSIS.replace("(NODE1 VOLTAGE 8.0)", "(NODE1 VOLTAGE 8.001)")
    with pytest.raises(AssertionError, match="NODE1 VOLTAGE"):
        assert_fills_match(analyze_chain(), wrong)


def test_golden_comparator_rejects_a_wrong_sign():
    wrong = CHAIN_ANALYSIS.replace("(R3 CURRENT ME -2.0E-3)", "(R3 CURRENT #2 -2.0E-3)")
    with pytest.raises(AssertionError, match="R3 CURRENT"):
        assert_fills_match(analyze_chain(), wrong)


def test_golden_comparator_rejects_missing_and_unexpected_fills():
    missing = CHAIN_ANALYSIS.replace("(NODE2 VOLTAGE 8.0)\n", "")
    with pytest.raises(AssertionError, match="NODE2 VOLTAGE"):
        assert_fills_match(analyze_chain(), missing)
    extra = CHAIN_ANALYSIS.replace("DONE", "(TOP VOLTAGE 12)\nDONE")
    with pytest.raises(AssertionError, match="TOP VOLTAGE"):
        assert_fills_match(analyze_chain(), extra)


def test_values_print_plain_from_a_tenth_up_and_in_exponent_form_below():
    result = analyze(
        """(wire two (node (top 2.5) (gnd 0))
             (resistor (r1 1) (r2 1000) (r3 20))
             (connect (top (#1 r1) (#1 r2) (#2 r3)) (gnd (#2 r1) (#2 r2) (#1 r3))))""",
        "two",
    )
    assert sorted(result.render().splitlines()) == [
        "(R1 CURRENT ME 2.5)",
        "(R2 CURRENT ME 2.5E-3)",
        "(R3 CURRENT ME -0.125)",
        "DONE",
    ]
