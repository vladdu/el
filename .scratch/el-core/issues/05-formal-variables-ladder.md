# 05: Formal variables and wishful thinking: ladder golden (milestone 1)

**What to build:** `(what output voltage)` on the ladder introduces a formal variable, propagates its consequences, solves it by a consistency check, and returns 0.125, matching Example 3 of the memo.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Linear expressions: constant plus coefficients over formal variables; exact add/subtract/scale; rendered in memo `&+`/`&*` form
- [ ] Laws compute with expressions, not just numbers
- [ ] A law whose quantities are all filled runs a consistency check; if exactly one formal variable is unsolved, it solves it and fills its VARVAL (printed e.g. `(V3 VARVAL 0.125)`)
- [ ] When a law reads a quantity, known formal-variable values are substituted in and each one used is recorded as an antecedent; stored expressions are not rewritten
- [ ] Formal variables named `V<n>` from a per-session counter
- [ ] `what` returns a filled quantity's value directly; on an unfilled quantity it introduces a formal variable (printed e.g. `(OUTPUT VOLTAGE V3)`), propagates, and returns the solved value
- [ ] Golden test: Example 3 transcript (`analyze` then `what output voltage`) matches under the agreed comparison rules
