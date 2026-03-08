#!/bin/bash
# PDF Bleed Trimmer — Mac App Builder
# Double-click this file to build PDF Bleed Trimmer.app

cd "$(dirname "$0")"

echo "========================================"
echo "  PDF Bleed Trimmer — App Builder"
echo "========================================"
echo

# Find the Python installation that has pdfrw (the main dependency)
PYTHON=""
for py in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null && "$py" -c "import pdfrw" 2>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Could not find a Python with pdfrw installed."
    echo
    echo "Fix: open Terminal and run:"
    echo "  pip3 install pdfrw"
    echo
    read -p "Press Enter to close..."
    exit 1
fi

echo "Python: $($PYTHON --version) — $(command -v $PYTHON)"
echo

# Install py2app if not present
if ! "$PYTHON" -c "import py2app" 2>/dev/null; then
    echo "Installing py2app..."
    "$PYTHON" -m pip install py2app
    echo
fi

# Clean previous build artefacts
echo "Cleaning previous build..."
rm -rf build dist
echo

# Build
echo "Building app (this takes a minute)..."
echo "----------------------------------------"
"$PYTHON" setup.py py2app 2>&1
echo "----------------------------------------"
echo

if [ -d "dist/PDF Bleed Trimmer.app" ]; then
    echo "✓ Build succeeded!"
    echo
    echo "  App location: $(pwd)/dist/PDF Bleed Trimmer.app"
    echo
    echo "  To install: drag 'PDF Bleed Trimmer.app' into your Applications folder."
    echo
    echo "  Note: drag-and-drop inside the app window requires tkinterdnd2."
    echo "  If drag-and-drop doesn't work, click the drop zone to use"
    echo "  the file picker instead — that always works."
    echo
    open dist/
else
    echo "✗ Build failed. See the output above for details."
    echo
    echo "Common fixes:"
    echo "  • Make sure setup.py is in the same folder as this script"
    echo "  • Try: $PYTHON -m pip install --upgrade py2app"
    echo
fi

read -p "Press Enter to close..."
