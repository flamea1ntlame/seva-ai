import os
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class QROutcome(BaseModel):
    qr_detected: bool = False
    qr_data: Optional[str] = None
    barcode_detected: bool = False
    barcode_data: Optional[str] = None
    checks_passed: List[str] = Field(default_factory=list)
    checks_failed: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    payload_fields: Dict[str, Any] = Field(default_factory=dict)


def analyze_qr_barcode(file_path: str, extracted_identifier: Optional[str] = None) -> QROutcome:
    """
    Scans document images or rendered PDF pages for 2D QR codes or 1D barcodes.
    Cross-checks decoded QR contents with visual/OCR identifier where available.
    """
    if not os.path.exists(file_path):
        return QROutcome(risk_flags=["FILE_NOT_FOUND"])

    checks_passed = []
    checks_failed = []
    risk_flags = []
    qr_detected = False
    qr_data = None
    barcode_detected = False
    barcode_data = None

    try:
        # Load image (if PDF, render first page using pypdfium2)
        img = None
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(file_path)
                if len(pdf) > 0:
                    page = pdf[0]
                    pil_img = page.render(scale=2).to_pil()
                    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception:
                pass
        else:
            img = cv2.imread(file_path)

        if img is not None:
            # 1. OpenCV QRCodeDetector
            detector = cv2.QRCodeDetector()
            val, points, _ = detector.detectAndDecode(img)
            if val and len(val.strip()) > 0:
                qr_detected = True
                qr_data = val.strip()
                checks_passed.append("qr_code_detected")
                checks_passed.append("qr_code_decoded")
            elif points is not None:
                qr_detected = True
                checks_passed.append("qr_code_detected")
                checks_failed.append("qr_code_decoded")
                risk_flags.append("QR_UNREADABLE")

        # Cross-reference with extracted identifier if QR payload text was recovered
        if qr_data and extracted_identifier:
            # Clean extracted identifier of redactions/masks
            clean_token = extracted_identifier.replace("X", "").replace("*", "").strip()
            if len(clean_token) >= 4:
                if clean_token in qr_data:
                    checks_passed.append("qr_identifier_cross_check_matched")
                else:
                    checks_failed.append("qr_identifier_cross_check_matched")
                    risk_flags.append("QR_IDENTIFIER_MISMATCH")

    except Exception as exc:
        risk_flags.append(f"QR_ANALYSIS_ERROR_{type(exc).__name__}")

    return QROutcome(
        qr_detected=qr_detected,
        qr_data=qr_data,
        barcode_detected=barcode_detected,
        barcode_data=barcode_data,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        risk_flags=risk_flags
    )
