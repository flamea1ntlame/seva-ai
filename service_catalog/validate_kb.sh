#!/bin/bash
set -e

echo "Validating schemas..."
# We can add jsonschema validation here if needed, but for now we rely on the python tests

echo "Running knowledge base validation tests..."
./backend/venv/bin/pytest -q tests/knowledge_base/test_kb_validation.py
