"""
Malayalam PDF → RAG-Ready Text Pipeline
========================================
Converts large batches of Malayalam PDFs into chunked, cleaned Unicode text
suitable for ingestion into vector databases (FAISS, Chroma, Pinecone).

Pipeline per PDF:
  PDF → page images (300 DPI) → Malayalam OCR → clean text → RAG chunks → JSON

Usage:
    python pipeline/pdf_content_pipeline.py                        # defaults
    python pipeline/pdf_content_pipeline.py --input ./input/pdfs --output ./output/rag_chunks
    python pipeline/pdf_content_pipeline.py --workers 8 --dpi 300 --chunk-size 500
"""

import argparse
import json
import logging
import multiprocessing
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Optional

from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from tqdm import tqdm

from text_cleaning import normalize_ocr_text

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mal_pipeline")

# ---------------------------------------------------------------------------
# Auto-detect bundled Poppler on Windows
# ---------------------------------------------------------------------------
POPPLER_PATH: Optional[str] = None

if sys.platform == "win32":
    # Point pytesseract to the Tesseract install location on Windows
    _tesseract_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if _tesseract_exe.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(_tesseract_exe)

    # Look for poppler bundled next to this script
    _script_dir = Path(__file__).resolve().parent
    _project_root = _script_dir.parent
    _candidates = [
        _project_root / "tools" / "poppler-24.08.0" / "Library" / "bin",
        _project_root / "poppler" / "poppler-24.08.0" / "Library" / "bin",
        _project_root / "poppler" / "Library" / "bin",
        _project_root / "poppler" / "bin",
        _project_root / "poppler",
        _script_dir / "tools" / "poppler-24.08.0" / "Library" / "bin",
        _script_dir / "poppler" / "poppler-24.08.0" / "Library" / "bin",
        _script_dir / "poppler" / "Library" / "bin",
        _script_dir / "poppler" / "bin",
        _script_dir / "poppler",
    ]
    for _p in _candidates:
        if (_p / "pdftoppm.exe").is_file():
            POPPLER_PATH = str(_p)
            break

    if POPPLER_PATH:
        log.info("Using bundled Poppler: %s", POPPLER_PATH)
    else:
        import shutil
        if shutil.which("pdftoppm") is None:
            log.error(
                "Poppler not found! Place poppler binaries in ./poppler/ "
                "or add poppler/bin to PATH."
            )
            sys.exit(1)

# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:
    """Convert every page of a PDF to a PIL Image at the given DPI."""
    kwargs = {"dpi": dpi, "fmt": "png"}
    if POPPLER_PATH:
        kwargs["poppler_path"] = POPPLER_PATH
    return convert_from_path(pdf_path, **kwargs)


def ocr_image(image: Image.Image, lang: str = "mal") -> str:
    """Run Tesseract OCR on a single PIL Image and return Unicode text."""
    return pytesseract.image_to_string(image, lang=lang)

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(raw: str) -> str:
    """Apply Malayalam-aware cleaning to OCR output."""
    return normalize_ocr_text(raw)

# ---------------------------------------------------------------------------
# Chunking for RAG
# ---------------------------------------------------------------------------

# Malayalam sentence-end characters + common punctuation
_SENTENCE_END = re.compile(r"(?<=[।\.!\?])\s+")


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences on Malayalam / English sentence boundaries."""
    parts = _SENTENCE_END.split(text)
    return [s.strip() for s in parts if s.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> List[str]:
    """
    Split *text* into chunks of approximately *chunk_size* characters with
    *overlap* character overlap, preserving sentence boundaries where possible.
    """
    if not text:
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return [text] if text.strip() else []

    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        candidate = (current_chunk + " " + sentence).strip() if current_chunk else sentence

        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            # Current chunk is big enough – flush it
            if current_chunk:
                chunks.append(current_chunk)

            # Build overlap from tail of previous chunk
            if overlap > 0 and current_chunk:
                tail = current_chunk[-overlap:]
                current_chunk = (tail + " " + sentence).strip()
            else:
                current_chunk = sentence

    # Flush remaining
    if current_chunk:
        chunks.append(current_chunk)

    # Handle edge case: a single sentence longer than chunk_size
    final: List[str] = []
    for c in chunks:
        if len(c) > chunk_size * 2:
            # Hard-split very long segments
            for i in range(0, len(c), chunk_size - overlap):
                segment = c[i : i + chunk_size]
                if segment.strip():
                    final.append(segment.strip())
        else:
            final.append(c)

    return final

# ---------------------------------------------------------------------------
# Single-PDF processor  (runs in worker process)
# ---------------------------------------------------------------------------

def process_single_pdf(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    lang: str = "mal",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    min_chunk_chars: int = 40,
) -> Dict:
    """
    Full pipeline for one PDF.  Returns a summary dict.
    Designed to be called inside a process-pool worker.
    """
    pdf_name = os.path.basename(pdf_path)
    result = {
        "file": pdf_name,
        "status": "success",
        "pages": 0,
        "chunks": 0,
        "empty_pages": 0,
        "ocr_failed_pages": 0,
        "short_chunks_skipped": 0,
        "error": None,
    }

    try:
        images = pdf_to_images(pdf_path, dpi=dpi)
    except Exception as exc:
        log.warning("Failed to convert %s: %s", pdf_name, exc)
        result["status"] = "error"
        result["error"] = f"PDF conversion failed: {exc}"
        return result

    result["pages"] = len(images)
    all_chunks: List[Dict] = []
    chunk_id = 0

    for page_num, img in enumerate(images, start=1):
        try:
            raw_text = ocr_image(img, lang=lang)
        except Exception as exc:
            log.warning("OCR failed on %s page %d: %s", pdf_name, page_num, exc)
            result["ocr_failed_pages"] += 1
            continue

        cleaned = clean_text(raw_text)
        if not cleaned:
            result["empty_pages"] += 1
            continue

        page_chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=chunk_overlap)
        for text in page_chunks:
            text = (text or "").strip()
            if len(text) < min_chunk_chars:
                result["short_chunks_skipped"] += 1
                continue
            all_chunks.append(
                {
                    "source": pdf_name,
                    "page": page_num,
                    "chunk_id": chunk_id,
                    "text": text,
                }
            )
            chunk_id += 1

    # Write JSON output
    out_name = Path(pdf_name).stem + ".json"
    out_path = os.path.join(output_dir, out_name)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(all_chunks, fh, ensure_ascii=False, indent=2)

    result["chunks"] = len(all_chunks)
    return result

# ---------------------------------------------------------------------------
# Batch orchestrator
# ---------------------------------------------------------------------------

def discover_pdfs(input_dir: str) -> List[str]:
    """Recursively find all PDF files under *input_dir*."""
    pdfs = sorted(
        str(p) for p in Path(input_dir).rglob("*.pdf")
    )
    return pdfs


def run_pipeline(
    input_dir: str,
    output_dir: str,
    workers: int = 4,
    dpi: int = 300,
    lang: str = "mal",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    min_chunk_chars: int = 40,
) -> None:
    """Discover PDFs, process them in parallel, and write JSON chunks."""
    os.makedirs(output_dir, exist_ok=True)

    pdfs = discover_pdfs(input_dir)
    if not pdfs:
        log.error("No PDF files found in %s", input_dir)
        sys.exit(1)

    log.info("Found %d PDF(s) in %s", len(pdfs), input_dir)
    log.info("Workers: %d | DPI: %d | Lang: %s", workers, dpi, lang)
    log.info("Chunk size: %d | Overlap: %d", chunk_size, chunk_overlap)
    log.info("Output dir: %s", output_dir)

    start = time.time()
    results: List[Dict] = []

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                process_single_pdf,
                pdf,
                output_dir,
                dpi,
                lang,
                chunk_size,
                chunk_overlap,
                min_chunk_chars,
            ): pdf
            for pdf in pdfs
        }

        with tqdm(total=len(futures), desc="Processing PDFs", unit="pdf") as pbar:
            for future in as_completed(futures):
                pdf_path = futures[future]
                try:
                    res = future.result()
                except Exception as exc:
                    res = {
                        "file": os.path.basename(pdf_path),
                        "status": "error",
                        "pages": 0,
                        "chunks": 0,
                        "error": str(exc),
                    }
                results.append(res)
                pbar.update(1)

    elapsed = time.time() - start

    # ---- Summary report ----
    ok = [r for r in results if r["status"] == "success"]
    fail = [r for r in results if r["status"] != "success"]
    total_chunks = sum(r["chunks"] for r in ok)
    total_empty_pages = sum(int(r.get("empty_pages", 0)) for r in ok)
    total_ocr_failed_pages = sum(int(r.get("ocr_failed_pages", 0)) for r in ok)
    total_short_chunks_skipped = sum(int(r.get("short_chunks_skipped", 0)) for r in ok)

    log.info("=" * 50)
    log.info("Pipeline complete in %.1f s", elapsed)
    log.info("Success: %d | Failed: %d | Total chunks: %d", len(ok), len(fail), total_chunks)
    log.info(
        "Quality stats: empty_pages=%d | ocr_failed_pages=%d | short_chunks_skipped=%d",
        total_empty_pages,
        total_ocr_failed_pages,
        total_short_chunks_skipped,
    )
    for f in fail:
        log.warning("  FAILED: %s – %s", f["file"], f["error"])

    # Write a manifest of all results
    manifest_path = os.path.join(output_dir, "_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    log.info("Manifest written to %s", manifest_path)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Malayalam PDF → RAG-ready JSON pipeline",
    )
    p.add_argument(
        "--input",
        default="./input/pdfs",
        help="Directory containing PDF files (default: ./input/pdfs)",
    )
    p.add_argument(
        "--output",
        default="./output/rag_chunks",
        help="Directory for JSON output (default: ./output/rag_chunks)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=max(1, multiprocessing.cpu_count() - 1),
        help="Number of parallel workers (default: CPU count − 1)",
    )
    p.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for PDF→image conversion (default: 300)",
    )
    p.add_argument(
        "--lang",
        default="mal",
        help="Tesseract language code (default: mal)",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Target chunk size in characters (default: 500)",
    )
    p.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between consecutive chunks (default: 100)",
    )
    p.add_argument(
        "--min-chunk-chars",
        type=int,
        default=40,
        help="Discard chunks shorter than this length after cleaning (default: 40)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        input_dir=args.input,
        output_dir=args.output,
        workers=args.workers,
        dpi=args.dpi,
        lang=args.lang,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        min_chunk_chars=args.min_chunk_chars,
    )


if __name__ == "__main__":
    main()
