"""Offline HTML results; no network assets or embedded third-party scripts."""
import html
import json
from pathlib import Path


def render_report(directory):
    directory = Path(directory)
    data = json.loads((directory / "summary.json").read_text())
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in
                  ("rank", "player_id", "bot", "points", "qualifier_net_chips", "decisions", "failures", "adapter_repairs"))
                  + "</tr>" for row in data["leaderboard"])
    text = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Poker Arena results</title>
<style>body{{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 24px;line-height:1.5}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #ddd}}
pre{{white-space:pre-wrap}}small{{color:#555}}</style><h1>Poker Arena</h1>
<p>Status: <b>{html.escape(data['status'])}</b> · {data['qualifier_games']} qualifier games ·
{data['tiebreak_games']} playoff games · {data['total_hands']} hands</p>
<p>Ranking uses round-placement points, not cumulative chip profit. Adapter repairs are reported separately from bot failures.</p>
<table><thead><tr><th>Rank</th><th>Entry</th><th>Policy</th><th>Points</th><th>Net chips</th><th>Decisions</th><th>Failures</th><th>Repairs</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Configuration</h2><pre>{html.escape(json.dumps(data['config'], indent=2))}</pre>
<p><small>Private replay journals contain the full deck. Never mount them into bot containers.</small></p></html>'''
    path = directory / "report.html"
    path.write_text(text)
    return path
