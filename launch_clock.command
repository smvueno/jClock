#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate venv and launch clock
cd "$DIR"
source venv/bin/activate

# Launch in background and exit terminal
nohup python main.py --background > /dev/null 2>&1 &

# Small delay to ensure process starts
sleep 1

# Close terminal window
osascript -e 'tell application "Terminal" to close (every window whose name contains ".command")' &
exit
