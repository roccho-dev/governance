# package closure handoff fixture

This fixture note marks the handoff packet selftest scope.

`tools/build-package-closure-handoff.py selftest` uses the package responsibility closure fixture to prove:

- unclosed package drift is not called pass;
- every work order receives owner routing;
- every work order receives required proof rows;
- every blocking work order returns a residual;
- handoff packet outputs are deterministic.
