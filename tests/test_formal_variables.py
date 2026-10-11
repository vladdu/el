from golden import assert_answer_matches

from el import Session


def test_what_on_the_ladder_solves_the_output_voltage_by_wishful_thinking(ladder):
    session = Session()
    for command, _ in ladder[:2]:
        session.run(command)
    command, expected = ladder[2]
    [result] = session.run(command)
    assert_answer_matches(result, expected)
