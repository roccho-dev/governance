package memory

import "example.com/passclean/core/data"

type Store struct {
	Items []data.Item
}

func (s *Store) Save(item data.Item) error {
	s.Items = append(s.Items, item)
	return nil
}
