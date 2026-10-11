"""The `cp` macro-element beyond the memo's Example 2."""

from golden import assert_fills_match, assert_why_matches

from el import Session

# QN's base is held at 10 V; the emitters of QN and QP share OUT, loaded by
# RL (1k) to GND; QP's base is PB. Without the hint, BE would put OUT at
# 9.4 V. With it, by hand: OUT = 10 - X, PB = OUT - X = 10 - 2X, and
# RL's current = OUT / 1000.
PAIR = """
(wire pair
  (node (vcc 20) (gnd 0) (bias 10) out pb)
  (resistor (rl 1000))
  (transistor (qn .6) (qp -.6))
  (connect (vcc (c qn)) (bias (b qn)) (out (e qn) (e qp) (#1 rl))
           (gnd (c qp) (#2 rl)) (pb (b qp)))
  (hint (cp qn qp)))
"""


def analyzed(text: str = PAIR) -> tuple[Session, object]:
    session = Session()
    session.run(text)
    [analysis] = session.run("(analyze 'pair)")
    return session, analysis


def test_a_filled_base_gives_the_midpoint_and_other_base_symmetrically():
    _, analysis = analyzed()
    assert_fills_match(
        analysis,
        """
        (OUT VOLTAGE (&+ 10.0 (&* -1.0 V1)))
        (PB VOLTAGE (&+ 10.0 (&* -2.0 V1)))
        (RL CURRENT ME (&+ 1.0E-2 (&* -1.0E-3 V1)))
        DONE
        """,
    )


def test_cp_transistors_get_no_be_deduction():
    session, _ = analyzed()
    [why] = session.run("(why out voltage)")
    assert_why_matches(
        why,
        """
        ((OUT VOLTAGE) <= ((BIAS VOLTAGE)) - CP)
        ((BIAS VOLTAGE) GIVEN)
        QED
        """,
    )


def test_hint_order_does_not_decide_which_base_is_above_the_midpoint():
    _, analysis = analyzed(PAIR.replace("(cp qn qp)", "(cp qp qn)"))
    assert "(OUT VOLTAGE (&+ 10.0 (&* -1.0 V1)))" in analysis.render().splitlines()


def test_without_the_hint_be_sets_the_emitter_voltage():
    _, analysis = analyzed(PAIR.replace("(hint (cp qn qp))", ""))
    assert "(OUT VOLTAGE 9.4)" in analysis.render().splitlines()


def test_cp_region_is_a_default_of_unknown():
    session, _ = analyzed()
    for transistor in ("qn", "qp"):
        [what] = session.run(f"(what {transistor} region)")
        assert what.render() == "UNKNOWN"
        [why] = session.run(f"(why {transistor} region)")
        assert why.render() == f"(({transistor.upper()} REGION) DEFAULT)\nQED"
