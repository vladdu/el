"""`change`: replacing a premise and redoing only what depended on it."""

from golden import assert_fills_match
from test_voltage_divider import LOADED

from el import Session
from el.results import Contradiction, Error, Unfilled

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


# Q2's emitter sits on the fixed node E2 (4.4 V), so BE puts BASE at 5.0.
# R1-R2 (1k each) divide VCC-GND onto BASE: 5 mA in, 5 mA out, KCL holds.
# Q1 follows BASE: NODE1 = 4.4, R3 to GND carries 4.4 mA, and so does R4
# from VCC to Q1's collector, so NODE2 = 5.6. Changing E2 to 3.0 puts BASE
# at 3.6, where R1 brings 6.4 mA but R2 takes only 3.6 mA: a contradiction.
TWIN = """
(wire twin
  (node (vcc 10) (gnd 0) (e2 4.4) base)
  (transistor (q1 .6) (q2 .6))
  (resistor (r1 1000) (r2 1000) (r3 1000) (r4 1000))
  (connect
    (vcc (#1 r1) (#1 r4) (c q2))
    (base (#2 r1) (#1 r2) (b q1) (b q2))
    (e2 (e q2))
    ((e q1) (#1 r3))              ;NODE1
    ((c q1) (#2 r4))              ;NODE2
    (gnd (#2 r2) (#2 r3))))
"""

TWIN_QUANTITIES = [
    *(f"{n} voltage" for n in ("vcc", "gnd", "e2", "base", "node1", "node2")),
    *(f"{r} {k}" for r in ("r1", "r2", "r3", "r4") for k in ("resistance", "current")),
    *(f"{q} {k}" for q in ("q1", "q2") for k in ("vbe", "current b", "current e", "current c")),
]


def state(session: Session) -> dict[str, tuple[str, str]]:
    """Each quantity's `why` tree and, if it has a value, its `what` answer."""
    out = {}
    for name in TWIN_QUANTITIES:
        [why] = session.run(f"(why {name})")
        value = "" if isinstance(why, Unfilled) else session.run(f"(what {name})")[0].render()
        out[name] = (why.render(), value)
    return out


def test_a_change_that_contradicts_is_undone():
    session = analyzed(TWIN, "twin")
    before = state(session)
    assert before["base voltage"][1] == "5.0"
    assert before["node2 voltage"][1] == "5.6"
    [result] = session.run("(change e2 voltage 3.0)")
    assert isinstance(result, Contradiction), result.render()
    report = result.render()
    assert "(BASE VOLTAGE 3.6)" in report.splitlines()
    assert report.splitlines()[-1] == ";CHANGE UNDONE: (E2 VOLTAGE) is still 4.4"
    assert state(session) == before


def test_after_an_undone_change_a_consistent_change_still_works():
    session = analyzed(TWIN, "twin")
    session.run("(change e2 voltage 3.0)")
    [result] = session.run("(change e2 voltage 4.0)")
    assert isinstance(result, Contradiction), result.render()
    [result] = session.run("(change r3 resistance 2000)")
    assert_fills_match(
        result,
        "(R3 RESISTANCE 2000.0) (R3 CURRENT ME 2.2E-3) (Q1 CURRENT E -2.2E-3)"
        " (Q1 CURRENT C 2.2E-3) (R4 CURRENT #2 -2.2E-3) (NODE2 VOLTAGE 7.8) DONE",
    )
