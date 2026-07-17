module example.com/failunused

go 1.23.2

require example.com/unused v0.0.0

replace example.com/unused => ./unusedmod
