package main

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestGenerateCreatesExternalRawSeedAndPublicReceipt(t *testing.T) {
	root := t.TempDir()
	repo := filepath.Join(root, "repo")
	owner := filepath.Join(root, "owner")
	if err := os.MkdirAll(repo, 0o755); err != nil {
		t.Fatal(err)
	}
	privatePath := filepath.Join(owner, "publisher.seed")
	publicPath := filepath.Join(owner, "publisher-public.json")
	receipt, err := generate(repo, privatePath, publicPath, defaultNamespace)
	if err != nil {
		t.Fatal(err)
	}
	seed, err := os.ReadFile(privatePath)
	if err != nil {
		t.Fatal(err)
	}
	if len(seed) != ed25519.SeedSize {
		t.Fatalf("seed length = %d", len(seed))
	}
	info, err := os.Stat(privatePath)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("private mode = %o", info.Mode().Perm())
	}
	publicKey := ed25519.NewKeyFromSeed(seed).Public().(ed25519.PublicKey)
	if receipt.PublicKeyHex != hex.EncodeToString(publicKey) {
		t.Fatal("public key mismatch")
	}
	digest := sha256.Sum256(publicKey)
	if receipt.KeyID != hex.EncodeToString(digest[:]) {
		t.Fatal("key id mismatch")
	}
	encoded, err := os.ReadFile(publicPath)
	if err != nil {
		t.Fatal(err)
	}
	var decoded publicReceipt
	if err := json.Unmarshal(encoded, &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded != receipt {
		t.Fatal("receipt readback mismatch")
	}
	if strings.Contains(string(encoded), privatePath) || strings.Contains(string(encoded), hex.EncodeToString(seed)) {
		t.Fatal("public receipt leaked private material")
	}
}

func TestGenerateRejectsPrivateKeyInsideRepository(t *testing.T) {
	root := t.TempDir()
	repo := filepath.Join(root, "repo")
	if err := os.MkdirAll(repo, 0o755); err != nil {
		t.Fatal(err)
	}
	_, err := generate(repo, filepath.Join(repo, "publisher.seed"), filepath.Join(root, "public.json"), defaultNamespace)
	if err == nil || err.Error() != "private-key-path-inside-repository" {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestGenerateRejectsOverwriteAndRemovesPartialSeed(t *testing.T) {
	root := t.TempDir()
	repo := filepath.Join(root, "repo")
	owner := filepath.Join(root, "owner")
	if err := os.MkdirAll(repo, 0o755); err != nil {
		t.Fatal(err)
	}
	privatePath := filepath.Join(owner, "publisher.seed")
	publicPath := filepath.Join(owner, "publisher-public.json")
	if _, err := generate(repo, privatePath, publicPath, defaultNamespace); err != nil {
		t.Fatal(err)
	}
	if _, err := generate(repo, privatePath, filepath.Join(owner, "second-public.json"), defaultNamespace); err == nil || err.Error() != "output-already-exists" {
		t.Fatalf("private overwrite error: %v", err)
	}

	otherPrivate := filepath.Join(owner, "other.seed")
	existingPublic := filepath.Join(owner, "existing-public.json")
	if err := os.WriteFile(existingPublic, []byte("existing"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := generate(repo, otherPrivate, existingPublic, defaultNamespace); err == nil || err.Error() != "output-already-exists" {
		t.Fatalf("public overwrite error: %v", err)
	}
	if _, err := os.Stat(otherPrivate); !os.IsNotExist(err) {
		t.Fatalf("partial private seed remains: %v", err)
	}
}

func TestGenerateRejectsCollidingOutputsAndEmptyNamespace(t *testing.T) {
	root := t.TempDir()
	repo := filepath.Join(root, "repo")
	outside := filepath.Join(root, "owner", "same")
	if err := os.MkdirAll(repo, 0o755); err != nil {
		t.Fatal(err)
	}
	if _, err := generate(repo, outside, outside, defaultNamespace); err == nil || err.Error() != "private-and-public-output-collide" {
		t.Fatalf("collision error: %v", err)
	}
	if _, err := generate(repo, filepath.Join(root, "owner", "seed"), filepath.Join(root, "owner", "public"), ""); err == nil || err.Error() != "empty-namespace" {
		t.Fatalf("namespace error: %v", err)
	}
}
