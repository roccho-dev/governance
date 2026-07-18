package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const defaultNamespace = "roccho-dev/signed-promotion/v1"

type publicReceipt struct {
	Kind                       string `json:"kind"`
	Status                     string `json:"status"`
	Algorithm                  string `json:"algorithm"`
	Namespace                  string `json:"namespace"`
	PublicKeyHex               string `json:"publicKeyHex"`
	KeyID                      string `json:"keyId"`
	PrivateKeyStoredOutsideGit bool   `json:"privateKeyStoredOutsideGit"`
	PrivateKeyStoredInGitHub   bool   `json:"privateKeyStoredInGitHub"`
	Authority                  bool   `json:"authority"`
}

func cleanAbs(path string) (string, error) {
	if path == "" {
		return "", errors.New("empty-path")
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	return filepath.Clean(absolute), nil
}

func requireOutsideRepo(path, repoRoot string) error {
	cleanPath, err := cleanAbs(path)
	if err != nil {
		return err
	}
	cleanRoot, err := cleanAbs(repoRoot)
	if err != nil {
		return err
	}
	relative, err := filepath.Rel(cleanRoot, cleanPath)
	if err != nil {
		return err
	}
	if relative == "." || (!strings.HasPrefix(relative, ".."+string(filepath.Separator)) && relative != "..") {
		return errors.New("private-key-path-inside-repository")
	}
	return nil
}

func writeExclusive(path string, data []byte, mode os.FileMode) error {
	parent := filepath.Dir(path)
	if err := os.MkdirAll(parent, 0o700); err != nil {
		return err
	}
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, mode)
	if err != nil {
		if os.IsExist(err) {
			return errors.New("output-already-exists")
		}
		return err
	}
	defer file.Close()
	if _, err := file.Write(data); err != nil {
		return err
	}
	return file.Sync()
}

func generate(repoRoot, privatePath, publicReceiptPath, namespace string) (publicReceipt, error) {
	if namespace == "" {
		return publicReceipt{}, errors.New("empty-namespace")
	}
	if err := requireOutsideRepo(privatePath, repoRoot); err != nil {
		return publicReceipt{}, err
	}
	privateAbs, err := cleanAbs(privatePath)
	if err != nil {
		return publicReceipt{}, err
	}
	publicAbs, err := cleanAbs(publicReceiptPath)
	if err != nil {
		return publicReceipt{}, err
	}
	if privateAbs == publicAbs {
		return publicReceipt{}, errors.New("private-and-public-output-collide")
	}
	if _, err := os.Stat(privateAbs); err == nil {
		return publicReceipt{}, errors.New("output-already-exists")
	} else if !os.IsNotExist(err) {
		return publicReceipt{}, err
	}
	if _, err := os.Stat(publicAbs); err == nil {
		return publicReceipt{}, errors.New("output-already-exists")
	} else if !os.IsNotExist(err) {
		return publicReceipt{}, err
	}

	publicKey, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return publicReceipt{}, err
	}
	seed := privateKey.Seed()
	keyDigest := sha256.Sum256(publicKey)
	receipt := publicReceipt{
		Kind:                       "promotionPublisherPublicKeyReceipt.v1",
		Status:                     "pass",
		Algorithm:                  "Ed25519",
		Namespace:                  namespace,
		PublicKeyHex:               hex.EncodeToString(publicKey),
		KeyID:                      hex.EncodeToString(keyDigest[:]),
		PrivateKeyStoredOutsideGit: true,
		PrivateKeyStoredInGitHub:   false,
		Authority:                  false,
	}
	receiptBytes, err := json.Marshal(receipt)
	if err != nil {
		return publicReceipt{}, err
	}
	receiptBytes = append(receiptBytes, '\n')

	if err := writeExclusive(privateAbs, seed, 0o600); err != nil {
		return publicReceipt{}, err
	}
	if err := writeExclusive(publicAbs, receiptBytes, 0o644); err != nil {
		_ = os.Remove(privateAbs)
		return publicReceipt{}, err
	}
	return receipt, nil
}

func run(args []string) error {
	flags := flag.NewFlagSet("promotion-keygen", flag.ContinueOnError)
	repoRoot := flags.String("repo-root", "", "repository root used only to reject private-key placement")
	privatePath := flags.String("private-key-file", "", "new raw 32-byte Ed25519 seed outside Git")
	publicReceiptPath := flags.String("public-receipt", "", "new JSON receipt containing only public material")
	namespace := flags.String("namespace", defaultNamespace, "accepted promotion namespace")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *repoRoot == "" || *privatePath == "" || *publicReceiptPath == "" {
		return errors.New("missing-required-argument")
	}
	receipt, err := generate(*repoRoot, *privatePath, *publicReceiptPath, *namespace)
	if err != nil {
		return err
	}
	encoded, err := json.Marshal(receipt)
	if err != nil {
		return err
	}
	fmt.Println(string(encoded))
	return nil
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
