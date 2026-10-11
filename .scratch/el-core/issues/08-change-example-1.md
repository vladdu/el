# 08: `change` with retraction: Example 1 change golden (milestone 3)

**What to build:** `(change r6 resistance 3200.0)` after analyzing 4T-AMP forgets exactly what depended on the old value, rededuces it, and prints the memo's output.

**Blocked by:** 07

**Status:** resolved

- [ ] Every fill records the quantities that depend on it
- [ ] `change`: retract the premise and transitively everything depending on it (quantities, VARVALs); fill the new value; wake every part that owned a retracted quantity and every macro-element watching one; propagate
- [ ] Output lists the new premise and only the quantities filled again
- [ ] `change` works on Defaults (e.g. a transistor's base current) as well as Givens
- [ ] `change` on a quantity that is not a premise is refused with an explanation
- [ ] Golden test: Example 1 `change r6 resistance 3200.0` transcript matches
