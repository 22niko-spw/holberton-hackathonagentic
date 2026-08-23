.PHONY: eval test

eval:
	.venv/bin/python3 eval/run_eval.py

test:
	.venv/bin/python3 -m pytest tests/ -v
