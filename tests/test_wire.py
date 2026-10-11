from el import Session
from el.results import Analysis, Error, Wired


def test_ladder_wiring_diagram_loads_and_answers_done(ladder):
    wire_text, expected = ladder[0]
    [result] = Session().run(wire_text)
    assert result.render() == expected == "DONE"


def test_analyzing_the_ladder_fills_nothing_and_answers_done(ladder):
    session = Session()
    for command, expected in ladder[:2]:
        [result] = session.run(command)
        assert result.render() == expected
    assert isinstance(result, Analysis)
    assert result.fills == []


def test_unnamed_nodes_are_numbered_in_connect_order(ladder):
    [result] = Session().run(ladder[0][0])
    nodes = result.circuit.nodes
    assert set(nodes) == {"GND", "INPUT", "OUTPUT", "NODE1", "NODE2"}
    assert {(t.name, t.element) for t in nodes["NODE1"].terminals} == {
        ("#2", "R1"),
        ("#1", "R2"),
        ("#1", "R3"),
    }
    assert {(t.name, t.element) for t in nodes["NODE2"].terminals} == {
        ("#2", "R3"),
        ("#1", "R4"),
        ("#1", "R5"),
    }


def test_named_nodes_may_have_fixed_voltages(ladder):
    [result] = Session().run(ladder[0][0])
    nodes = result.circuit.nodes
    assert nodes["GND"].voltage == 0.0
    assert nodes["INPUT"].voltage == 1.0
    assert nodes["OUTPUT"].voltage is None
    assert {(t.name, t.element) for t in nodes["OUTPUT"].terminals} == {
        ("#2", "R5"),
        ("#1", "R6"),
    }


def test_resistors_are_declared_with_resistances(ladder):
    [result] = Session().run(ladder[0][0])
    elements = result.circuit.elements
    assert {name: r.resistance for name, r in elements.items()} == {
        "R1": 1.0,
        "R2": 2.0,
        "R3": 1.0,
        "R4": 2.0,
        "R5": 1.0,
        "R6": 1.0,
    }


DIVIDER = """
(WIRE Div ; a comment (with parens
  (Node (Top {top}) (gnd 0) MID)  ; trailing comment
  (resistor (Ra {ra}) (rb {rb}))
  (connect (top (#1 ra)) (mid (#2 RA) (#1 rb)) (GND (#2 rb))))
"""


def wire_divider(session, top="15", ra="370000", rb="100000"):
    [result] = session.run(DIVIDER.format(top=top, ra=ra, rb=rb))
    assert isinstance(result, Wired), result.render()
    return result.circuit


def test_input_is_case_insensitive_and_comments_are_ignored():
    circuit = wire_divider(Session())
    assert circuit.name == "DIV"
    assert set(circuit.nodes) == {"TOP", "GND", "MID"}
    assert set(circuit.elements) == {"RA", "RB"}
    assert {(t.name, t.element) for t in circuit.nodes["MID"].terminals} == {
        ("#2", "RA"),
        ("#1", "RB"),
    }


def test_numbers_are_read_in_the_memos_forms():
    for text, value in [
        (".6", 0.6),
        ("-.6", -0.6),
        ("370000", 370000.0),
        ("2.7", 2.7),
        ("0.0", 0.0),
        ("1.10638307E-3", 1.10638307e-3),
    ]:
        circuit = wire_divider(Session(), top=text, ra=text)
        assert circuit.nodes["TOP"].voltage == value, text
        assert circuit.elements["RA"].resistance == value, text


def test_rewiring_under_an_existing_name_replaces_the_circuit():
    session = Session()
    wire_divider(session, ra="1000")
    wire_divider(session, ra="2000")
    [result] = session.run("(analyze 'div)")
    assert result.circuit.elements["RA"].resistance == 2000.0


def test_analyze_unknown_circuit_is_an_error():
    [result] = Session().run("(analyze 'nothing)")
    assert isinstance(result, Error)
    assert "NOTHING" in result.render()


def test_several_forms_in_one_text_each_give_a_result(ladder):
    text = "\n".join(command for command, _ in ladder[:2])
    assert [r.render() for r in Session().run(text)] == ["DONE", "DONE"]
