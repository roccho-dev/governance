# Proposal: hq autocomplete quality gates

## Goal

Define the first governance gate shape for hq autocomplete quality.

## Candidate gates

| gate | purpose |
|---|---|
| no false positive key | do not suggest keys outside schema/context |
| no false negative required key | suggest missing required keys |
| compile draft required | every suggestion has a compile draft |
| accept before queue | unaccepted suggestions never enter queue |
| reproducible preview | preview HTML comes from real CLI/REPL output |

## Status

Proposal only. Do not force globally until hq local tests are stable.
