# Using EL

EL reads commands as S-expressions on standard input and prints one result per command, followed by a blank line. The commands are the memo's: `wire`, `analyze`, `what`, `why`, `change`. Terms used here (premise, Given, Default, supposition, formal variable, hint, macro-element) are defined in `GLOSSARY.md`.

## Running

```sh
uv run el                          # interactive: type commands, Ctrl-C or Ctrl-D to quit
uv run el < circuit.el             # batch: run a file of commands
uv run python -m el                # same as `el`
```

A command may span several lines; EL waits until the parentheses balance, then runs it. The `.el` files under `tests/memo/` are memo transcripts (commands interleaved with expected output), not plain command files; copy the command forms out of them to run them.

From Python:

```python
from el import Session

session = Session()
for result in session.run(text):   # one Result per top-level form
    print(result.render())
```

## Reader syntax

- Symbols are case-insensitive and printed upper case: `r1` is `R1`.
- `;` starts a comment running to end of line.
- `'x` reads as `(quote x)`; `(analyze 'amp)` and `(analyze amp)` are the same.
- Numbers: integers (`370000`), decimals (`.6`, `-.6`, `2.7`), exponents (`1.1E-3`).

## Wiring diagram: `wire`

```lisp
(wire NAME clause...)
```

Clauses, in any order, each may appear more than once:

| Clause | Entries | Meaning |
|---|---|---|
| `(node e...)` | `name` or `(name volts)` | Declare named nodes. A node with a voltage is fixed (a supply rail or ground); KCL does not apply to it. |
| `(resistor (name ohms)...)` | | Resistors, terminals `#1` and `#2`. |
| `(transistor (name vbe)...)` | | Bipolar transistors, terminals `B`, `E`, `C`. `vbe` is signed: positive for NPN, negative for PNP (`.6` silicon, `.3` germanium). |
| `(connect c...)` | `(node (term elem)...)` or `((term elem)...)` | Each entry is one node and the terminals joined at it. A leading symbol names a declared node; without one the node is anonymous and is named `NODE1`, `NODE2`, ... in `connect` order. |
| `(hint h...)` | `(vd r-top r-bottom)`, `(cp q-a q-b)` | Designer intent; see below. |

A terminal is written `(terminal element)`, e.g. `(#1 r1)`, `(b q1)`.

Hints:

- `(vd R1 R2)`: R1 and R2 form a voltage divider (two resistors sharing exactly one node). Once both resistances and both end voltages are known, the midpoint voltage is filled with a formal variable, solved later by a consistency check, so a loaded divider still comes out right.
- `(cp QA QB)`: a complementary pair, one NPN and one PNP whose emitters meet at a common node (directly, or each through one resistor). Their bases are assumed to sit symmetrically about that node. Their operating region becomes unknown, so the BE law deduces nothing for them.

Example (memo Example 1):

```lisp
(wire 4t-amp
 (node (vcc 15) (gnd 0) input output)
 (transistor (q1 .6) (q2 .6) (q3 .6) (q4 .6))
 (resistor (r1 370000) (r2 100000) (r3 10000) (r4 1800)
           (r5 5600) (r6 3900) (r7 6800))
 (connect
  (vcc (#1 r1) (#1 r3) (#1 r5) (c q4))
  (gnd (#2 r2) (#2 r4) (#2 r6) (#2 r7))
  (input (#2 r1) (#1 r2) (b q1))
  ((#2 r3) (c q1) (c q2) (b q3))          ;NODE1
  ((e q1) (b q2))                         ;NODE2
  ((e q2) (#1 r4))                        ;NODE3
  ((#2 r5) (c q3) (b q4))                 ;NODE4
  ((e q3) (#1 r6))                        ;NODE5
  (output (e q4) (#1 r7)))
 (hint (vd r1 r2)))
```

On success EL prints `DONE`. Loading the same name again replaces the circuit. A rejected diagram changes nothing and lists every problem found:

```
;ERROR: wiring diagram BAD rejected
;  (#2 R9) names undeclared element R9
;  element R3 is declared but never connected
```

Load-time checks: undeclared node or element, unknown terminal, declared part never connected, terminal connected to two nodes, element with some terminals unconnected, malformed `vd` or `cp` hint.

## Quantities

Commands other than `wire` and `analyze` name a quantity of the current circuit (the one last analyzed) as `part kind [label]`:

| Part | Quantity | Premise? |
|---|---|---|
| node | `VOLTAGE` | Given if declared with a voltage |
| resistor | `RESISTANCE` | Given |
| resistor | `CURRENT ME`, `CURRENT #1`, `CURRENT #2`; bare `CURRENT` means `ME` | no. `ME` and `#1` are the current into `#1`; `#2` is the same quantity negated |
| transistor | `VBE` | Given |
| transistor | `CURRENT B` | Default 0 |
| transistor | `CURRENT E`, `CURRENT C` | no |
| transistor | `REGION` | Default `ACTIVE`, or `UNKNOWN` under a `cp` hint |

All terminal currents are currents *into* the terminal. `REGION` is the transistor's operating region (ADR 0001). It is hidden: it never appears in fills or as an antecedent in `why` trees, but `(why q1 region)` shows it, and `change` refuses to touch it.

## Laws

| Law | Part | Relation |
|---|---|---|
| `OHM` | resistor | V(#1) - V(#2) = R * I(ME) |
| `BE` | transistor | V(B) - V(E) = VBE, only while the region is ACTIVE |
| `TRANSISTOR` | transistor | I(B) + I(E) + I(C) = 0 |
| `KCL` | non-fixed node | currents into the node sum to 0 |
| `VD-DEMON` | `vd` hint | introduces a formal variable at the divider midpoint |
| `CP-OFFSET`, `CP` | `cp` hint | NPN base = mid + X, PNP base = mid - X, X a formal variable |

A law with exactly one unfilled quantity fills it. A law with all quantities filled is a consistency check: it may solve a formal variable, or report a contradiction.

## Commands

### `(analyze 'NAME)`

Makes NAME the current circuit and propagates from its premises. Prints every quantity filled, in fill order, then `DONE`:

```
(analyze '4t-amp)

(Q1 CURRENT E 0.0)
(Q1 CURRENT C 0.0)
(INPUT VOLTAGE V1)
(R1 CURRENT ME (&+ 4.054054054054054E-5 (&* -2.7027027027027026E-6 V1)))
(R2 CURRENT #1 (&+ 4.054054054054054E-5 (&* -2.7027027027027026E-6 V1)))
(V1 VARVAL 3.1914893617021276)
(NODE2 VOLTAGE 2.5914893617021275)
(NODE3 VOLTAGE 1.9914893617021274)
(R4 CURRENT ME 1.1063829787234041E-3)
...
(OUTPUT VOLTAGE 9.609601745771958)
(R7 CURRENT ME 1.4131767273194056E-3)
(Q4 CURRENT E -1.4131767273194056E-3)
(Q4 CURRENT C 1.4131767273194056E-3)
DONE
```

Here the `vd` hint put formal variable `V1` at INPUT. Values computed from INPUT stay expressions in `V1` until the OHM check on R2 solves it (`V1 VARVAL`). Later fills use the solved value. A value printed as an expression is printed as it was stored, so it does not change once the variable is solved.

The memo prints fewer digits and does not print transistor `C` currents (it treats them as `E` with the sign flipped). EL keeps them as separate quantities tied by the TRANSISTOR law.

A circuit with nothing to deduce prints just `DONE` (e.g. a resistor ladder with no hint; use `what`).

### `(what part kind [label])`

Prints the quantity's value. If it has none, EL supposes it: fills it with a fresh formal variable, propagates, and prints those fills, a blank line, then the answer with solved variables substituted:

```
(what output voltage)

(OUTPUT VOLTAGE V1)
(R6 CURRENT ME V1)
(R5 CURRENT #2 (&* -1.0 V1))
(NODE2 VOLTAGE (&* 2.0 V1))
(R4 CURRENT ME V1)
(R3 CURRENT #2 (&* -2.0 V1))
(NODE1 VOLTAGE (&* 4.0 V1))
(R1 CURRENT ME (&+ 1.0 (&* -4.0 V1)))
(R2 CURRENT #1 (&+ 1.0 (&* -6.0 V1)))
(V1 VARVAL 0.125)

0.125
```

Asking again prints just `0.125`. The quantity keeps `V1` as its value and `why` shows it as a supposition: `((OUTPUT VOLTAGE) WHAT)`.

If the answer is still an expression, the pending equations in its variables follow it, one per line, as `(EXPR = 0 - LAW)`. EL does not solve simultaneous equations, so two variables tied only to each other stay pending:

```
V1
((&+ -2.0 (&* 26.0 V1) (&* -5.0 V2)) = 0 - OHM)
((&+ (&* 2.0 V2) (&* -2.0 V1)) = 0 - OHM)
```

A `what` that leads to a contradiction is undone.

### `(why part kind [label])`

Prints the justification tree of a filled quantity, breadth first, ending in `QED`. Each line is one of:

```
((Q) <= ((A) (B) ...) - LAW)   ; deduced by LAW from antecedents A, B, ...
((Q) GIVEN)                    ; premise from the wiring diagram
((Q) DEFAULT)                  ; premise from a component model, e.g. zero base current
((Q) WHAT)                     ; supposition made by `what`
```

Formal-variable solutions appear as `(Vn VARVAL)`. An unfilled quantity prints `(Q) has no value`. Example, after the `analyze` above:

```
(why r4 current)

((R4 CURRENT) <= ((NODE3 VOLTAGE) (GND VOLTAGE) (R4 RESISTANCE)) - OHM)
((NODE3 VOLTAGE) <= ((NODE2 VOLTAGE) (Q2 VBE)) - BE)
((GND VOLTAGE) GIVEN)
((R4 RESISTANCE) GIVEN)
((NODE2 VOLTAGE) <= ((INPUT VOLTAGE) (Q1 VBE) (V1 VARVAL)) - BE)
((Q2 VBE) GIVEN)
((INPUT VOLTAGE) <= ((R1 RESISTANCE) (R2 RESISTANCE) (VCC VOLTAGE) (GND VOLTAGE)) - VD-DEMON)
((Q1 VBE) GIVEN)
((V1 VARVAL) <= ((INPUT VOLTAGE) (GND VOLTAGE) (R2 RESISTANCE) (R2 CURRENT ME)) - OHM)
((R1 RESISTANCE) GIVEN)
((R2 RESISTANCE) GIVEN)
((VCC VOLTAGE) GIVEN)
((R2 CURRENT ME) <= ((R1 CURRENT #2) (Q1 CURRENT B)) - KCL)
((R1 CURRENT #2) <= ((VCC VOLTAGE) (INPUT VOLTAGE) (R1 RESISTANCE)) - OHM)
((Q1 CURRENT B) DEFAULT)
QED
```

Each quantity appears once, under the name the first law that read it used for it. Each BE step also reads the transistor's `REGION`, but hidden antecedents are recorded without being printed.

### `(change part kind [label] value)`

Replaces a premise (Given or Default) and re-deduces only what depended on it. Prints the new premise and the re-filled quantities, then `DONE`:

```
(change r6 resistance 3200.0)

(R6 RESISTANCE 3200.0)
(R6 CURRENT ME 1.042553191489362E-3)
(Q3 CURRENT E -1.042553191489362E-3)
(Q3 CURRENT C 1.042553191489362E-3)
(R5 CURRENT #2 -1.042553191489362E-3)
(NODE4 VOLTAGE 9.161702127659574)
(OUTPUT VOLTAGE 8.561702127659574)
(R7 CURRENT ME 1.2590738423028786E-3)
(Q4 CURRENT E -1.2590738423028786E-3)
(Q4 CURRENT C 1.2590738423028786E-3)
DONE
```

The input stage (`V1`, NODE1 to NODE3) does not depend on R6, so it is not recomputed.

Refusals:

```
;ERROR: (NODE1 VOLTAGE) is not a premise: it is deduced by OHM; only Givens and Defaults can change
;ERROR: (Q1 REGION) is an operating region; switching transistor models is not supported
```

A supposition made by `what` cannot be changed either. A change that leads to a contradiction is undone.

## Output reference

Values:

- Numbers in [0.1, 1e8) and zero print plain (`2.5914893617021275`); others in exponent form (`1.1063829787234041E-3`). Both use the fewest digits that read back as the same float.
- Formal variables are `V1`, `V2`, ..., numbered per session.
- Linear expressions: `V1`, `(&* -2.0 V1)`, `(&+ 1.0 (&* -4.0 V1))` (constant first, then terms).

A fill line is `(part kind [label] value)`; a solved formal variable is `(Vn VARVAL value)`.

Contradiction (a check whose quantities disagree): the fills made before it, then the law, then each conflicting quantity with its value and indented `why` tree:

```
(wire clash
  (node (vcc 10) (base 2) (emit 1))
  (transistor (q1 .6))
  (resistor (r1 1000))
  (connect (vcc (#1 r1)) (base (b q1)) (emit (e q1)) ((c q1) (#2 r1))))
(analyze 'clash)

;CONTRADICTION: law BE does not hold
(BASE VOLTAGE 2.0)
  ((BASE VOLTAGE) GIVEN)
(EMIT VOLTAGE 1.0)
  ((EMIT VOLTAGE) GIVEN)
(Q1 VBE 0.6)
  ((Q1 VBE) GIVEN)
```

After `analyze`, fills made before the contradiction are kept. After `change` or `what`, everything is rolled back and a last line says so, e.g. `;CHANGE UNDONE: (BASE VOLTAGE) is still 2.0` or `;WHAT UNDONE: (BASE VOLTAGE) has no value`.

Other errors print as `;ERROR: message`, e.g. `unknown command FROB`, `no circuit analyzed yet`, `4T-AMP has no quantity (R9 CURRENT)`. Input that ends inside an unfinished form is dropped without a message.
