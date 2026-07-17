package action

import (
	"errors"
	"example.com/passclean/core/calculation"
	"example.com/passclean/core/data"
	"example.com/passclean/core/port"
)

type Service struct {
	Store port.Store
}

func (s Service) Add(item data.Item) error {
	if calculation.Total([]data.Item{item}) < 0 {
		return errors.New("negative total")
	}
	return s.Store.Save(item)
}
