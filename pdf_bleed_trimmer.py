#!/usr/bin/env python3
"""
PDF Bleed Trimmer
Drag a PDF onto the window to remove 4mm bleeds from all sides.
Output is saved as A3-0mm-gr.pdf in the same directory as the input.
"""

import os
import sys
import tkinter as tk

import pdfrw

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


BLEED_MM = 4
MM_TO_PT = 72 / 25.4
BLEED_PT = BLEED_MM * MM_TO_PT
OUTPUT_FILENAME = "A3-0mm-gr.pdf"

# Colours (Catppuccin-inspired dark theme)
BG_COLOR = "#1e1e2e"
ZONE_COLOR = "#2a2a3e"
ZONE_BORDER = "#6c6cff"
TEXT_COLOR = "#cdd6f4"
ACCENT_COLOR = "#89b4fa"
SUCCESS_COLOR = "#a6e3a1"
ERROR_COLOR = "#f38ba8"
MUTED_COLOR = "#585b70"


def _parse_rect(rect_obj):
    """Return (left, bottom, right, top) as floats from a pdfrw array."""
    return tuple(float(v) for v in rect_obj)


def trim_bleed(input_path: str) -> str:
    reader = pdfrw.PdfReader(input_path)

    for page in reader.pages:
        # Resolve MediaBox (may be inherited from parent)
        mb = page.MediaBox
        if mb is None:
            raise ValueError("Could not read MediaBox from page.")

        left, bottom, right, top = _parse_rect(mb)
        new_left   = left   + BLEED_PT
        new_bottom = bottom + BLEED_PT
        new_right  = right  - BLEED_PT
        new_top    = top    - BLEED_PT

        if new_right <= new_left or new_top <= new_bottom:
            raise ValueError(
                f"Page is too small to trim {BLEED_MM}mm bleeds "
                f"(page: {right - left:.1f} x {top - bottom:.1f} pt)."
            )

        new_box = pdfrw.PdfArray([
            pdfrw.PdfObject(str(round(new_left,   4))),
            pdfrw.PdfObject(str(round(new_bottom, 4))),
            pdfrw.PdfObject(str(round(new_right,  4))),
            pdfrw.PdfObject(str(round(new_top,    4))),
        ])

        page.MediaBox = new_box
        page.CropBox  = new_box
        # Remove any boxes that could override the new MediaBox
        page.TrimBox  = None
        page.BleedBox = None
        page.ArtBox   = None

    output_dir = os.path.dirname(os.path.abspath(input_path))
    output_path = os.path.join(output_dir, OUTPUT_FILENAME)

    pdfrw.PdfWriter(output_path, trailer=reader).write()
    return output_path


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def _reset_zone(drop_zone):
    drop_zone.config(bg=ZONE_COLOR, highlightbackground=ZONE_BORDER)


def process_file(path: str, status_label: tk.Label, drop_zone: tk.Label):
    # tkinterdnd2 wraps paths containing spaces in curly braces
    path = path.strip().strip("{}")

    if not path.lower().endswith(".pdf"):
        status_label.config(text="Error: Please drop a PDF file.", fg=ERROR_COLOR)
        drop_zone.config(highlightbackground=ERROR_COLOR)
        return

    if not os.path.isfile(path):
        status_label.config(text=f"Error: File not found:\n{path}", fg=ERROR_COLOR)
        drop_zone.config(highlightbackground=ERROR_COLOR)
        return

    filename = os.path.basename(path)
    status_label.config(text=f"Processing {filename}…", fg=MUTED_COLOR)
    drop_zone.update_idletasks()

    try:
        output_path = trim_bleed(path)
        out_dir = os.path.dirname(output_path)
        status_label.config(
            text=(
                f"Saved as:\n{OUTPUT_FILENAME}\n\n"
                f"{out_dir}"
            ),
            fg=SUCCESS_COLOR,
        )
        drop_zone.config(highlightbackground=SUCCESS_COLOR)
    except Exception as exc:
        status_label.config(text=f"Error: {exc}", fg=ERROR_COLOR)
        drop_zone.config(highlightbackground=ERROR_COLOR)


def on_drop(event, status_label, drop_zone):
    _reset_zone(drop_zone)
    process_file(event.data, status_label, drop_zone)


def build_ui():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("PDF Bleed Trimmer")
    root.configure(bg=BG_COLOR)
    root.resizable(False, False)

    # ---- Title ----
    tk.Label(
        root,
        text="PDF Bleed Trimmer",
        font=("Helvetica", 18, "bold"),
        bg=BG_COLOR,
        fg=TEXT_COLOR,
    ).pack(pady=(24, 2))

    tk.Label(
        root,
        text=f"Removes {BLEED_MM}mm bleed from all sides  ·  Saves as {OUTPUT_FILENAME}",
        font=("Helvetica", 10),
        bg=BG_COLOR,
        fg=MUTED_COLOR,
    ).pack(pady=(0, 16))

    # ---- Drop zone ----
    drop_zone_text = (
        "Drop PDF here"
        if DND_AVAILABLE
        else "Click to select PDF\n(install tkinterdnd2 for drag-and-drop)"
    )
    drop_zone = tk.Label(
        root,
        text=drop_zone_text,
        font=("Helvetica", 16),
        bg=ZONE_COLOR,
        fg=ACCENT_COLOR,
        width=36,
        height=8,
        relief="flat",
        highlightthickness=2,
        highlightbackground=ZONE_BORDER,
        cursor="hand2",
    )
    drop_zone.pack(padx=32, pady=8)

    # ---- Status ----
    status_label = tk.Label(
        root,
        text="Waiting for a PDF file…",
        font=("Helvetica", 11),
        bg=BG_COLOR,
        fg=MUTED_COLOR,
        wraplength=360,
        justify="center",
    )
    status_label.pack(pady=(8, 24))

    if DND_AVAILABLE:
        drop_zone.drop_target_register(DND_FILES)
        drop_zone.dnd_bind(
            "<<Drop>>",
            lambda e: on_drop(e, status_label, drop_zone),
        )
        drop_zone.dnd_bind(
            "<<DragEnter>>",
            lambda e: drop_zone.config(bg="#3a3a5e", highlightbackground=ACCENT_COLOR),
        )
        drop_zone.dnd_bind(
            "<<DragLeave>>",
            lambda e: _reset_zone(drop_zone),
        )
    else:
        from tkinter import filedialog

        def click_open(_event=None):
            path = filedialog.askopenfilename(
                title="Select a PDF file",
                filetypes=[("PDF files", "*.pdf")],
            )
            if path:
                process_file(path, status_label, drop_zone)

        drop_zone.bind("<Button-1>", click_open)

    # macOS: handle files dropped onto the .app icon in Finder
    def _open_document(*paths):
        for p in paths:
            process_file(p, status_label, drop_zone)
            break  # process only first file dropped at once

    root.createcommand("::tk::mac::OpenDocument", _open_document)

    # macOS: if launched with a file argument (e.g. via open -a App file.pdf)
    if len(sys.argv) == 2 and sys.argv[1].lower().endswith(".pdf"):
        root.after(100, lambda: process_file(sys.argv[1], status_label, drop_zone))

    # Centre on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.mainloop()


if __name__ == "__main__":
    build_ui()
