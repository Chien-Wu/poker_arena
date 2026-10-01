"""Command-line entry point: python -m simulation --help."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .config import Config,Entry,GameConfig,ExecutionConfig,override
from .registry import Registry,ROOT
from .tournament import Tournament
from .experiments import repeat,sweep
from .report import render_report
from .replay import verify_file
from .scaffold import create_bot
from .game import play_game
from utils.io import atomic_json


def status(manifest,registry):
    if not manifest['id'].startswith('up_'):return 'native_ready'
    directory=registry.root/manifest['id']/'code'
    if manifest['runtime']=='command':return 'ready' if (directory/'handler').is_file() else 'build_required'
    return 'source_extract_ready' if (directory/'upstream'/'receipt.json').is_file() else 'source_install_required'


def progress(event):
    if event['type']=='round_finished':
        print('Round',event['round']['round'],'points:',json.dumps(event['round']['cumulative_points']),flush=True)


def load_config(args):
    config=Config.load(args.config)
    expressions=list(args.set or [])
    for key,path in [('hands','game.hands_per_game'),('rounds','tournament.rounds'),
                     ('seed','seed'),('runner','execution.runner')]:
        value=getattr(args,key,None)
        if value is not None:expressions.append(f'{path}={json.dumps(value)}')
    return override(config,expressions)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline poker bot arena: strict observations, configurable NLHE, and rank-points tournaments.')
    parser.add_argument('--bots-root',type=Path,default=ROOT/'bots')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('run','batch','sweep'):
        p=sub.add_parser(name)
        p.add_argument('--config','-c',type=Path,default=ROOT/'configs/quickstart.json')
        p.add_argument('--out',type=Path,required=True)
        p.add_argument('--set',action='append',default=[],metavar='PATH=VALUE')
        p.add_argument('--hands',type=int);p.add_argument('--rounds',type=int);p.add_argument('--seed',type=int)
        p.add_argument('--runner',choices=['inprocess','subprocess','docker']);p.add_argument('--quiet',action='store_true')
        if name!='run':p.add_argument('--iterations',type=int,default=10)
        if name=='batch':p.add_argument('--resume',action='store_true')
        if name=='sweep':p.add_argument('--grid',type=Path,required=True)
    p=sub.add_parser('list-bots');p.add_argument('--json',action='store_true')
    p=sub.add_parser('new-bot');p.add_argument('id');p.add_argument('--name')
    p=sub.add_parser('replay');p.add_argument('file',type=Path)
    p=sub.add_parser('report');p.add_argument('directory',type=Path)
    p=sub.add_parser('validate-bot')
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--bot');g.add_argument('--all-upstreams',action='store_true')
    p.add_argument('--hands',type=int,default=20);p.add_argument('--players',type=int,default=2)
    p.add_argument('--seed',type=int,default=20261002);p.add_argument('--params',default='{}')
    p.add_argument('--runner',choices=['inprocess','subprocess','docker'],default='subprocess')
    p.add_argument('--out',type=Path)
    args=parser.parse_args(argv)
    registry=Registry(args.bots_root)
    try:
        if args.command=='list-bots':
            rows=[{**m,'installation_status':status(m,registry)} for m in registry.list()]
            if args.json:print(json.dumps(rows,indent=2))
            else:
                for m in rows:print(f"{m['id']:24} {m['capabilities']['min_players']}-{m['capabilities']['max_players']} seats  {m['installation_status']:24} {m['name']}")
        elif args.command=='new-bot':print(create_bot(registry.root,args.id,args.name))
        elif args.command=='replay':print(json.dumps({'verified_hands':verify_file(args.file)}))
        elif args.command=='report':print(render_report(args.directory))
        elif args.command=='validate-bot':
            bots=[m['id'] for m in registry.list() if m['id'].startswith('up_')] if args.all_upstreams else [args.bot]
            records=[]
            params=json.loads(args.params)
            for bot_id in bots:
                entries=[Entry('candidate',bot_id,params)]+[Entry(f'opponent_{i}','random_bot') for i in range(1,args.players)]
                result=play_game(entries,f'validate:{bot_id}',game=GameConfig(hands_per_game=args.hands),
                    execution=ExecutionConfig(runner=args.runner,failure_policy='abort'),seed=args.seed,registry=registry)
                row={'bot':bot_id,**result}
                if bot_id.startswith('up_') and result['stats']['candidate']['upstream_calls']==0:
                    raise RuntimeError(f'{bot_id}: no actual source-policy decision was exercised')
                records.append(row)
                print(bot_id,json.dumps(result['stats']['candidate']),flush=True)
            if args.out:atomic_json(args.out,{'integrations':len(records),'results':records})
        else:
            config=load_config(args)
            callback=None if args.quiet else progress
            if args.command=='run':
                result=Tournament(config,registry=registry,output=args.out,progress=callback).run()
                render_report(args.out)
                print(json.dumps({'status':result['status'],'qualifier_games':result['qualifier_games'],
                    'tiebreak_games':result['tiebreak_games'],'total_hands':result['total_hands'],
                    'leaderboard':result['leaderboard'],'report':str(args.out/'report.html')},indent=2))
            elif args.command=='batch':
                # A null seed is resolved once on first launch. On resume recover it
                # from the original experiment, never generate a new master seed.
                if args.resume and config.seed is None:
                    config.seed=json.loads((args.out/'experiment.json').read_text())['config']['seed']
                print(json.dumps(repeat(config,args.iterations,args.out,registry=registry,progress=callback,resume=args.resume),indent=2))
            else:
                grid=json.loads(args.grid.read_text())
                records=sweep(config,grid,args.iterations,args.out,registry=registry,progress=callback)
                print(json.dumps({'variants':len(records),'index':str(args.out/'sweep.json')}))
    except (Exception,KeyboardInterrupt) as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr)
        return 130 if isinstance(exc,KeyboardInterrupt) else 1
    return 0

if __name__=='__main__':raise SystemExit(main())
