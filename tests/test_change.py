"""`change`: replacing a premise and redoing only what depended on it."""

from golden import assert_fills_match
from test_voltage_divider import LOADED

from el import Session
from el.results import Error

# VCC (10 V) -R1(100k)- BASE node -> Q1 base; emitter -R2(1k)- GND;
# collector on VCC. With the Default base current 0, R1 carries nothing:
# BASE = 10, emitter (NODE1) = 9.4, R2 current = 9.4 mA.
FOLLOWER = """
(wire follower
  (node (vcc 10) (gnd 0) base)
  (transistor (q1 .6))
  (resistor (r1 100000) (r2 1000))
  (connect
    (vcc (#1 r1) (c q1))
    (base (#2 r1) (b q1))
    ((e q1) (#1 r2))              ;NODE1
    (gnd (#2 r2))))
"""


def analyzed(wiring: str, name: str) -> Session:
    session = Session()
    session.run(wiring)
    session.run(f"(analyze '{name})")
    return session


def test_change_refuses_a_deduced_quantity():
    session = analyzed(FOLLOWER, "follower")
    [result] = session.run("(change nodE1 voltage 5.0)")
    assert isinstance(result, Error)
    assert result.render() == (
        ";ERROR: (NODE1 VOLTAGE) is not a premise: it is deduced by BE;"
        " only Givens and Defaults can change"
    )
    [why] = session.run("(why node1 voltage)")
    assert "- BE)" in why.render().splitlines()[0]


def test_change_a_default_base_current():
    """The memo's manual finite-beta step. By hand, with Ib = 10 uA:
    KCL at BASE: R1 carries 10 uA; OHM: BASE = 10 - 100k * 10 uA = 9.0;
    BE: NODE1 = 8.4; OHM: R2 = 8.4 mA; KCL: Ie = -8.4 mA;
    transistor law: Ic = 8.4 mA - 10 uA = 8.39 mA."""
    session = analyzed(FOLLOWER, "follower")
    [result] = session.run("(change q1 current b 1.0E-5)")
    assert_fills_match(
        result,
        """
        (Q1 CURRENT B 1.0E-5)
        (R1 CURRENT #2 -1.0E-5)
        (BASE VOLTAGE 9.0)
        (NODE1 VOLTAGE 8.4)
        (R2 CURRENT ME 8.4E-3)
        (Q1 CURRENT E -8.4E-3)
        (Q1 CURRENT C 8.39E-3)
        DONE
        """,
    )
    [why] = session.run("(why q1 current b)")
    assert why.render() == "((Q1 CURRENT B) GIVEN)\nQED"


def test_change_retracts_a_formal_variable_value_that_depended_on_the_premise():
    """In the loaded divider (tests/test_voltage_divider.py) MID is V1 and
    R3's current comes from KCL; R3's own OHM law is the check that solves
    V1. So R3's resistance supports only V1's value: changing it forgets that
    alone, and the check solves V1 again. By hand, with R3 = 500:
    (10 - m)/1000 = m/1000 + m/500, so m = 2.5."""
    session = analyzed(LOADED, "loaded")
    [result] = session.run("(change r3 resistance 500)")
    assert result.render() == "(R3 RESISTANCE 500.0)\n(V1 VARVAL 2.5)\nDONE"
    [answer] = session.run("(what mid voltage)")
    assert answer.render() == "2.5"


def test_change_of_a_divider_resistor_redoes_the_divider_with_a_new_variable():
    """R2's resistance feeds VD-DEMON, so MID and everything after it is
    forgotten and the demon introduces a fresh variable. As in `analyze`,
    R3's current comes from KCL at MID and R3's OHM law is the check. By
    hand, with R2 = 500: (10 - m)/1000 = m/500 + m/1000, so m = 2.5."""
    session = analyzed(LOADED, "loaded")
    [result] = session.run("(change r2 resistance 500)")
    assert_fills_match(
        result,
        """
        (R2 RESISTANCE 500.0)
        (MID VOLTAGE V2)
        (R1 CURRENT ME (&+ 1.0E-2 (&* -1.0E-3 V2)))
        (R2 CURRENT ME (&* 2.0E-3 V2))
        (R3 CURRENT #1 (&+ 1.0E-2 (&* -3.0E-3 V2)))
        (V2 VARVAL 2.5)
        DONE
        """,
    )
    [answer] = session.run("(what mid voltage)")
    assert answer.render() == "2.5"
