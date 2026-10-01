"""Repeatable experiments, parameter sweeps, and completed-iteration resume."""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import statistics
from .config import Config, override
from .registry import Registry
from .tournament import Tournament
from .report import render_report
from utils.io import atomic_json
from utils.randomness import derive_seed


def aggregate(summaries: list[dict]) -> list[dict]:
    """Aggregate independent tournaments. Points/ranks are not cash-game EV."""
    by_player={}
    for result in summaries:
        for row in result['leaderboard']:
            by_player.setdefault(row['player_id'],[]).append(row)
    rows=[]
    for player,values in by_player.items():
        points=[v['points'] for v in values]
        rows.append({'player_id':player,'bot':values[0]['bot'],'iterations':len(values),
                     'mean_points':statistics.mean(points),
                     'points_stdev':statistics.stdev(points) if len(points)>1 else 0.0,
                     'mean_rank':statistics.mean(v['rank'] for v in values),
                     'mean_qualifier_net_chips':statistics.mean(v['qualifier_net_chips'] for v in values),
                     'failures':sum(v['failures'] for v in values),
                     'timeouts':sum(v['timeouts'] for v in values)})
    return sorted(rows,key=lambda row:(-row['mean_points'],row['player_id']))


def repeat(config:Config,iterations:int,output:Path|str,*,registry=None,progress=None,resume=False):
    if type(iterations) is not int or iterations<1:raise ValueError('iterations must be a positive integer')
    output=Path(output)
    registry=registry or Registry()
    spec_path=output/'experiment.json'
    config=config.resolved()
    fingerprints={p.bot:registry.fingerprint(p.bot) for p in config.players}
    spec={'schema_version':1,'config':config.to_dict(),'iterations':iterations,'bot_fingerprints':fingerprints}
    if resume:
        if not spec_path.exists():raise ValueError('No experiment.json to resume')
        old=json.loads(spec_path.read_text())
        if old!=spec:raise ValueError('Resume requires identical resolved config, iteration count, and bot code hashes')
    else:
        output.mkdir(parents=True,exist_ok=False)
        atomic_json(spec_path,spec)
    results=[]
    for i in range(iterations):
        run_config=Config.from_dict(config.to_dict())
        run_config.seed=derive_seed(config.seed,'experiment_iteration',i)
        directory=output/f'iteration_{i+1:04d}'
        complete=directory/'summary.json'
        if resume and complete.exists():
            result=json.loads(complete.read_text())
            if result['config']!=run_config.to_dict():raise ValueError(f'Unexpected completed config at {directory}')
        else:
            if directory.exists():
                # Preserve all interrupted logs, rather than deleting evidence.
                suffix=1
                while directory.with_name(directory.name+f'.interrupted.{suffix}').exists():suffix+=1
                directory.rename(directory.with_name(directory.name+f'.interrupted.{suffix}'))
            result=Tournament(run_config,registry=registry,output=directory,progress=progress).run()
            render_report(directory)
        results.append(result)
        atomic_json(output/'progress.json',{'completed_iterations':len(results),'iterations':iterations})
        atomic_json(output/'aggregate.json',{'schema_version':1,'master_seed':config.seed,
                    'completed_iterations':len(results),'rows':aggregate(results)})
    return {'schema_version':1,'master_seed':config.seed,'completed_iterations':len(results),'rows':aggregate(results)}


def sweep(config:Config,grid:dict[str,list],iterations:int,output:Path|str,*,registry=None,progress=None):
    if not grid or any(not isinstance(v,list) or not v for v in grid.values()):
        raise ValueError('Grid must map dotted config paths to nonempty lists')
    config=config.resolved()
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    keys=list(grid)
    records=[]
    for index,values in enumerate(itertools.product(*(grid[k] for k in keys))):
        params=dict(zip(keys,values))
        variant=override(config,[f'{k}={json.dumps(v)}' for k,v in params.items()])
        # Same experiment seed stream for every variant. Regrouping and bust-outs
        # can still change subsequent opponents and deals; this is not duplicate poker.
        directory=output/f'variant_{index+1:04d}'
        result=repeat(variant,iterations,directory,registry=registry,progress=progress)
        records.append({'variant':index+1,'parameters':params,'directory':directory.name,**result})
        atomic_json(output/'sweep.json',{'schema_version':1,'grid':grid,'variants':records})
    return records
