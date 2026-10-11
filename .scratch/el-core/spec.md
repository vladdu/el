# Spec: EL core (1975 DC bias analyzer)

Status: resolved

Source: Sussman & Stallman, MIT AI Memo 328 (`ref/AIM-328.md` + `ref/figures/`). Vocabulary: `GLOSSARY.md`. Decisions: `docs/adr/`.

## Problem Statement

The project is empty. We want EL, the heuristic circuit analyzer described in AI Memo 328: it solves DC bias circuits by local one-step deductions guided by designer intent (hints), introduces formal variables when local deduction stalls, and can explain every result and revise it when a premise changes. No implementation exists, and the memo's original MACLISP source is not available. We need a faithful reconstruction of the core whose behaviour is checked against the memo's own transcripts, built so that the memo's proposed extensions can be added later without a rewrite.

## Solution

A Python package plus a REPL that accepts the memo's command syntax as written: `wire`, `analyze`, `why`, `change`, `what`. A user can paste any of the memo's three example wiring diagrams and commands and get the same quantities, values (to single-float precision) and explanations as the memo's transcripts. Underneath is a propagation engine:

- every part of a circuit (element or node) owns quantities and laws
- filling a quantity wakes the parts that own it
- each fill records its justification
- hints become macro-elements
- formal variables are solved by consistency checks
- `change` retracts a premise and everything that depends on it, then re-propagates

Contradictions are reported with explanations instead of failing silently.

## User Stories

### Describing circuits

1. As a circuit analyst, I want to declare a wiring diagram with the memo's `wire` form, so that I can paste the memo's examples unchanged.
2. As a circuit analyst, I want to declare named nodes, optionally with fixed voltages (e.g. `(vcc 15)`, `(gnd 0)`), so that supply rails and ground are Givens.
3. As a circuit analyst, I want to declare resistors with resistance values, so that Ohm's law can be applied.
4. As a circuit analyst, I want to declare transistors with a signed base-emitter drop (`.6` NPN silicon, `-.6` PNP, magnitude `.3` germanium), so that polarity and material follow from one number.
5. As a circuit analyst, I want to list each node as a set of connected terminals in `connect`, so that the circuit's topology is explicit.
6. As a circuit analyst, I want to refer to terminals as `(#1 r1)`, `(#2 r1)`, `(b q1)`, `(e q1)`, `(c q1)`, so that I use the memo's terminal names.
7. As a circuit analyst, I want unnamed nodes to be named `NODE1`, `NODE2`, ... in the order they appear in `connect`, so that my results line up with the memo's.
8. As a circuit analyst, I want to declare a `vd` hint naming two resistors, so that EL treats them as a voltage-divider macro-element.
9. As a circuit analyst, I want to declare a `cp` hint naming an NPN and a PNP transistor, so that EL treats them as a complementary-pair macro-element.
10. As a circuit analyst, I want input to be case-insensitive and to accept `;` comments and numbers like `.6`, `-.6`, `370000`, `2.7`, so that the memo's text is read exactly as printed.
11. As a circuit analyst, I want re-declaring a wiring diagram under an existing name to replace the old circuit, so that I can iterate on a design.
12. As a circuit analyst, I want `wire` to answer `DONE` on success, so that the REPL behaves like the memo.

### Load-time checks

13. As a circuit analyst, I want a clear error when a connection names a part that was never declared, so that typos are caught.
14. As a circuit analyst, I want a clear error when a declared part is never connected, so that I don't silently analyze a different circuit.
15. As a circuit analyst, I want a clear error when a terminal appears in two connections, so that contradictory topology is rejected.
16. As a circuit analyst, I want a clear error when a terminal is left unconnected, so that incomplete diagrams are rejected.
17. As a circuit analyst, I want a clear error when a `vd` hint names parts that are not two resistors sharing a node, so that wrong hints are caught.
18. As a circuit analyst, I want a clear error when a `cp` hint does not name one NPN and one PNP whose emitters reach a common node, so that wrong hints are caught.
19. As a circuit analyst, I want a rejected wiring diagram to leave any existing circuit of that name untouched, so that a typo doesn't destroy prior work.

### Analysis

20. As a circuit analyst, I want `(analyze 'name)` to run propagation until nothing more can be deduced and print every quantity filled along the way, so that I see what EL concluded.
21. As a circuit analyst, I want each printed line in the memo's form, e.g. `(R4 CURRENT ME 1.10638307E-3)` or `(NODE2 VOLTAGE 2.59148955)`, so that output reads like the memo.
22. As a circuit analyst, I want terminal currents to mean current *into* that terminal, and `ME` to mean the current into a resistor's `#1` terminal, so that signs match the memo.
23. As a circuit analyst, I want quantities whose value is an expression in formal variables printed in the memo's `&+`/`&*` form, so that intermediate symbolic results are visible.
24. As a circuit analyst, I want the introduction of a formal variable shown as e.g. `(INPUT VOLTAGE V7)` and its solution as `(V7 VARVAL 3.19148964)`, so that I can follow EL's reasoning.
25. As a circuit analyst, I want each transistor's base current to be a Default of zero, so that EL reasons the way designers do.
26. As a circuit analyst, I want each transistor's operating region to be a Default of ACTIVE (unless a `cp` hint applies), so that the BE law sets the emitter voltage from the base voltage.
27. As a circuit analyst, I want the `vd` macro-element to introduce a formal variable at the divider's midpoint once both end voltages are known, so that dividers are solved correctly even when current is drawn from the midpoint.
28. As a circuit analyst, I want the `cp` macro-element to tie the two bases and the midpoint node symmetrically with a fresh formal variable once any one of the three voltages is known, so that complementary pairs are solved as in Example 2.
29. As a circuit analyst, I want a `cp` hint to make its transistors' operating region unknown rather than ACTIVE, so that no fixed base-emitter drop is assumed for them.
30. As a circuit analyst, I want a law whose quantities are all filled to check consistency, and to solve for the formal variable if exactly one remains unsolved, so that voltage dividers and the ladder resolve.
31. As a circuit analyst, I want an equation with more than one unsolved formal variable kept as a pending equation and retried whenever one of its variables is solved, so that no information is thrown away.
32. As a circuit analyst, I want `analyze` on a circuit with no possible one-step deduction (the ladder) to print nothing and answer `DONE`, so that behaviour matches the memo.
33. As a circuit analyst, I want the most recently analyzed circuit to be the one `why`, `change` and `what` act on, so that I don't have to repeat its name.

### Explanation

34. As a circuit analyst, I want `(why r3 current)` to print the justification tree of a quantity in the memo's format, so that I can audit any result.
35. As a circuit analyst, I want each line of a `why` tree to show the quantity, its antecedents and the law (KCL, OHM, BE, VD-DEMON, ...), so that each step can be checked by hand.
36. As a circuit analyst, I want Givens shown as `GIVEN` and Defaults shown as `DEFAULT`, so that I can tell my inputs apart from EL's design assumptions.
37. As a circuit analyst, I want a formal variable's value used in a deduction to appear as an antecedent (e.g. `(V7 VARVAL)`), so that the explanation is complete.
38. As a circuit analyst, I want a `why` tree to end with `QED`, so that output matches the memo.
39. As a circuit analyst, I want `why` on an unfilled quantity to say so plainly, so that I am not misled.
40. As a circuit analyst, I want operating-region premises left out of `why` output, so that explanations stay as concise as the memo's (ADR 0001).

### Change

41. As a circuit analyst, I want `(change r6 resistance 3200.0)` to replace a premise's value, so that I can explore design variations.
42. As a circuit analyst, I want `change` to forget every quantity, formal-variable value and pending equation that depended on the old premise, and nothing else, so that surviving conclusions are reused.
43. As a circuit analyst, I want `change` to print the new premise and every quantity deduced again, so that I see exactly what moved.
44. As a circuit analyst, I want `change` to be able to target Defaults as well as Givens (e.g. a transistor's base current), so that I can do the memo's manual finite-beta perturbation.
45. As a circuit analyst, I want `change` on a quantity that is not a premise to be refused with an explanation, so that I don't corrupt the dependency record.

### Wishful thinking

46. As a circuit analyst, I want `(what output voltage)` to return a filled quantity's value directly, so that I can query results.
47. As a circuit analyst, I want `what` on an unfilled quantity to introduce a formal variable for it, propagate, and return the solved value, so that the ladder and similar circuits are solved (Example 3).
48. As a circuit analyst, I want `what` to return the expression and list the pending equations involved when the formal variable cannot be solved, so that I get partial information instead of a failure.

### Contradictions

49. As a circuit analyst, I want a law whose filled quantities disagree to report a contradiction naming the quantities and printing the justification of each, so that I can see which premises conflict.
50. As a circuit analyst, I want the state left unchanged after a contradiction, so that I can fix it with `change`.

### REPL and library use

51. As a circuit analyst, I want an interactive REPL that reads memo commands and prints memo-style output, so that I can work as in the memo.
52. As a researcher, I want the same functionality from Python through a `Session` object that takes command text and returns structured results (fills, why trees, contradictions, load errors), so that I can script analyses and write tests.
53. As a researcher, I want structured results to render to exactly the text the REPL prints, so that there is one source of output.

### Extensibility (for later work)

54. As a researcher, I want element types, their quantities and their laws defined uniformly, so that capacitors, inductors and new macro-elements can be added later without changing the engine.
55. As a researcher, I want operating region recorded as a premise in the dependency graph, so that model switching on contradiction can later be done by premise retraction.
56. As a researcher, I want transistor currents related by an explicit transistor current law rather than aliased, so that finite base current works without rework.
57. As a researcher, I want expressions to support several formal variables, so that a simultaneous-equation solver can later consume pending equations.

## Implementation Decisions

- **Language and packaging**: Python 3.14, managed with uv, built with hatchling, src layout, package `el`. Lint with ruff, test with pytest. No runtime dependencies.
- **Modules**:
  - **Reader**: s-expression reader. Case-folds symbols, parses numbers in the memo's forms, strips `;` comments. Also used by tests to parse expected transcripts.
  - **Linear expressions**: a constant plus a map from formal variable to coefficient, with exact arithmetic for add, subtract, scale, evaluate under known variable values, and solve for a single unknown. Renders as memo `&+`/`&*` form. Hand-written; no SymPy.
  - **Wiring-diagram loader**: turns a `wire` form into a circuit, applying every load-time check (stories 13-19) before anything is built. Names anonymous nodes NODE1..n in `connect` order.
  - **Circuit model**: parts (elements and nodes), the quantities each owns, and the laws attached to each part type:
    - Node: KCL over its terminal currents, plus voltage. KCL applies only to nodes without a fixed voltage: a fixed node stands for a source, which supplies whatever current is needed.
    - Resistor: OHM over its terminal voltages, resistance and current. `ME` is current into `#1`, and the `#1` and `#2` currents are opposite.
    - Transistor:
      - BE law over base voltage, emitter voltage and VBE. It depends on operating region = ACTIVE.
      - Transistor current law `Ie + Ib + Ic = 0`.
      - Base current is a Default of 0, and operating region is a Default of ACTIVE.
    - Macro-elements: `vd` (VD-DEMON) and `cp`, as described in stories 27-29.
  - **Engine**:
    - Propagates with an explicit LIFO stack of parts to wake (depth-first), running until the stack is empty. FIFO cannot reproduce the memo's intermediate expressions (e.g. the ladder's `(R2 CURRENT #1 (&+ 1.0 (&* -6.0 V3)))`) or its why trees; the memo's own account of the voltage divider (one resistor, then KCL at the midpoint, then the other resistor's consistency check) is a depth-first chain.
    - When a node's voltage is filled, the parts at that node are woken in the order its `connect` entry lists them, with macro-elements last. This reproduces Example 1's why trees.
    - Fills quantities and records a justification (law plus antecedents) and the quantities that depend on each one.
    - When a law reads a quantity, the values of known formal variables are substituted in, and each one used is recorded as an antecedent. Stored expressions are not rewritten.
    - Runs consistency checks. Holds pending equations. Retracts. Detects contradictions.
    - Its interface is one function per command, `analyze`, `what` and `change`, each one transaction. It owns the premise rule (refusing a non-premise or an operating region), fresh formal variables, retract-wake-refill and undo on contradiction. It is the only code that writes quantity state during a command; every write is recorded on a trail, and undo replays the trail backwards.
  - **Session**: the command interpreter for `wire`, `analyze`, `why`, `change`, `what`. Holds circuits by name and tracks the current circuit. Parses commands, words the engine's refusals, and returns structured results that can render to memo text. Result data (fills, `why` trees, conflicts) is built in the domain modules; the results module only renders.
  - **REPL/CLI**: a thin loop over Session.
- **Premises**: a premise is either a Given (from the wiring diagram or `change`) or a Default (from a component model). Only premises may be `change`d.
- **Operating region**: a hidden Default premise, per ADR 0001. It is recorded in the dependency graph and omitted from `why` output. A `cp` hint sets it to unknown.
- **Transistor currents**: separate quantities related by the transistor current law. This is a deliberate deviation from the memo, which aliases the emitter and collector currents.
- **`change` algorithm**:
  1. Retract the premise and, transitively, everything that depends on it: quantities, VARVALs and pending equations.
  2. Fill the premise with its new value.
  3. Wake every part that owned a retracted quantity, and every macro-element watching one.
  4. Propagate.
  5. Report only the quantities that were filled again.
  6. If propagation ends in a contradiction, report it as it stood at the failed check, then undo the whole change: the premise has its old value again and every retracted quantity, VARVAL and pending equation is back.
- **Formal variables**: named `V<n>` from one counter per session. Names will not match the memo's.
- **Contradictions**: a structured report listing the conflicting quantities and their justifications. The engine stops propagating. After `analyze` the state stays as it was before the failed check (its fills rest only on premises). A `change` or a `what` that ends in a contradiction is undone entirely; the report says so (`;CHANGE UNDONE: ...`, `;WHAT UNDONE: ... has no value`), since every fill a `what` makes rests on the formal variable it introduced, which `change` cannot retract.
- **Floating point**: Python floats. The memo's single-precision artifacts (e.g. `0.60000002`) are not reproduced.

## Testing Decisions

- **One seam: `Session`.** Every test drives `Session` with command text and inspects its structured results. Reader, Linear expressions, engine, laws and retraction are tested only through it. If a defect is hard to localize, a second seam at Linear expressions is the agreed fallback.
- **Good tests check external behaviour only**: the quantities filled, their values, their `why` trees, contradiction reports, load errors and rendered text. Never propagation order, internal data structures or private helpers.
- **Golden tests from the memo**: each example's wiring diagram, commands and expected transcript are stored exactly as printed in the memo. Expected output is parsed with the same reader and compared structurally:
  - Values: relative tolerance 1e-5. Expressions compare coefficient by coefficient.
  - Formal variables: equal up to a consistent renaming.
  - `why` trees: same law and the same set of antecedents per line. `DEFAULT` is treated as equal to `GIVEN`, and transistor-current-law steps are collapsed.
  - Order of fills: not compared.
  - Where a `why` tree differs because there are two valid derivations, decide case by case and record the decision in the test.
- **Golden fixtures**:
  - Example 3, the ladder: `analyze` prints nothing, then `what output voltage` gives 0.125.
  - Example 1, 4T-AMP: `analyze`, `why r3 current`, then `change r6 resistance 3200.0`.
  - Example 2, GR-58: `analyze` and `why output voltage`.
- **Non-golden tests at the same seam**:
  - each load-time check
  - contradiction reporting, e.g. giving a transistor's base and emitter voltages explicitly with a difference other than its VBE
  - the `what` fallback with pending equations
  - `change` refused on a non-premise
  - `change` on a Default
  - `why` on an unfilled quantity
  - a few exact rendered-text checks
- **Prior art**: none. This is the first code in the repo.
- **Milestones**: each one ends with its golden fixture passing.
  1. Ladder.
  2. Example 1 `analyze` and `why`.
  3. Example 1 `change`.
  4. Example 2.

## Out of Scope

- Everything in the memo's Extensions section:
  - capacitors and inductors
  - incremental and sinusoidal steady-state analysis
  - finite-beta perturbation as an automatic process (manual `change` of base current is in scope)
  - transistor model switching or reductio on contradiction
  - automatic recognition of voltage dividers or other macro-elements without hints
  - symmetry
  - Thevenin equivalents
  - differential pairs
  - solving simultaneous equations (pending equations are only stored)
- Test circuits for Figures 4, 5a and 6. They have no netlists or values; inventing them belongs to the extensions design session.
- Reproducing the memo's deduction order, formal-variable numbering, or single-precision float artifacts.
- Voltage-source elements (Figure 5a). EL models sources as nodes with fixed voltages.

## Further Notes

- **Errors in the memo**:
  - In Example 2, the prose swaps NODE3 and NODE4. The transcript is correct: NODE4, the NPN base, is OUTPUT + V10.
  - "Figure 3 with RE1=0" should read Figure 4.
  - Tests follow the transcripts in both cases.
- **Artifact of the transistor model**: in Example 1, Q1's currents come out exactly 0.0 because a Darlington's driving transistor feeds a zero base current. A faithful implementation reproduces this.
- **Aliasing in the memo**: evidence that the memo aliases emitter and collector currents includes `(Q2 CURRENT C) <= ((R4 CURRENT #1)) - KCL`, which is KCL at Q2's emitter node. This is why the golden comparator collapses transistor-current-law steps.
- **Later work**: the extensions get their own grilling session after milestone 4.
