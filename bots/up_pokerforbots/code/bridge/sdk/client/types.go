package client

type GameState struct{}
// The pinned handler's method signature is independently exercised by main.go.
// Handler here is an embedding point, not the full upstream network client.
type Handler interface{}
