{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python312;
in
pkgs.writeShellApplication {
  name = "approval-receipt-verifier";
  runtimeInputs = [ python ];
  text = ''
    exec ${python}/bin/python3 ${../tools/approval-receipt-verifier.py} "$@"
  '';
}
