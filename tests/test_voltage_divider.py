"""The `vd` macro-element beyond the memo's Example 1."""

from golden import assert_why_matches

from el import Session

# TOP (10 V) -R1(1k)- MID -R2(1k)- GND, with R3 (1k) loading MID to GND.
# By hand: R2 || R3 = 500, so MID = 10 * 500 / 1500 = 3.3333.... The divider
# formula, which ignores the load, would give 5.0.
LOADED = """
(wire loaded
  (node (top 10) (gnd 0) mid)
  (resistor (r1 1000) (r2 1000) (r3 1000))
  (connect (top (#1 r1)) (mid (#2 r1) (#1 r2) (#1 r3)) (gnd (#2 r2) (#2 r3)))
  (hint (vd r1 r2)))
"""


def loaded_session() -> Session:
    session = Session()
    session.run(LOADED)
    session.run("(analyze 'loaded)")
    return session


def test_loaded_divider_midpoint_accounts_for_the_load():
    [answer] = loaded_session().run("(what mid voltage)")
    assert abs(answer.value - 10 / 3) < 1e-12


def test_vd_demon_introduces_a_formal_variable_justified_by_the_divider():
    [why] = loaded_session().run("(why mid voltage)")
    assert_why_matches(
        why,
        """
        ((MID VOLTAGE) <= ((R1 RESISTANCE) (R2 RESISTANCE) (TOP VOLTAGE) (GND VOLTAGE))
                          - VD-DEMON)
        ((R1 RESISTANCE) GIVEN)
        ((R2 RESISTANCE) GIVEN)
        ((TOP VOLTAGE) GIVEN)
        ((GND VOLTAGE) GIVEN)
        QED
        """,
    )


def test_without_the_hint_the_divider_is_not_solved():
    session = Session()
    session.run(LOADED.replace("(hint (vd r1 r2))", ""))
    [analysis] = session.run("(analyze 'loaded)")
    assert analysis.render() == "DONE"
