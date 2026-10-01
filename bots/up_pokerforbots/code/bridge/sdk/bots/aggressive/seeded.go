// Arena-owned deterministic constructor. The fetched handler.go is unmodified.
package aggressive
import rand "math/rand/v2"
func NewSeeded(first uint64, second uint64) *Handler {
    return &Handler{rng: rand.New(rand.NewPCG(first, second))}
}
