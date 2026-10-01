"""Editable example. This is a uniform-range Monte Carlo heuristic, not a solver."""
from simulation.sdk import Action, Observation
from utils.cards import equity


def decide(obs: Observation, params: dict, rng) -> Action:
    samples = int(params.get("equity_samples", 80))
    if not 1 <= samples <= 100000: raise ValueError("equity_samples must be 1–100000")
    share = equity(obs.hole_cards, obs.board, max(1, len(obs.opponents)), samples, rng)
    legal = obs.legal_actions
    price = legal.call_amount / max(1, obs.pot + legal.call_amount)
    bluff = rng.random() < float(params.get("bluff_frequency", 0.02))
    if "raise" in legal.types and (share >= float(params.get("raise_equity", 0.65)) or (bluff and price < 0.15)):
        current_wager = obs.hero.street_bet + legal.to_call
        increment = int((obs.pot + legal.call_amount) * float(params.get("bet_fraction", 0.6)))
        target = max(legal.min_raise_to, min(legal.max_raise_to, current_wager + increment))
        return Action("raise", target)
    if "check" in legal.types: return Action("check")
    if share >= price + float(params.get("call_margin", 0.02)): return Action("call")
    return Action("fold")
