# Testing Guidelines

## TDD Cycle
1. Write ONE failing test > 2. Confirm FAILS for right reason > 3. Minimal code to pass > 4. Confirm PASSES > 5. Refactor > 6. Repeat

Never skip step 2. A test that never failed never proved it catches bugs.

## Anti-Patterns
1. **Testing mocks** — verify system output, not that mock was called with args
2. **Test-only methods** — test through public API; if you can't, redesign
3. **Tautological tests** — mocking the function under test; passes regardless of implementation
4. **Over-mocking** — mock only at system boundaries (external APIs), use real internal deps
5. **Snapshot abuse** — assert specific properties, not entire HTML/JSON blobs
6. **Implementation details** — test observable behavior (inputs > outputs), not internals
7. **No failure verification** — every test must be seen to fail before passing

## Mock vs Real

| Dependency | Approach |
|---|---|
| Internal utils | Real (never mock) |
| Database (test DB) | Real (transaction rollback) |
| Database (no test DB) | Mock repository layer |
| External HTTP APIs | Mock (recorded responses) |
| File system | Real (temp dirs, cleanup) |
| Time/dates | Inject clock |
| Random values | Inject seed |
| Env vars | Set in setup, restore in teardown |
