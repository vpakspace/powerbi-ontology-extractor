#!/bin/bash
# Run Visual Ontology Editor
# Usage: ./run_editor.sh

cd "$(dirname "$0")"
streamlit run ontology_editor.py --server.port 8503
