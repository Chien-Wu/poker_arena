"""Run from the repository root: python examples/iterative_experiment.py."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simulation.config import Config,override
from simulation.tournament import Tournament
from simulation.report import render_report

base=Config.load('configs/quickstart.json')
for threshold in (0.55,0.65,0.75):
    config=override(base,[f'players.0.params.raise_equity={threshold}',
                          'game.hands_per_game=25','tournament.rounds=4'])
    out=Path('results')/f'threshold_{threshold:.2f}'
    result=Tournament(config,output=out).run()
    print(threshold,result['leaderboard'])
    render_report(out)
