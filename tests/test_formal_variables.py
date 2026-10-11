from golden import assert_answer_matches, assert_why_matches

from el import Session
from el.results import Error


def ladder_session(ladder) -> Session:
    session = Session()
    for command, _ in ladder[:2]:
        session.run(command)
    return session


def test_what_on_the_ladder_solves_the_output_voltage_by_wishful_thinking(ladder):
    command, expected = ladder[2]
    [result] = ladder_session(ladder).run(command)
    assert_answer_matches(result, expected)


def test_what_prints_expressions_in_memo_form_then_a_blank_line_and_the_answer(ladder):
    [result] = ladder_session(ladder).run("(what output voltage)")
    assert result.render() == "\n".join(
        [
            "(OUTPUT VOLTAGE V1)",
            "(R6 CURRENT ME V1)",
            "(R5 CURRENT #2 (&* -1.0 V1))",
            "(NODE2 VOLTAGE (&* 2.0 V1))",
            "(R4 CURRENT ME V1)",
            "(R3 CURRENT #2 (&* -2.0 V1))",
            "(NODE1 VOLTAGE (&* 4.0 V1))",
            "(R1 CURRENT ME (&+ 1.0 (&* -4.0 V1)))",
            "(R2 CURRENT #1 (&+ 1.0 (&* -6.0 V1)))",
            "(V1 VARVAL 0.125)",
            "",
            "0.125",
        ]
    )


def test_what_on_a_filled_quantity_answers_its_value_with_variables_substituted(ladder):
    session = ladder_session(ladder)
    session.run("(what output voltage)")
    # R2's current was filled as 1 - 6 V1 with V1 = 0.125.
    [result] = session.run("(what r2 current #1)")
    assert result.render() == "0.25"
    [result] = session.run("(what r1 current)")
    assert result.render() == "0.5"


def test_formal_variables_are_numbered_per_session(ladder):
    session = ladder_session(ladder)
    session.run("(what output voltage)")
    session.run(ladder[0][0])
    session.run("(analyze 'ladder)")
    [result] = session.run("(what node1 voltage)")
    lines = result.render().splitlines()
    assert lines[0] == "(NODE1 VOLTAGE V2)"
    assert lines[-1] == "0.5"


# A divider TOP-R1-NODE1-R2-GND with R3 hanging off NODE1 to an open node OUT.
# `analyze` only finds R3's current (0, by KCL at OUT). `what node1 voltage`
# introduces V1 at NODE1; R1's current follows, KCL at NODE1 passes it to R2,
# and R2's OHM, now fully filled, solves V1 = 5. Only then does R3 run: it
# reads NODE1's stored value V1 with V1 known, so OUT gets the number 5.0, and
# (V1 VARVAL) is among its antecedents.
TAIL = """
(wire tail
  (node (top 10) (gnd 0) out)
  (resistor (r1 1000) (r2 1000) (r3 500))
  (connect (top (#1 r1)) (gnd (#2 r2))
           ((#2 r1) (#1 r2) (#1 r3))      ;NODE1
           (out (#2 r3))))
"""


def test_a_law_reading_a_solved_variable_substitutes_it_and_cites_its_varval():
    session = Session()
    session.run(TAIL)
    session.run("(analyze 'tail)")
    [result] = session.run("(what node1 voltage)")
    assert result.render() == "\n".join(
        [
            "(NODE1 VOLTAGE V1)",
            "(R1 CURRENT ME (&+ 1.0E-2 (&* -1.0E-3 V1)))",
            "(R2 CURRENT #1 (&+ 1.0E-2 (&* -1.0E-3 V1)))",
            "(V1 VARVAL 5.0)",
            "(OUT VOLTAGE 5.0)",
            "",
            "5.0",
        ]
    )
    [why] = session.run("(why out voltage)")
    assert_why_matches(
        why,
        """
        ((OUT VOLTAGE) <= ((NODE1 VOLTAGE) (R3 RESISTANCE) (R3 CURRENT ME) (V1 VARVAL)) - OHM)
        ((NODE1 VOLTAGE) WHAT)
        ((R3 RESISTANCE) GIVEN)
        ((R3 CURRENT ME) <= () - KCL)
        ((V1 VARVAL) <= ((NODE1 VOLTAGE) (GND VOLTAGE) (R2 RESISTANCE) (R2 CURRENT #1)) - OHM)
        ((GND VOLTAGE) GIVEN)
        ((R2 RESISTANCE) GIVEN)
        ((R2 CURRENT #1) <= ((R1 CURRENT #2) (R3 CURRENT #1)) - KCL)
        ((R1 CURRENT #2) <= ((TOP VOLTAGE) (NODE1 VOLTAGE) (R1 RESISTANCE)) - OHM)
        ((TOP VOLTAGE) GIVEN)
        ((R1 RESISTANCE) GIVEN)
        QED
        """,
    )


def test_what_without_a_circuit_or_on_an_unknown_quantity_is_an_error(ladder):
    [result] = Session().run("(what output voltage)")
    assert isinstance(result, Error)
    [result] = ladder_session(ladder).run("(what r9 current)")
    assert isinstance(result, Error)


def test_why_shows_a_supposition_like_a_premise_with_its_law(ladder):
    session = ladder_session(ladder)
    session.run("(what output voltage)")
    [result] = session.run("(why output voltage)")
    assert result.render() == "((OUTPUT VOLTAGE) WHAT)\nQED"
    [result] = session.run("(why r6 current)")
    assert "((OUTPUT VOLTAGE) WHAT)" in result.render().splitlines()
