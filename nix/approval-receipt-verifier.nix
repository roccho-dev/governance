{ pkgs ? import <nixpkgs> {} }:

pkgs.writeShellApplication {
  name = "approval-receipt-verifier";
  runtimeInputs = [ pkgs.python3 ];
  text = ''
    exec ${pkgs.python3}/bin/python3 ${../tools/approval-receipt-verifier.py} "$@"
  '';
}
