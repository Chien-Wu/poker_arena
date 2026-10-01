// Minimal compatibility types for the pinned aggressive Handler only.
// This is NOT a replacement implementation of the PokerForBots server or SDK.
package protocol

type ActionRequest struct {
    ValidActions []string
    MinBet int
}
type HandStart struct{}
type GameUpdate struct{}
type PlayerAction struct{}
type StreetChange struct{}
type HandResult struct{}
type GameCompleted struct{}
