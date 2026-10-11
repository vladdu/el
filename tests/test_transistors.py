import pytest
from golden import assert_fills_match, assert_why_matches

from el import Session
from el.results import Analysis, LoadError, Wired

# Emitter follower with a fixed base voltage. Worked by hand:
#   BE: VE = VB - VBE = 2.0 - 0.6 = 1.4 (NODE1)
#   OHM on R2 (#1 at the emitter, #2 at GND): 1.4 / 1000 = 1.4 mA
#   KCL at NODE1: Ie = -1.4 mA; transistor law: Ic = -(Ie + Ib) = 1.4 mA
#   KCL at NODE2: R1 #2 current = -1.4 mA; OHM on R1: VC = 10 - 1.4 = 8.6
NPN = """
(wire npn
  (node (vcc 10) (gnd 0) (base 2))
  (transistor (q1 .6))
  (resistor (r1 1000) (r2 1000))
  (connect
    (vcc (#1 r1))
    (base (b q1))
    ((e q1) (#1 r2))              ;NODE1
    ((c q1) (#2 r1))              ;NODE2
    (gnd (#2 r2))))
"""

NPN_ANALYSIS = """
(NODE1 VOLTAGE 1.4)
(R2 CURRENT ME 1.4E-3)
(Q1 CURRENT E -1.4E-3)
(Q1 CURRENT C 1.4E-3)
(R1 CURRENT #2 -1.4E-3)
(NODE2 VOLTAGE 8.6)
DONE
"""

# The PNP mirror image: emitter resistor to VCC, collector resistor to GND.
#   BE: VB - VE = -0.6, so VE = 8.0 + 0.6 = 8.6 (NODE1)
#   OHM on R2 (#1 at VCC): (10 - 8.6) / 1000 = 1.4 mA
#   KCL at NODE1: Ie = +1.4 mA (current flows into a PNP emitter); Ic = -1.4 mA
#   KCL at NODE2: R1 ME = 1.4 mA; OHM on R1: VC = 1.4
PNP = """
(wire pnp
  (node (vcc 10) (gnd 0) (base 8))
  (transistor (q1 -.6))
  (resistor (r1 1000) (r2 1000))
  (connect
    (vcc (#1 r2))
    (base (b q1))
    ((e q1) (#2 r2))              ;NODE1
    ((c q1) (#1 r1))              ;NODE2
    (gnd (#2 r1))))
"""

PNP_ANALYSIS = """
(NODE1 VOLTAGE 8.6)
(R2 CURRENT ME 1.4E-3)
(Q1 CURRENT E 1.4E-3)
(Q1 CURRENT C -1.4E-3)
(R1 CURRENT ME 1.4E-3)
(NODE2 VOLTAGE 1.4)
DONE
"""


def analyze(wire_text, name):
    session = Session()
    [wired] = session.run(wire_text)
    assert isinstance(wired, Wired), wired.render()
    [result] = session.run(f"(analyze '{name})")
    assert isinstance(result, Analysis), result.render()
    return result


def test_npn_with_fixed_base_voltage_analyzes_fully():
    assert_fills_match(analyze(NPN, "npn"), NPN_ANALYSIS)


def test_pnp_with_fixed_base_voltage_analyzes_fully():
    assert_fills_match(analyze(PNP, "pnp"), PNP_ANALYSIS)


def test_germanium_transistor_uses_its_smaller_drop():
    result = analyze(NPN.replace("(q1 .6)", "(q1 .3)"), "npn")
    assert_fills_match(
        result,
        """(NODE1 VOLTAGE 1.7) (R2 CURRENT ME 1.7E-3) (Q1 CURRENT E -1.7E-3)
           (Q1 CURRENT C 1.7E-3) (R1 CURRENT #2 -1.7E-3) (NODE2 VOLTAGE 8.3) DONE""",
    )


def npn_session():
    session = Session()
    session.run(NPN)
    session.run("(analyze 'npn)")
    return session


def answers(session, *commands):
    return [result.render() for c in commands for result in session.run(c)]


def test_vbe_is_a_given_and_base_current_a_default_of_zero():
    assert answers(
        npn_session(), "(what q1 vbe)", "(why q1 vbe)", "(what q1 current b)", "(why q1 current b)"
    ) == ["0.6", "((Q1 VBE) GIVEN)\nQED", "0.0", "((Q1 CURRENT B) DEFAULT)\nQED"]


def test_region_is_a_default_of_active_left_out_of_be_explanations():
    session = npn_session()
    assert answers(session, "(what q1 region)", "(why q1 region)") == [
        "ACTIVE",
        "((Q1 REGION) DEFAULT)\nQED",
    ]
    [why] = answers(session, "(why node1 voltage)")
    assert why.splitlines()[0] == "((NODE1 VOLTAGE) <= ((BASE VOLTAGE) (Q1 VBE)) - BE)"


# NPN with a PNP partner QP whose emitter shares NODE1, under a `cp` hint:
# the pair's region is unknown, so BE no longer puts NODE1 at 1.4.
NPN_IN_A_PAIR = """
(wire npn
  (node (vcc 10) (gnd 0) (base 2) pb)
  (transistor (q1 .6) (qp -.6))
  (resistor (r1 1000) (r2 1000))
  (connect
    (vcc (#1 r1))
    (base (b q1))
    ((e q1) (e qp) (#1 r2))       ;NODE1
    ((c q1) (#2 r1))              ;NODE2
    (gnd (#2 r2) (c qp))
    (pb (b qp)))
  (hint (cp q1 qp)))
"""


def test_without_an_active_region_be_deduces_nothing():
    session = Session()
    session.run(NPN_IN_A_PAIR)
    [analysis] = session.run("(analyze 'npn)")
    assert isinstance(analysis, Analysis), analysis.render()
    assert "(NODE1 VOLTAGE 1.4)" not in analysis.render().splitlines()
    for quantity in ("node1 voltage", "pb voltage"):
        [why] = session.run(f"(why {quantity})")
        assert "- BE)" not in why.render()


def test_emitter_and_collector_currents_are_separate_quantities():
    session = npn_session()
    [why] = answers(session, "(why q1 current c)")
    assert why.splitlines()[0] == (
        "((Q1 CURRENT C) <= ((Q1 CURRENT B) (Q1 CURRENT E)) - TRANSISTOR)"
    )
    [change] = answers(session, "(change q1 current b 1.0E-4)")
    assert "(Q1 CURRENT C 1.3E-3)" in change.splitlines()
    assert answers(session, "(what q1 current e)") == ["-1.4E-3"]


def test_load_time_checks_cover_transistor_terminals():
    [result] = Session().run(NPN.replace("(base (b q1))", "(base (x q1))"))
    assert isinstance(result, LoadError), result.render()
    assert sorted(p.kind for p in result.problems) == ["UNCONNECTED-TERMINAL", "UNKNOWN-TERMINAL"]
    assert any("(B Q1)" in p.message for p in result.problems)


# The memo aliases a transistor's E and C currents (spec Further Notes); our
# tree has `(Q1 CURRENT C) <= ((Q1 CURRENT B) (Q1 CURRENT E)) - TRANSISTOR`
# and `(Q1 CURRENT E) <= ((R2 CURRENT #1)) - KCL`. Collapsed, that is the
# memo's `(Q1 CURRENT C) <= ((R2 CURRENT #1)) - KCL`, and (Q1 CURRENT B),
# used only by the transistor step, drops out.
MEMO_STYLE_WHY_R1 = """
((R1 CURRENT #2) <= ((Q1 CURRENT C)) - KCL)
((Q1 CURRENT C) <= ((R2 CURRENT #1)) - KCL)
((R2 CURRENT #1) <= ((NODE1 VOLTAGE) (GND VOLTAGE) (R2 RESISTANCE)) - OHM)
((NODE1 VOLTAGE) <= ((Q1 VBE) (BASE VOLTAGE)) - BE)
((GND VOLTAGE) GIVEN)
((R2 RESISTANCE) GIVEN)
((Q1 VBE) GIVEN)
((BASE VOLTAGE) GIVEN)
QED
"""


def npn_why_r1():
    session = Session()
    session.run(NPN)
    session.run("(analyze 'npn)")
    [why] = session.run("(why r1 current)")
    return why


def test_comparator_collapses_transistor_current_law_steps_when_asked():
    assert_why_matches(npn_why_r1(), MEMO_STYLE_WHY_R1, collapse_transistor_currents=True)


def test_comparator_keeps_transistor_current_law_steps_by_default():
    with pytest.raises(AssertionError):
        assert_why_matches(npn_why_r1(), MEMO_STYLE_WHY_R1)


def test_collapsed_comparison_still_catches_a_wrong_antecedent():
    wrong = MEMO_STYLE_WHY_R1.replace(
        "((Q1 CURRENT C) <= ((R2 CURRENT #1)) - KCL)",
        "((Q1 CURRENT C) <= ((R2 CURRENT #1) (Q1 CURRENT B)) - KCL)\n((Q1 CURRENT B) DEFAULT)",
    )
    with pytest.raises(AssertionError):
        assert_why_matches(npn_why_r1(), wrong, collapse_transistor_currents=True)


def test_collapsed_fills_count_aliased_e_and_c_currents_once():
    memo_style = NPN_ANALYSIS.replace("(Q1 CURRENT C 1.4E-3)\n", "")
    result = analyze(NPN, "npn")
    assert_fills_match(result, memo_style, collapse_transistor_currents=True)
    with pytest.raises(AssertionError):
        assert_fills_match(result, memo_style)
    inconsistent = NPN_ANALYSIS.replace("(Q1 CURRENT C 1.4E-3)", "(Q1 CURRENT C 2.0E-3)")
    with pytest.raises(AssertionError):
        assert_fills_match(result, inconsistent, collapse_transistor_currents=True)
