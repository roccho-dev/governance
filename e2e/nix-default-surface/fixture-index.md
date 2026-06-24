# Fixture index

This directory records the intended pass and fail cases for the Nix default surface checker.

Pass cases:

- no implicit package default
- default run app points to help
- help explains build, run, check, devShells, and authority boundary

Fail cases:

- implicit package default is introduced
- default run app no longer points to help
- help stops explaining the public flake surface
- help presents generated text as decision authority
- help depends on non-explicit state
