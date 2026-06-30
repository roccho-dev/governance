# Package obligation and claim parser fixture work order

## Purpose

Create the first governance core PR for ADRS #100 and ADRS #101.

This PR is the TDD entry point: it should define fixture expectations before the validator grows.

## Scope

Add work-order guidance for:

- ADRS package obligation parser
- feature package claim parser
- fixture format for red and green cases
- initial diagnostics: `target-universe-unknown`, `obligation-missing`, `package-id-missing`, `claim-missing`

## Inputs

- ADRS package obligations
- feature package claims
- target universe records

## Outputs

- parsed obligations
- parsed claims
- fixture diagnostic report

## Required fixtures

| fixture | expected diagnostic |
|---|---|
| purpose reset without target universe | `target-universe-unknown` |
| universe without package obligation | `obligation-missing` |
| package obligation without package_id | `package-id-missing` |
| obligation without feature claim | `claim-missing` |
| adopted claim with valid required fields | `ok` |

## Non-goals

- Do not build all diagnostics here.
- Do not wire all-repo blocking CI here.
- Do not require feature repos to adopt validators in this PR.
- Do not make governance an authority for ADRS meaning.

## Acceptance

The future implementation should fail fixtures for the expected reasons and pass the minimal valid fixture.
