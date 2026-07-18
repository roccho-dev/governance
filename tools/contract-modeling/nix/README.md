# Nix materialization

`materialize.nix` copies the provider-neutral semantic packet into an immutable
store object and emits its SHA-256 digest. It consumes no GitHub metadata and
creates no effect outside the Nix store.
