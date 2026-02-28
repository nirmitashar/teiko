VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

.PHONY: setup pipeline dashboard

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

pipeline:
	$(PYTHON) load_data.py
	$(PYTHON) run_analysis.py

dashboard:
	STREAMLIT_BROWSER_GATHER_USAGE_STATS=false $(VENV)/bin/streamlit run app.py --server.headless true
