SHELL := /bin/bash

ifeq ($(OS),Windows_NT)
  VENV_BIN := venv/Scripts
  PY := $(VENV_BIN)/python.exe
else
  VENV_BIN := venv/bin
  PY := $(VENV_BIN)/python
endif

.PHONY: setup build module clean help

# ---- setup --------------------------------------------------------------
setup:
	bash ./setup.sh

# ---- build --------------------------------------------------------------
build: setup
	bash ./build.sh

# ---- module package -----------------------------------------------------
module: build
	cp dist/archive.tar.gz module.tar.gz
	@echo "Module package created: module.tar.gz"

# ---- clean --------------------------------------------------------------
clean:
	rm -rf .pkg build dist *.spec module.tar.gz venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ---- help ---------------------------------------------------------------
help:
	@echo "Available targets:"
	@echo "  setup   - Create venv and install dependencies"
	@echo "  build   - Build PyInstaller binary and create archive"
	@echo "  module  - Copy archive to module.tar.gz"
	@echo "  clean   - Remove build artifacts and venv"
