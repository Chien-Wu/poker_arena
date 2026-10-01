// JSON-lines adapter around an unmodified, separately fetched Go policy.
package main
import (
    "bufio"
    "encoding/json"
    "fmt"
    "math/big"
    "os"
    "github.com/lox/pokerforbots/v2/protocol"
    "github.com/lox/pokerforbots/v2/sdk/bots/aggressive"
    "github.com/lox/pokerforbots/v2/sdk/client"
)

type Request struct {
    ID int `json:"request_id"`
    Method string `json:"method"`
    Data json.RawMessage `json:"data"`
}
type Observation struct {
    Legal struct {
        Types []string `json:"types"`
        MinRaiseTo *int `json:"min_raise_to"`
        ToCall int `json:"to_call"`
    } `json:"legal_actions"`
}
func main() {
    scanner := bufio.NewScanner(os.Stdin)
    scanner.Buffer(make([]byte, 65536), 8*1024*1024)
    out := json.NewEncoder(os.Stdout)
    var policy *aggressive.Handler
    calls := 0
    for scanner.Scan() {
        var req Request
        if err := json.Unmarshal(scanner.Bytes(), &req); err != nil {
            fmt.Fprintln(os.Stderr, err); os.Exit(2)
        }
        response := map[string]interface{}{"request_id": req.ID, "ok": true}
        switch req.Method {
        case "initialize":
            var d struct {Seed json.RawMessage `json:"seed"`}
            if err := json.Unmarshal(req.Data, &d); err != nil { panic(err) }
            seed, valid := new(big.Int).SetString(string(d.Seed), 10)
            if !valid { panic("seed must be an integer") }
            low := seed.Uint64()
            high := new(big.Int).Rsh(new(big.Int).Set(seed),64).Uint64()
            policy = aggressive.NewSeeded(low, high)
        case "act":
            if policy == nil { panic("initialize first") }
            var obs Observation
            if err := json.Unmarshal(req.Data, &obs); err != nil { panic(err) }
            legal := make([]string, 0, len(obs.Legal.Types))
            for _, action := range obs.Legal.Types {
                if action == "check" { action = "call" }
                legal = append(legal, action)
            }
            minimum := 0
            if obs.Legal.MinRaiseTo != nil { minimum = *obs.Legal.MinRaiseTo }
            kind, amount, err := policy.OnActionRequest(&client.GameState{}, protocol.ActionRequest{ValidActions:legal, MinBet:minimum})
            if err != nil { response["error"] = err.Error(); break }
            calls++
            if kind == "call" && obs.Legal.ToCall == 0 { kind = "check" }
            action := map[string]interface{}{"type":kind}
            if kind == "raise" { action["raise_to"] = amount }
            response["action"] = action
            response["telemetry"] = map[string]int{"upstream_calls":calls,"adapter_repairs":0}
        case "close":
            out.Encode(response); return
        case "on_game_start", "on_hand_start", "on_event", "on_hand_end", "on_game_end":
            // All corresponding methods in the selected upstream handler are no-ops.
        default:
            response["error"] = "unknown method"
        }
        if err := out.Encode(response); err != nil { os.Exit(2) }
    }
    if err := scanner.Err(); err != nil {fmt.Fprintln(os.Stderr,err); os.Exit(2)}
}
