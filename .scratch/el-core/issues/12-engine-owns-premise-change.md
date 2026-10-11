# 12: The engine owns analyze, what and change, undo included

**What to build:** The engine's interface becomes one function per command, `analyze`, `what` and `change`, each a single transaction. The engine owns the premise rule, fresh formal variables, retract-wake-refill and undo on contradiction; `Session` only parses commands, words refusals and builds results. Undo replays a trail of every write the command made instead of copying the circuit's state up front. A `what` that ends in a contradiction is now undone, like a `change`.

**Blocked by:** 08, 10, 11

**Status:** resolved

- [x] `engine.analyze(circuit, new_variable)`, `engine.what(ref, new_variable)` and `engine.change(ref, value, new_variable)` are the engine's whole interface; `Engine`, `propagate`, `retract` and `snapshot` are private or gone
- [x] Only the engine writes quantity state during a command (`value`, `justification`, `dependents`, a formal variable's `pending`, a pending equation's `justification`); every write goes through a trail, and undo replays it backwards
- [x] `change` refuses a quantity that is not a premise, or an operating region, by raising `Refused` with a structured reason; `Session` renders the same `Error` text as before
- [x] `Contradicted` carries the fills, the law, the conflicting quantities with their `why` trees as they were at the failed check, and what was undone; state is already undone when it reaches `Session`
- [x] A `what` that ends in a contradiction is undone: no fills and no formal variable remain, and the report ends `;WHAT UNDONE: (X Y) has no value`
- [x] `Fill`, `why` steps and their walk, `Conflict` and pending-equation report data live in `el.quantity`; `el.results` only renders; the engine no longer imports `el.results`
- [x] Test: a `what` that contradicts leaves no fills and no new variable
- [x] Test: a `change` that makes a fresh variable and a pending equation, then contradicts, is fully undone
- [x] Test: a refused `change` still renders the same `Error` text
- [x] Memo examples and all existing tests pass (one test line reworded, see Comments)

## Comments

- `what` and `change` take no circuit argument (`what(ref, new_variable)`, `change(ref, value, new_variable)`): with undo on the trail, neither needs it.
- One existing test line changed: `test_after_a_contradiction_only_the_reported_fills_are_made` took a fill's name from `fill.render()`; `Fill` is now data with no `render`, so it uses `fill.ref.name`.
- Mutation check: dropping undo for any one trail operation (set, list append, list remove) fails at least one test; list undo is caught only by the new fresh-variable change test.
