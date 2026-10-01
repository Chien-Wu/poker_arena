.PHONY: test demo sources validate-upstreams exhaustive

test:
	python -m pytest -q

demo:
	python -m simulation run -c configs/quickstart.json --out results/demo

sources:
	python tools/fetch_upstreams.py --all

validate-upstreams:
	python -m simulation validate-bot --all-upstreams --hands 20

exhaustive:
	python tools/verify_evaluator.py --out results/evaluator.json
