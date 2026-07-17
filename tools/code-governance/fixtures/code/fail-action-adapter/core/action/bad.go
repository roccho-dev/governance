package action

import "example.com/failactionadapter/adapters/memory"

func Build() memory.Store {
	return memory.Store{}
}
