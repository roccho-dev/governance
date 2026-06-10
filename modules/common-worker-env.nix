{ pkgs ? import <nixpkgs> {} }:
{
  requiredTools = [ pkgs.bash pkgs.python3 pkgs.git pkgs.zip pkgs.unzip ];
}
