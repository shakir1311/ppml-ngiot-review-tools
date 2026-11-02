"""PDF Text Extractor: the full text of PDF papers, verified by several engines and local OCR, with sections, figures and tables."""
import os

__version__ = "1.1.1"
os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")     # PyMuPDF's hint about an add-on for layout is not wanted here
