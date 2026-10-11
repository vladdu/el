# 11: Pending equations and the `what` fallback

**What to build:** Consistency checks that leave more than one formal variable unsolved no longer lose information, and `what` returns a partial answer instead of failing when it can't solve.

**Blocked by:** 05, 08

**Status:** resolved

- [ ] An equation from a consistency check with more than one unsolved formal variable is stored as a pending equation
- [ ] A pending equation is retried whenever one of its variables is solved, and solves the last variable when only one remains
- [ ] `change` retracts pending equations that depend on the changed premise
- [ ] `what` that cannot solve its formal variable returns the expression plus the pending equations involved
- [ ] Memo examples still pass unchanged
- [ ] Demo test: a circuit that leaves two coupled formal variables after `what`
