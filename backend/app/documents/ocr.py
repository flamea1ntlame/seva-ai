"""
SEVA AI - Pretrained OCR Module

Provides an isolated, dedicated OCR engine using pretrained PaddleOCR
for English and printed government documents.
Returns structured text lines, bounding boxes, confidence scores, and page numbers.
"""

import os
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from PIL import Image
import numpy as np

from app.documents.preprocessing import load_document_images, preprocess_image_for_ocr

logger = logging.getLogger(__name__)

# Pre-import torch and configure Paddle static runner to avoid Windows oneDNN PIR attribute bug
try:
    import torch
except Exception:
    pass

try:
    import paddlex.inference.models.runners.paddle_static.runner as _paddlex_runner
    for _m in [
        'PP-OCRv6_medium_det', 'PP-OCRv6_mobile_det',
        'PP-OCRv4_medium_det', 'PP-OCRv4_mobile_det',
        'PP-OCRv3_det', 'PP-OCRv2_det'
    ]:
        if _m not in _paddlex_runner.MKLDNN_BLOCKLIST:
            _paddlex_runner.MKLDNN_BLOCKLIST.append(_m)
except Exception:
    pass


@dataclass
class OCRLine:
    text: str
    confidence: float
    bbox: List[int] = field(default_factory=list)  # [x_min, y_min, x_max, y_max]
    page: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OCRResult:
    text: str
    lines: List[OCRLine]
    average_confidence: float
    page_count: int
    engine: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "lines": [line.to_dict() for line in self.lines],
            "average_confidence": round(self.average_confidence, 4),
            "page_count": self.page_count,
            "engine": self.engine,
        }


class OCREngine:
    _paddle_instance = None
    _last_init_attempt = 0.0
    _init_cooldown = 15.0  # seconds before attempting re-initialization

    @classmethod
    def get_paddle_ocr(cls):
        import time
        if cls._paddle_instance is not None:
            return cls._paddle_instance

        now = time.time()
        if (now - cls._last_init_attempt) < cls._init_cooldown:
            return None

        cls._last_init_attempt = now
        try:
            from paddleocr import PaddleOCR
            try:
                cls._paddle_instance = PaddleOCR(
                    lang="en",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
            except (TypeError, Exception):
                cls._paddle_instance = PaddleOCR(
                    lang="en",
                    use_angle_cls=False,
                    show_log=False,
                )
            logger.info("PaddleOCR engine initialized successfully.")
            return cls._paddle_instance
        except Exception as e:
            logger.warning(f"PaddleOCR initialization failed: {e}. Will retry after cooldown.")
            return None


def perform_ocr(file_path: str) -> OCRResult:
    """
    Executes pretrained OCR on an uploaded image or PDF document using PaddleOCR.
    Returns structured text lines with confidence scores and coordinates.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document file not found: {file_path}")

    # 1. Render/load images across all pages
    page_images = load_document_images(file_path)
    if not page_images:
        return OCRResult(text="", lines=[], average_confidence=0.0, page_count=0, engine="none")

    all_lines: List[OCRLine] = []
    used_engine = "paddleocr"

    paddle_ocr = OCREngine.get_paddle_ocr()

    for page_idx, raw_img in enumerate(page_images, start=1):
        # 2. Image Preprocessing (orientation, CLAHE contrast, bilateral denoising)
        proc_img = preprocess_image_for_ocr(raw_img)
        np_img = np.array(proc_img)

        page_lines: List[OCRLine] = []

        # 3. Primary OCR: Pretrained PaddleOCR
        if paddle_ocr:
            try:
                preds = None
                if hasattr(paddle_ocr, "predict"):
                    try:
                        preds = paddle_ocr.predict(np_img)
                    except Exception:
                        preds = None
                if preds is None and hasattr(paddle_ocr, "ocr"):
                    preds = paddle_ocr.ocr(np_img, cls=False)

                if preds is not None:
                    if isinstance(preds, list) and len(preds) == 1 and isinstance(preds[0], list):
                        preds = preds[0]

                    for pred in preds:
                        if isinstance(pred, dict):
                            rec_texts = pred.get("rec_texts", [])
                            rec_scores = pred.get("rec_scores", [])
                            rec_boxes = pred.get("rec_boxes", [])
                            for idx, txt in enumerate(rec_texts):
                                score = float(rec_scores[idx]) if idx < len(rec_scores) else 0.8
                                bbox: List[int] = []
                                if idx < len(rec_boxes):
                                    b = rec_boxes[idx]
                                    if hasattr(b, "tolist"):
                                        b = b.tolist()
                                    if isinstance(b, list) and len(b) >= 4:
                                        bbox = [int(v) for v in b[:4]]
                                page_lines.append(OCRLine(text=str(txt).strip(), confidence=score, bbox=bbox, page=page_idx))
                        elif isinstance(pred, (list, tuple)) and len(pred) == 2 and isinstance(pred[1], (list, tuple)):
                            poly, text_score = pred
                            txt = text_score[0] if len(text_score) > 0 else ""
                            score = float(text_score[1]) if len(text_score) > 1 else 0.8
                            xs = [pt[0] for pt in poly] if isinstance(poly, (list, tuple)) else [0, 0]
                            ys = [pt[1] for pt in poly] if isinstance(poly, (list, tuple)) else [0, 0]
                            bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
                            page_lines.append(OCRLine(text=str(txt).strip(), confidence=score, bbox=bbox, page=page_idx))
            except Exception as e:
                logger.warning(f"PaddleOCR prediction failed on page {page_idx}: {e}")

        all_lines.extend(page_lines)

    # 4. Fallback for digital PDFs if visual OCR yielded no text
    if not all_lines and file_path.lower().endswith(".pdf"):
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_path)
            for page_idx in range(len(pdf)):
                textpage = pdf[page_idx].get_textpage()
                txt = textpage.get_text_range()
                if txt:
                    for line in txt.splitlines():
                        s = line.strip()
                        if s:
                            all_lines.append(OCRLine(text=s, confidence=0.99, bbox=[0, 0, 0, 0], page=page_idx + 1))
            if all_lines:
                used_engine = "pypdfium_text"
        except Exception as pdf_err:
            logger.warning(f"PDF direct text extraction fallback failed: {pdf_err}")

    # 5. Compute summary metrics
    total_conf = sum(l.confidence for l in all_lines)
    avg_conf = (total_conf / len(all_lines)) if all_lines else 0.0
    joined_text = "\n".join(l.text for l in all_lines if l.text)

    return OCRResult(
        text=joined_text,
        lines=all_lines,
        average_confidence=avg_conf,
        page_count=len(page_images),
        engine=used_engine,
    )
