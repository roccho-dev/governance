# 260611 webmcp lossless renderer proposal

## Decision target

Adopt this board surface path:

```text
board-view.ir.v1 -> webmcp :8787 -> renderer-for-html
```

## Authority rule

- `governance` records remain the authority.
- `board-view.ir.v1` is the composed read model.
- `webmcp` is a read-only host, query router, and lossless index.
- `renderer-for-html` is a projection only.
- `:8087` is allowed only as a mirror of the same artifact.

## Blocked paths

- rendering the board from `webmcp.organizationGraph.ir.v1`
- `data.html` repo/specs direct scan as canonical board path
- HTML as state
- separate 8787/8087 board data sources

## Required checks

- webmcp query returns unchanged `board-view.ir.v1`
- HTML embeds the full `board-view.ir.v1` for parity checking
- sourceRefs/state/typed edges survive query and render paths
