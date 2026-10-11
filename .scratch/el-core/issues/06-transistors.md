# 06: Transistors

**What to build:** Wiring diagrams can declare transistors, and `analyze` deduces through them using EL's simple model: a fixed base-emitter drop in the active region and zero base current.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `transistor` clause with signed VBE (`.6` NPN Si, `-.6` PNP Si, magnitude `.3` Ge); VBE is a Given
- [ ] Terminals `b`, `e`, `c`, with currents into each terminal
- [ ] Base current is a Default of 0
- [ ] Operating region is a hidden Default premise of ACTIVE (ADR 0001): recorded as an antecedent of BE deductions, omitted from `why` output
- [ ] BE law relates base voltage, emitter voltage and VBE
- [ ] Transistor current law `Ie + Ib + Ic = 0` as separate quantities (not aliased)
- [ ] Load-time checks cover transistor terminals
- [ ] Demo test: a single-transistor circuit with a fixed base voltage analyzes fully, with correct signs for NPN and PNP
