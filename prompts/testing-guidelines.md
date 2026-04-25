# Testing Guidelines

```
<role>
This is a testing reference included in implementer context. Follow these guidelines when writing and reviewing tests.
</role>

<context>
These guidelines exist because the most common test failures in code review are not missing tests — they are tests that pass without actually verifying anything. The rules below prevent that class of problem.
</context>

<instructions>
## Mock vs Real

Use this table to decide whether to mock a dependency or use the real one:

| Dependency | Approach |
|---|---|
| Internal utils | Real (never mock) |
| Database (test DB available) | Real (transaction rollback) |
| Database (no test DB) | Mock repository layer |
| External HTTP APIs | Mock (recorded responses) |
| File system | Real (temp dirs, cleanup after) |
| Time/dates | Inject clock |
| Random values | Inject seed |
| Env vars | Set in setup, restore in teardown |
</instructions>

<constraints>
## Anti-Patterns

Avoid these patterns. Each one is listed with the reason it causes problems.

1. **Testing mocks instead of behavior** — Asserting that a mock was called with specific arguments only proves your code talks to the mock, not that the system produces correct output. Verify system output instead.

2. **Test-only methods** — Adding public methods solely for test access bloats the API surface and couples tests to internals. Test through the public API; if that is difficult, the design likely needs adjustment.

3. **Tautological tests** — Mocking the function under test makes the test pass regardless of implementation. The test asserts nothing about real behavior.

4. **Over-mocking** — Mocking internal dependencies makes tests brittle to refactors and hides integration bugs. Mock only at system boundaries (external APIs, third-party services). Use real implementations for internal code.

5. **Snapshot abuse** — Asserting against entire HTML or JSON blobs makes tests fragile to irrelevant changes. Assert specific properties that matter to the behavior under test.

6. **Testing implementation details** — Asserting on internal state, private method calls, or execution order ties tests to the current implementation. Test observable behavior: given these inputs, expect these outputs.

7. **Skipping failure verification** — A test that was never seen to fail may be tautological or misconfigured. Every test must be observed in its failing (red) state before trusting its passing (green) state.
</constraints>

<verification>
When reviewing tests, check:
- [ ] Each test was seen to fail before passing
- [ ] Tests verify observable outputs, not mock interactions
- [ ] Mocks are only used at system boundaries (see Mock vs Real table)
- [ ] No test-only methods were added to production code
- [ ] Assertions target specific properties, not full snapshots
</verification>
```
