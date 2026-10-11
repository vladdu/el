# 04: `why` explanations

**What to build:** `(why <part> <quantity> [terminal])` prints the justification tree of a filled quantity in the memo's format, so any result can be audited.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Every fill records its Justification: the law and its antecedents; premises have no antecedents
- [ ] `why` prints one line per quantity: `((Q) <= (antecedents) - LAW)`, premises as `GIVEN` (user) or `DEFAULT` (component model), ending with `QED`
- [ ] `why` on an unfilled quantity says so plainly
- [ ] `why` acts on the current circuit (most recently analyzed)
- [ ] Why-tree comparator for golden tests: same law and same antecedent set per line; consistent renaming of formal variables; `DEFAULT` treated as equal to `GIVEN`
- [ ] Demo test on the ticket 02 resistor chain
