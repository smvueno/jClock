#!/bin/bash
set -e
if [ -f package.json ]; then
  npm install
elif [ -f requirements.txt ]; then
  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
elif [ -f Gemfile ]; then
  bundle install
elif [ -f go.mod ]; then
  go mod download
elif [ -f Cargo.toml ]; then
  cargo fetch
fi
