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
