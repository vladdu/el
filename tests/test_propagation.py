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


def analyze_chain():
    session = Session()
    session.run(CHAIN)
    [result] = session.run("(analyze 'chain)")
    assert isinstance(result, Analysis), result.render()
    return result


def test_resistor_chain_between_fixed_nodes_analyzes_fully():
    assert_fills_match(analyze_chain(), CHAIN_ANALYSIS)
