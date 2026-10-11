import pytest
from golden import assert_why_matches, assert_why_texts_match
from test_propagation import CHAIN

from el import Session


def chain_session():
    session = Session()
    session.run(CHAIN)
    session.run("(analyze 'chain)")
    return session


def why(session, args):
    [result] = session.run(f"(why {args})")
    return result


# Worked by hand from the chain's deductions (see test_propagation.CHAIN):
# KCL at NODE2 (only R5's #1) gives R5's current from nothing; KCL at NODE1
# passes it to R4; R4's OHM carries MID's voltage to NODE1, R5's OHM to NODE2.
# Each quantity appears once, named as its first reader named it; R5's #2
# current under R4's line is the R5 current already explained.
NODE2_WHY = """\
((NODE2 VOLTAGE) <= ((NODE1 VOLTAGE) (R5 RESISTANCE) (R5 CURRENT ME)) - OHM)
((NODE1 VOLTAGE) <= ((MID VOLTAGE) (R4 RESISTANCE) (R4 CURRENT ME)) - OHM)
((R5 RESISTANCE) GIVEN)
((R5 CURRENT ME) <= () - KCL)
((MID VOLTAGE) GIVEN)
((R4 RESISTANCE) GIVEN)
((R4 CURRENT ME) <= ((R5 CURRENT #2)) - KCL)
QED"""


def test_why_prints_the_justification_tree_of_a_deduced_quantity():
    assert why(chain_session(), "node2 voltage").render() == NODE2_WHY


def test_why_on_a_premise_is_a_one_line_tree():
    assert why(chain_session(), "r1 resistance").render() == "((R1 RESISTANCE) GIVEN)\nQED"


def test_why_on_an_unfilled_quantity_says_it_has_no_value():
    session = Session()
    session.run("""(wire divider (node (top 12) (gnd 0)) (resistor (r1 1000) (r2 1000))
                     (connect (top (#1 r1)) ((#2 r1) (#1 r2)) (gnd (#2 r2))))""")
    # A divider without a hint: no one-step deduction, nothing is filled.
    session.run("(analyze 'divider)")
    assert why(session, "r1 current").render() == "(R1 CURRENT) has no value"


def test_why_acts_on_the_most_recently_analyzed_circuit():
    session = chain_session()
    session.run(
        "(wire other (node (top 5) (gnd 0)) (resistor (r1 5))"
        " (connect (top (#1 r1)) (gnd (#2 r1))))"
    )
    # `other` is wired but not analyzed: `why` still answers about `chain`.
    assert why(session, "r1 current #1").render() == (
        "((R1 CURRENT #1) <= ((TOP VOLTAGE) (MID VOLTAGE) (R1 RESISTANCE)) - OHM)\n"
        "((TOP VOLTAGE) GIVEN)\n((MID VOLTAGE) GIVEN)\n((R1 RESISTANCE) GIVEN)\nQED"
    )
    session.run("(analyze 'other)")
    assert (
        why(session, "r1 current")
        .render()
        .startswith("((R1 CURRENT) <= ((TOP VOLTAGE) (GND VOLTAGE) (R1 RESISTANCE)) - OHM)")
    )


def test_why_before_any_analysis_or_on_an_unknown_quantity_is_an_error():
    session = Session()
    session.run(CHAIN)
    assert why(session, "r1 current").render().startswith(";ERROR:")
    session.run("(analyze 'chain)")
    assert why(session, "r9 current").render().startswith(";ERROR:")
    assert why(session, "r1 voltage").render().startswith(";ERROR:")


# The why-tree comparator: same law and same antecedent set per quantity, in
# any order, under any name for the same quantity, DEFAULT equal to GIVEN.
NODE2_WHY_REWRITTEN = """
((R4 CURRENT #2) <= ((R5 CURRENT #1)) - KCL)
((NODE2 VOLTAGE) <= ((R5 CURRENT #1) (NODE1 VOLTAGE)
                     (R5 RESISTANCE)) - OHM)
((MID VOLTAGE) DEFAULT)
((R4 RESISTANCE) GIVEN)
((R5 CURRENT #2) <= () - KCL)
((NODE1 VOLTAGE) <= ((R4 CURRENT ME) (MID VOLTAGE) (R4 RESISTANCE)) - OHM)
((R5 RESISTANCE) GIVEN)
          QED
"""


def test_why_comparator_ignores_order_naming_and_premise_kind():
    assert_why_matches(why(chain_session(), "node2 voltage"), NODE2_WHY_REWRITTEN)


def test_why_comparator_rejects_a_wrong_law():
    wrong = NODE2_WHY.replace("(R4 CURRENT ME)) - OHM)", "(R4 CURRENT ME)) - KVL)")
    with pytest.raises(AssertionError, match="NODE1 VOLTAGE"):
        assert_why_matches(why(chain_session(), "node2 voltage"), wrong)


def test_why_comparator_rejects_a_wrong_antecedent_set():
    wrong = NODE2_WHY.replace("((MID VOLTAGE) (R4 RESISTANCE)", "((MID VOLTAGE)")
    with pytest.raises(AssertionError, match="NODE1 VOLTAGE"):
        assert_why_matches(why(chain_session(), "node2 voltage"), wrong)


def test_why_comparator_rejects_missing_and_unexpected_lines():
    missing = NODE2_WHY.replace("((R4 RESISTANCE) GIVEN)\n", "")
    with pytest.raises(AssertionError, match="R4 RESISTANCE"):
        assert_why_matches(why(chain_session(), "node2 voltage"), missing)
    extra = NODE2_WHY.replace("QED", "((TOP VOLTAGE) GIVEN)\nQED")
    with pytest.raises(AssertionError, match="TOP VOLTAGE"):
        assert_why_matches(why(chain_session(), "node2 voltage"), extra)


# Formal variables (ticket 05) appear as `(Vn VARVAL)` lines and antecedents;
# their numbering is not the memo's, so trees match up to consistent renaming.
# Checked on hand-written trees over the chain circuit's quantities.
WITH_VARS = """
((NODE1 VOLTAGE) <= ((MID VOLTAGE) (V7 VARVAL)) - BE)
((NODE2 VOLTAGE) <= ((V8 VARVAL)) - BE)
((V7 VARVAL) <= ((R4 RESISTANCE)) - OHM)
((V8 VARVAL) <= ((R5 RESISTANCE) (V7 VARVAL)) - OHM)
((MID VOLTAGE) GIVEN)
((R4 RESISTANCE) GIVEN)
((R5 RESISTANCE) GIVEN)
QED
"""


def test_why_comparator_renames_formal_variables_consistently():
    circuit = chain_session().current
    renamed = WITH_VARS.replace("V7", "V1").replace("V8", "V2")
    assert_why_texts_match(circuit, WITH_VARS, renamed)
    swapped = WITH_VARS.replace("(V7 VARVAL)) - BE", "(V8 VARVAL)) - BE")
    swapped = swapped.replace("((V8 VARVAL)) - BE", "((V7 VARVAL)) - BE")
    with pytest.raises(AssertionError, match="NODE"):
        assert_why_texts_match(circuit, WITH_VARS, swapped)
