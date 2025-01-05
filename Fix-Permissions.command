#!/bin/bash
echo "Starting to remove quarantine attributes from .app files..."
# Loop through all .app files in the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
for app in "$DIR"/*.app; do
    if [ -e "$app" ]; then
        echo "Removing quarantine from: $app"
        xattr -dr com.apple.quarantine "$app"
    else
        echo "No .app files found in the directory."
    fi
done
echo "Process completed. Press Enter to exit."
read
