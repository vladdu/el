# 03: Load-time checks for nodes and resistors

**What to build:** A malformed wiring diagram is rejected at `wire` time with a clear message, and never reaches analysis.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Error when a connection names a part that was never declared
- [ ] Error when a declared part is never connected
- [ ] Error when a terminal appears in two connections
- [ ] Error when a terminal is left unconnected
- [ ] Errors are structured results from `Session` and render as readable text
- [ ] A rejected wiring diagram leaves any existing circuit of that name untouched
