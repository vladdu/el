from el import Session
from el.results import Analysis, Contradiction, Wired

# The memo's BE example: base and emitter voltages both given explicitly, 2.0
# and 1.0, so the base-emitter drop is 1.0, not Q1's VBE of 0.6.
BE_CLASH = """
(wire clash
  (node (vcc 10) (base 2) (emit 1))
  (transistor (q1 .6))
  (resistor (r1 1000))
  (connect
    (vcc (#1 r1))
    (base (b q1))
    (emit (e q1))
    ((c q1) (#2 r1))))
"""


def analyze(wire_text, name):
    session = Session()
    [wired] = session.run(wire_text)
    assert isinstance(wired, Wired), wired.render()
    [result] = session.run(f"(analyze '{name})")
    return session, result


def test_be_drop_other_than_vbe_is_a_contradiction():
    _, result = analyze(BE_CLASH, "clash")
    assert isinstance(result, Contradiction), result.render()
    assert result.law == "BE"
    names = {c.fill.ref.name for c in result.conflicts}
    assert names == {("BASE", "VOLTAGE"), ("EMIT", "VOLTAGE"), ("Q1", "VBE")}


def test_contradiction_report_gives_each_quantitys_value_and_justification():
    _, result = analyze(BE_CLASH, "clash")
    assert result.render() == (
        ";CONTRADICTION: law BE does not hold\n"
        "(BASE VOLTAGE 2.0)\n"
        "  ((BASE VOLTAGE) GIVEN)\n"
        "(EMIT VOLTAGE 1.0)\n"
        "  ((EMIT VOLTAGE) GIVEN)\n"
        "(Q1 VBE 0.6)\n"
        "  ((Q1 VBE) GIVEN)"
    )


# A deduced value clashes: Q1's BE puts NODE1 at 2.0 - 0.6 = 1.4, so Q2's
# base-emitter drop is 1.4 - 1.0 = 0.4, not its VBE of 0.6.
DEDUCED_CLASH = """
(wire chain
  (node (vcc 10) (base 2) (emit 1))
  (transistor (q1 .6) (q2 .6))
  (connect
    (vcc (c q1) (c q2))
    (base (b q1))
    ((e q1) (b q2))               ;NODE1
    (emit (e q2))))
"""


def test_contradiction_on_a_deduced_quantity_shows_its_derivation():
    _, result = analyze(DEDUCED_CLASH, "chain")
    assert isinstance(result, Contradiction), result.render()
    assert result.law == "BE"
    [node1] = [c.fill for c in result.conflicts if c.fill.ref.name == ("NODE1", "VOLTAGE")]
    assert node1.value == 1.4
    report = result.render().splitlines()
    report = report[report.index(";CONTRADICTION: law BE does not hold") :]
    i = report.index("(NODE1 VOLTAGE 1.4)")
    assert report[i + 1 : i + 4] == [
        "  ((NODE1 VOLTAGE) <= ((BASE VOLTAGE) (Q1 VBE)) - BE)",
        "  ((BASE VOLTAGE) GIVEN)",
        "  ((Q1 VBE) GIVEN)",
    ]


CHAIN_QUANTITIES = [
    *(f"{n} voltage" for n in ("vcc", "base", "emit", "node1")),
    *(f"{q} {k}" for q in ("q1", "q2") for k in ("vbe", "current b", "current e", "current c")),
]


def test_after_a_contradiction_only_the_reported_fills_are_made():
    session, result = analyze(DEDUCED_CLASH, "chain")
    assert isinstance(result, Contradiction), result.render()
    reported = {fill.render().rsplit(" ", 1)[0] + ")" for fill in result.fills}
    deduced = set()
    for name in CHAIN_QUANTITIES:
        [why] = session.run(f"(why {name})")
        first = why.render().splitlines()[0]
        if " <= " in first:
            deduced.add(first[1 : first.index(" <= ")])
    assert reported
    assert deduced == reported


def test_quantities_deduced_before_a_contradiction_can_still_be_explained():
    session, _ = analyze(DEDUCED_CLASH, "chain")
    [why] = session.run("(why node1 voltage)")
    assert why.render() == (
        "((NODE1 VOLTAGE) <= ((BASE VOLTAGE) (Q1 VBE)) - BE)\n"
        "((BASE VOLTAGE) GIVEN)\n"
        "((Q1 VBE) GIVEN)\n"
        "QED"
    )


def test_given_voltages_agreeing_with_vbe_up_to_rounding_are_no_contradiction():
    # 2.0 - 1.4 is 0.6000000000000001 in floating point.
    _, result = analyze(BE_CLASH.replace("(emit 1)", "(emit 1.4)"), "clash")
    assert isinstance(result, Analysis), result.render()
