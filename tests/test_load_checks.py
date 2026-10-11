from el import Session
from el.results import LoadError, Wired

GOOD = """
(wire div
  (node (top 15) (gnd 0))
  (resistor (ra 1000) (rb 2000))
  (connect (top (#1 ra)) ((#2 ra) (#1 rb)) (gnd (#2 rb))))
"""


def rejected(text, session=None):
    [result] = (session or Session()).run(text)
    assert isinstance(result, LoadError), result.render()
    return result


def kinds(result):
    return [p.kind for p in result.problems]


def test_good_wiring_diagram_passes_every_check():
    [result] = Session().run(GOOD)
    assert isinstance(result, Wired), result.render()


def test_connection_naming_an_undeclared_element_is_rejected():
    result = rejected(GOOD.replace("(gnd (#2 rb))", "(gnd (#2 rb) (#1 r7))"))
    assert kinds(result) == ["UNDECLARED-PART"]
    assert "R7" in result.problems[0].message


def test_connection_naming_an_undeclared_node_is_rejected():
    result = rejected(GOOD.replace("(gnd (#2 rb))", "(ground (#2 rb))"))
    assert "UNDECLARED-PART" in kinds(result)
    assert any("GROUND" in p.message for p in result.problems)


def test_declared_element_never_connected_is_rejected():
    result = rejected(GOOD.replace("(rb 2000)", "(rb 2000) (rc 5)"))
    assert kinds(result) == ["UNCONNECTED-PART"]
    assert "RC" in result.problems[0].message


def test_declared_node_never_connected_is_rejected():
    result = rejected(GOOD.replace("(gnd 0)", "(gnd 0) spare"))
    assert kinds(result) == ["UNCONNECTED-PART"]
    assert "SPARE" in result.problems[0].message


def test_terminal_in_two_connections_is_rejected():
    result = rejected(GOOD.replace("(gnd (#2 rb))", "(gnd (#2 rb) (#1 ra))"))
    assert kinds(result) == ["TERMINAL-CONNECTED-TWICE"]
    message = result.problems[0].message
    assert "(#1 RA)" in message and "TOP" in message and "GND" in message


def test_terminal_left_unconnected_is_rejected():
    result = rejected(GOOD.replace("(gnd (#2 rb))", "(gnd)"))
    assert kinds(result) == ["UNCONNECTED-TERMINAL"]
    assert "(#2 RB)" in result.problems[0].message


def test_terminal_the_element_does_not_have_is_rejected():
    result = rejected(GOOD.replace("(gnd (#2 rb))", "(gnd (#2 rb) (#3 rb))"))
    assert kinds(result) == ["UNKNOWN-TERMINAL"]
    assert "(#3 RB)" in result.problems[0].message


def test_every_problem_is_reported_and_renders_as_readable_text():
    text = GOOD.replace("(rb 2000)", "(rb 2000) (rc 5)").replace(
        "(gnd (#2 rb))", "(gnd (#1 r7)) (ground (#1 ra))"
    )
    result = rejected(text)
    assert result.name == "DIV"
    assert result.render() == "\n".join(
        [
            ";ERROR: wiring diagram DIV rejected",
            ";  (#1 R7) names undeclared element R7",
            ";  connection names undeclared node GROUND",
            ";  element RC is declared but never connected",
            ";  (#1 RA) is connected to both TOP and GROUND",
            ";  (#2 RB) is not connected",
        ]
    )


def test_malformed_wiring_diagram_is_a_load_error():
    result = rejected("(wire div (node (top fifteen)))")
    assert kinds(result) == ["MALFORMED"]


def test_rejected_wiring_diagram_leaves_existing_circuit_untouched():
    session = Session()
    [good] = session.run(GOOD)
    rejected(GOOD.replace("(gnd (#2 rb))", "(gnd)"), session)
    [analysis] = session.run("(analyze 'div)")
    assert analysis.circuit is good.circuit
    assert session.circuits["DIV"] is good.circuit


# GOOD plus a transistor and a third resistor RC from TOP to GND, so that a
# vd hint can name the wrong kinds of part.
HINTED = """
(wire div
  (node (top 15) (gnd 0) base)
  (resistor (ra 1000) (rb 2000) (rc 500))
  (transistor (q1 .6))
  (connect (top (#1 ra) (#1 rc) (c q1)) ((#2 ra) (#1 rb)) (gnd (#2 rb) (#2 rc) (e q1))
           (base (b q1)))
  (hint HINT))
"""


def hinted(hint):
    return HINTED.replace("HINT", hint)


def test_vd_hint_on_two_resistors_sharing_a_node_passes():
    [result] = Session().run(hinted("(vd ra rb)"))
    assert isinstance(result, Wired), result.render()


def test_vd_hint_naming_a_transistor_is_rejected():
    result = rejected(hinted("(vd ra q1)"))
    assert kinds(result) == ["BAD-HINT"]
    assert "(VD RA Q1)" in result.problems[0].message


def test_vd_hint_naming_an_undeclared_part_is_rejected():
    assert kinds(rejected(hinted("(vd ra r9)"))) == ["BAD-HINT"]


def test_vd_hint_naming_other_than_two_parts_is_rejected():
    assert kinds(rejected(hinted("(vd ra)"))) == ["BAD-HINT"]
    assert kinds(rejected(hinted("(vd ra rb rc)"))) == ["BAD-HINT"]


def test_vd_hint_on_resistors_not_sharing_a_node_is_rejected():
    text = hinted("(vd ra rb)").replace("((#2 ra) (#1 rb))", "((#2 ra)) ((#1 rb))")
    result = rejected(text)
    assert kinds(result) == ["BAD-HINT"]
    assert "share" in result.problems[0].message


def test_vd_hint_on_resistors_in_parallel_is_rejected():
    # RD across TOP-NODE1, alongside RA: both nodes shared, no midpoint.
    text = hinted("(vd ra rd)").replace("(rc 500)", "(rc 500) (rd 10)")
    text = text.replace("(#1 rc)", "(#1 rc) (#1 rd)").replace("((#2 ra)", "((#2 ra) (#2 rd)")
    assert kinds(rejected(text)) == ["BAD-HINT"]


def test_unknown_hint_is_a_load_error():
    assert kinds(rejected(hinted("(xx ra rb)"))) == ["MALFORMED"]


# An NPN QN and a PNP QP whose emitters reach OUT through RE1 and RE2, plus
# a second NPN QX and a resistor RB.
PAIRED = """
(wire pair
  (node (vcc 20) (gnd 0) out)
  (resistor (re1 10) (re2 10) (rb 1000))
  (transistor (qn .6) (qp -.6) (qx .6))
  (connect (vcc (c qn) (c qx) (#1 rb)) ((#2 rb) (b qn) (b qp) (b qx))
           ((e qn) (#1 re1)) ((e qp) (#1 re2)) (out (#2 re1) (#2 re2) (e qx))
           (gnd (c qp)))
  (hint HINT))
"""


def paired(hint):
    return PAIRED.replace("HINT", hint)


def test_cp_hint_on_an_npn_and_a_pnp_whose_emitters_reach_a_common_node_passes():
    for hint in ("(cp qn qp)", "(cp qp qn)"):
        [result] = Session().run(paired(hint))
        assert isinstance(result, Wired), result.render()


def test_cp_hint_on_emitters_at_the_same_node_passes():
    text = paired("(cp qx qp)").replace("((e qp) (#1 re2))", "((#1 re2))")
    text = text.replace("(e qx))", "(e qx) (e qp))")
    [result] = Session().run(text)
    assert isinstance(result, Wired), result.render()


def test_cp_hint_on_two_npns_is_rejected():
    result = rejected(paired("(cp qn qx)"))
    assert kinds(result) == ["BAD-HINT"]
    assert "(CP QN QX)" in result.problems[0].message


def test_cp_hint_naming_a_resistor_an_undeclared_part_or_not_two_parts_is_rejected():
    for hint in ("(cp qn rb)", "(cp qn q9)", "(cp qn)", "(cp qn qp qx)"):
        assert kinds(rejected(paired(hint))) == ["BAD-HINT"], hint


def test_cp_hint_on_emitters_reaching_no_common_node_is_rejected():
    text = paired("(cp qn qp)").replace("(out (#2 re1) (#2 re2) (e qx))", "(out (#2 re1) (e qx))")
    text = text.replace("(gnd (c qp))", "(gnd (c qp) (#2 re2))")
    assert kinds(rejected(text)) == ["BAD-HINT"]
