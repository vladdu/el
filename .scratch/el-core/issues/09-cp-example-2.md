# 09: `cp` macro-element: Example 2 golden (milestone 4)

**What to build:** The memo's GR-58 wiring diagram with `(vd r130 r131)` and `(cp q107 q108)`, pasted verbatim, analyzes to the memo's values (including V10), and `(why output voltage)` produces the memo's explanation.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] `cp` hint creates a complementary-pair macro-element
- [ ] Load-time check: `cp` must name one NPN and one PNP whose emitters reach a common node
- [ ] When any one of the two base voltages or the midpoint node voltage is filled, the macro-element fills the other two symmetrically using a fresh formal variable (NPN base = midpoint + X, PNP base = midpoint - X)
- [ ] `cp` sets both transistors' operating region to unknown, so no BE deduction is made for them
- [ ] Golden test: Example 2 `analyze` output matches (follow the transcript, not the prose, which swaps NODE3/NODE4)
- [ ] Golden test: Example 2 `why output voltage` matches
