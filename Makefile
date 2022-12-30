run: fmt lint
	python3 mug.py

fmt:
	isort --profile black -l 79 mug.py
	black -l 79 mug.py

lint:
	flake8 mug.py

.PHONY: fmt run lint
