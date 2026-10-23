.PHONY: install data train evaluate test serve package

install:
	python -m pip install -r requirements.lock
	python -m pip install -e '.[dev]'

data:
	python scripts/download_data.py

train:
	python scripts/train.py

evaluate:
	python scripts/evaluate.py

test:
	python -m pytest -q

serve:
	python scripts/serve.py

package:
	python scripts/package_release.py
