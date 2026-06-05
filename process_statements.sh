#!/bin/bash

# Navigate to the directory where this script is located
cd "$(dirname "$0")"

# Activate the virtual environment
source venv/bin/activate

# Run ScanFiler on all files in Downloads starting with "View PDF Statement"
# (Remove the --dry-run flag when you are ready to actually move the files)
python scanfiler.py --dry-run ~/Downloads/"View PDF Statement"*
