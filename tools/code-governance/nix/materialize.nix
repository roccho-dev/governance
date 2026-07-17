{ packet }:
builtins.toFile "code-governance-semantic-v1.json" (builtins.readFile packet)
