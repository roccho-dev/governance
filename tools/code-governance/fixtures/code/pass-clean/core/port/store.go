package port

import "example.com/passclean/core/data"

type Store interface {
	Save(data.Item) error
}
