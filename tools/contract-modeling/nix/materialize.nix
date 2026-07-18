{ pkgs, semanticPacket }:

pkgs.runCommand "contract-modeling-semantic-packet" {
  nativeBuildInputs = [ pkgs.coreutils ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  cp ${semanticPacket} "$out/semantic-packet.json"
  sha256sum "$out/semantic-packet.json" | cut -d' ' -f1 > "$out/semantic-packet.sha256"
  test -s "$out/semantic-packet.json"
  test -s "$out/semantic-packet.sha256"
''
