package calculation

import "example.com/passclean/core/data"

func Total(items []data.Item) int {
	total := 0
	for _, item := range items {
		total += item.Price
	}
	return total
}
