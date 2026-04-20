---
name: pymupdf-scanned-pdf-ocr
description: Use when PyMuPDF extracts zero text from old scanned PDFs — OCR workaround for Italian/Romanian docs
---

pymupdf extracts zero or near-zero text from old scanned PDFs (Italian/Romanian legal docs, contracts, tax forms), leaving downstream LLM processing with nothing to work on.

Built 2026-04-10 for the LLM-Wiki ingestion pipeline (~/Claude/LLM-Wiki/bin/extract.py + llm_extract.py + notes_write.py). Key insight: post-OCR regex cleanup alone isn't enough for old scans; Haiku-curated clean_excerpts (with strict no-invention rules) deliver much better previews, and honest fallback to `[]` prevents hallucination on truly unreadable docs.

Solution: Install tesseract language packs directly (see tessdata direct-download procedure): `curl -sL https://github.com/tesseract-ocr/tessdata_fast/raw/main/ron.traineddata -o /opt/homebrew/share/tessdata/ron.traineddata`; In the PDF extractor, check if pymupdf's text layer returned < 50 meaningful (non-whitespace) characters; If below threshold, call pymupdf's built-in OCR: `page.get_textpage_ocr(language='ron+eng+ita+fra+spa+deu', dpi=300, full=True)` then `page.get_text('text', textpage=tp)`
