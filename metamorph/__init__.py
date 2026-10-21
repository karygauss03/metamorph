"""Metamorph: drag-and-drop file converter for Linux (X11)."""

import warnings

# pdf2docx still imports PyMuPDF under its legacy "fitz" name.
warnings.filterwarnings("ignore", message="The `fitz` API is deprecated")

__version__ = "1.0.0"
