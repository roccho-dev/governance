package main

import (
	"example.com/passclean/adapters/memory"
	"example.com/passclean/core/action"
)

func main() {
	store := &memory.Store{}
	_ = action.Service{Store: store}
}
