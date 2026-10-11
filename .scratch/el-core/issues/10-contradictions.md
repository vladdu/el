# 10: Contradiction reports

**What to build:** When a law finds all its quantities filled and they disagree, EL reports the contradiction with explanations instead of continuing or failing silently.

**Blocked by:** 04, 06

**Status:** resolved

- [ ] A failed consistency check produces a structured contradiction report naming the conflicting quantities and including the justification of each
- [ ] Propagation stops; circuit state is left as it was before the failed check
- [ ] The user can then `change` a premise to resolve it (once ticket 08 lands; not required for this ticket's tests)
- [ ] Demo test: the memo's BE example: transistor base and emitter voltages given explicitly with a difference other than its VBE
