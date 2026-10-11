# 07: `vd` macro-element: Example 1 `analyze` and `why` golden (milestone 2)

**What to build:** The memo's 4T-AMP wiring diagram with its `(vd r1 r2)` hint, pasted verbatim, analyzes to the memo's values, and `(why r3 current)` produces the memo's explanation.

**Blocked by:** 04, 05, 06

**Status:** resolved

- [ ] `hint` clause with `vd` creates a voltage-divider macro-element
- [ ] Load-time check: `vd` must name two resistors sharing a node
- [ ] When both end voltages of the divider are filled, VD-DEMON fills the midpoint voltage with a fresh formal variable (not the divider formula), so loaded dividers come out correctly
- [ ] Golden comparator collapses transistor-current-law steps when matching `why` trees against the memo
- [ ] Golden test: Example 1 `analyze` output matches (including Q1's 0.0 currents)
- [ ] Golden test: Example 1 `why r3 current` matches
