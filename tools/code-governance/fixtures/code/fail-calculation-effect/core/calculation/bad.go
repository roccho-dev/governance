package calculation

import fileapi "os"

func Persist(value []byte) error {
	return fileapi.WriteFile("result.txt", value, 0o644)
}
