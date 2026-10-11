# 02: Numeric propagation over resistors and nodes

**What to build:** `analyze` on a resistor circuit with fixed node voltages deduces every quantity reachable by local one-step deductions (OHM, KCL) and prints each fill in memo form. Introduces the golden-test value comparator.

**Blocked by:** 01

**Status:** resolved

- [ ] Parts (nodes, resistors) own quantities; filling a quantity wakes the parts that own it via an explicit FIFO queue; propagation runs until the queue is empty
- [ ] OHM law on resistors and KCL on nodes fill the last unfilled quantity when all others are filled
- [ ] Fixed node voltages and resistances are Given premises
- [ ] Terminal currents are currents *into* the terminal; `ME` is the current into a resistor's `#1`
- [ ] Fills print as e.g. `(R4 CURRENT ME 1.1E-3)` / `(NODE2 VOLTAGE 2.59)`
- [ ] Golden comparator: parses expected transcript text with the reader; compares values with relative tolerance 1e-5; ignores order
- [ ] Demo test: a resistor chain between fixed nodes where every quantity is step-by-step deducible analyzes fully
