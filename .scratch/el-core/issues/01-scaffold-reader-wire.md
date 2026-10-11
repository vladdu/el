# 01: Project scaffold, reader, `wire` and a no-op `analyze`

**What to build:** A runnable project and REPL where a user can paste a resistor-only wiring diagram in the memo's syntax, get `DONE`, then `analyze` it and get `DONE` with nothing filled. This is the skeleton every later ticket extends. See spec `.scratch/el-core/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [ ] Python 3.14 project managed by uv, built with hatchling, src layout, package `el`; ruff and pytest configured; no runtime dependencies
- [ ] A `Session` accepts command text and returns structured results that render to memo-style text; a REPL loop runs on top of it
- [ ] The reader is case-insensitive, strips `;` comments, and parses numbers in the memo's forms (`.6`, `-.6`, `370000`, `2.7`, `0.0`)
- [ ] `wire` accepts `node` (with optional fixed voltages), `resistor` and `connect` clauses and answers `DONE`
- [ ] Unnamed nodes are named NODE1, NODE2, ... in `connect` order
- [ ] Re-wiring under an existing name replaces the circuit
- [ ] The Example 3 (ladder) wiring diagram, pasted verbatim, loads; `(analyze 'ladder)` prints nothing and answers `DONE`
- [ ] Tests go through `Session` only
