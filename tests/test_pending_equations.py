from el import Session

# The memo's ladder (Example 3) with a voltage divider RA-RB hanging off
# NODE2. `what output voltage` introduces V1 at OUTPUT; once NODE2 is known
# (2 V1) the VD-DEMON introduces V2 at the divider midpoint NODE3. From then
# on every check has both variables: R2's OHM gives 26 V1 - 5 V2 - 2 = 0 and
# RB's OHM gives 2 V2 - 2 V1 = 0. EL solves no simultaneous equations, so both
# stay pending. (By hand: V1 = V2 = 2/21.)
COUPLED = """
(wire coupled
  (node (gnd 0.0) (input 1.0) output)
  (resistor (r1 1) (r2 2) (r3 1) (r4 2) (r5 1) (r6 1) (ra 1) (rb 1))
  (connect
      (gnd (#2 r2) (#2 r4) (#2 r6) (#2 rb))
      (input (#1 r1))
      ((#2 r1) (#1 r2) (#1 r3))          ;NODE1
      ((#2 r3) (#1 r4) (#1 r5) (#1 ra))  ;NODE2
      ((#2 ra) (#1 rb))                  ;NODE3
      (output (#2 r5) (#1 r6)))
  (hint (vd ra rb)))
"""


def coupled_session() -> Session:
    session = Session()
    session.run(COUPLED)
    session.run("(analyze 'coupled)")
    return session


def test_what_that_cannot_solve_answers_the_expression_and_the_pending_equations():
    [result] = coupled_session().run("(what output voltage)")
    assert result.render() == "\n".join(
        [
            "(OUTPUT VOLTAGE V1)",
            "(R6 CURRENT ME V1)",
            "(R5 CURRENT #2 (&* -1.0 V1))",
            "(NODE2 VOLTAGE (&* 2.0 V1))",
            "(R4 CURRENT ME V1)",
            "(NODE3 VOLTAGE V2)",
            "(RA CURRENT ME (&+ (&* 2.0 V1) (&* -1.0 V2)))",
            "(R3 CURRENT #2 (&+ (&* -4.0 V1) V2))",
            "(NODE1 VOLTAGE (&+ (&* 6.0 V1) (&* -1.0 V2)))",
            "(R1 CURRENT ME (&+ 1.0 (&* -6.0 V1) V2))",
            "(R2 CURRENT #1 (&+ 1.0 (&* -10.0 V1) (&* 2.0 V2)))",
            "(RB CURRENT #1 (&+ (&* 2.0 V1) (&* -1.0 V2)))",
            "",
            "V1",
            "((&+ -2.0 (&* 26.0 V1) (&* -5.0 V2)) = 0 - OHM)",
            "((&+ (&* 2.0 V2) (&* -2.0 V1)) = 0 - OHM)",
        ]
    )


# An NPN stage: base divider RA-RB (no hint), collector divider RC-RD (vd
# hint), emitter to ground through RE and through RF-RG in series.
# `analyze`: the VD-DEMON puts V1 at the collector, and KCL there and the
# transistor current law carry it to the emitter current; KCL at the emitter
# then stalls. `what base voltage` puts V2 at the base. BE runs first (Q1 is
# listed first at BASE): the emitter, RE's current, RF's and RG's currents
# and NODE3 follow, and RF's OHM check has both V1 and V2: pending. Then RA
# and RB give V2 = 5 alone, and the pending equation, retried, solves V1.
# By hand: emitter 4.4 V into 1000 || 1000 ohms draws 8.8 mA; at the
# collector (10 - C)/100 = C/100 + 8.8 mA, so C = 4.56.
STAGE = """
(wire stage
  (node (vcc 10) (gnd 0) base)
  (resistor (ra 1000) (rb 1000) (rc 100) (rd 100) (re 1000) (rf 500) (rg 500))
  (transistor (q1 .6))
  (connect
      (vcc (#1 ra) (#1 rc))
      (gnd (#2 rb) (#2 rd) (#2 re) (#2 rg))
      (base (b q1) (#2 ra) (#1 rb))
      ((#2 rc) (#1 rd) (c q1))           ;NODE1
      ((e q1) (#1 re) (#1 rf))           ;NODE2
      ((#2 rf) (#1 rg)))                 ;NODE3
  (hint (vd rc rd)))
"""


def stage_session() -> Session:
    session = Session()
    session.run(STAGE)
    session.run("(analyze 'stage)")
    return session


def test_a_pending_equation_solves_its_last_variable_when_the_others_are_solved():
    session = stage_session()
    [result] = session.run("(what base voltage)")
    lines = result.render().splitlines()
    assert lines[-1] == "5.0"
    assert "(V2 VARVAL 5.0)" in lines
    assert sorted(line.split()[0] for line in lines if "VARVAL" in line) == ["(V1", "(V2"]
    [collector] = session.run("(what node1 voltage)")
    assert abs(collector.value - 4.56) < 1e-9


def test_change_retracts_the_pending_equations_that_depend_on_the_premise():
    session = coupled_session()
    session.run("(what output voltage)")
    # Only R2's OHM check read R2's resistance: that equation is retracted and
    # the check, run again, leaves (6 V1 - V2) - (1 - 10 V1 + 2 V2) = 0.
    [change] = session.run("(change r2 resistance 1)")
    assert change.render() == "(R2 RESISTANCE 1.0)\nDONE"
    [result] = session.run("(what output voltage)")
    assert result.render() == "\n".join(
        [
            "V1",
            "((&+ (&* 2.0 V2) (&* -2.0 V1)) = 0 - OHM)",
            "((&+ -1.0 (&* 16.0 V1) (&* -3.0 V2)) = 0 - OHM)",
        ]
    )


def test_change_forgets_a_variable_solved_by_a_pending_equation_and_solves_it_again():
    session = stage_session()
    session.run("(what base voltage)")
    [change] = session.run("(change rg resistance 1000)")
    varvals = [line.split()[0] for line in change.render().splitlines() if "VARVAL" in line]
    assert varvals == ["(V1"]
    [collector] = session.run("(what node1 voltage)")
    assert abs(collector.value - (10 - 4.4 / 600 * 100) / 2) < 1e-9
