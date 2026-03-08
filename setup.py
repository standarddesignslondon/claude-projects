"""
py2app build configuration for PDF Bleed Trimmer.

Usage:
    python setup.py py2app

Or just double-click build-app.command
"""

from setuptools import setup

APP = ["pdf_bleed_trimmer.py"]
DATA_FILES = []
OPTIONS = {
    # False is required for tkinter apps — True breaks the event loop
    "argv_emulation": False,
    "packages": ["pdfrw", "tkinterdnd2"],
    "includes": ["tkinter", "tkinter.filedialog"],
    "plist": {
        "CFBundleName": "PDF Bleed Trimmer",
        "CFBundleDisplayName": "PDF Bleed Trimmer",
        "CFBundleIdentifier": "com.standarddesignslondon.pdfbleedtrimmer",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        # Allows the app to accept dropped files on its Dock icon
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "PDF Document",
                "CFBundleTypeExtensions": ["pdf"],
                "CFBundleTypeRole": "Viewer",
            }
        ],
    },
}

setup(
    name="PDF Bleed Trimmer",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
