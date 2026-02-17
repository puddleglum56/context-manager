#!/bin/bash

VENV_DIR="venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    echo "Installing dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt
else
    source "$VENV_DIR/bin/activate"
fi

echo "Starting Claude Interface..."
python3 main.py