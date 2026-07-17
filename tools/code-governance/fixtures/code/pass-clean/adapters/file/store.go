package file

import (
	"example.com/passclean/core/data"
	"os"
)

type Store struct {
	Path string
}

func (s Store) Save(item data.Item) error {
	return os.WriteFile(s.Path, []byte{byte(item.Price)}, 0o644)
}
