# README train boundary regression checks proposal

## Why

The README artifact train is complete, so the most useful next guard is a small set of regression checks that prevent boundary backsliding. A broad DD or closure implementation is out of scope for this train.

## Direction

Add governance-side fixtures or checks for the four highest-risk boundary regressions.

## Required regressions

1. raw ADR rows must not be treated as direct README authority input;
2. README artifacts must not be treated as accepted authority;
3. gov-lib must not render Markdown bytes;
4. gov-lib must not upload or own artifact lifecycle.

## Boundary

These checks protect the completed train. They do not implement DD view, transfer view, runtime receipts, or closureView.

## Merge Gate

Merge only if each regression has a failing fixture or check plan and the failure reason is explicit.