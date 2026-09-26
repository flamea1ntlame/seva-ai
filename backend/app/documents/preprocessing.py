"""
SEVA AI - Document Preprocessing Module

Provides image enhancement, resolution normalization, deskewing, and
multi-page PDF rendering for the pretrained OCR pipeline.
"""

import os
import io
import logging
from typing import List, Tuple, Optional
from PIL import Image, ImageOps, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)

# Minimum and maximum dimension constraints for optimal OCR recognition
MIN_OCR_DIM = 600
MAX_OCR_DIM = 3200


def render_pdf_to_images(pdf_path: str, max_pages: int = 5) -> List[Image.Image]:
    """
    Renders pages of a PDF document into PIL RGB Images using pypdfium2.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    images: List[Image.Image] = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        num_pages = min(len(pdf), max_pages)

        for page_idx in range(num_pages):
            page = pdf[page_idx]
            # Render at 2.0 scale (~144-200 DPI) for sharp text recognition
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil().convert("RGB")
            images.append(pil_image)
        pdf.close()
    except Exception as e:
        logger.warning(f"pypdfium2 PDF rendering failed for {pdf_path}: {e}")
        # Fallback: check if it's an image misnamed as PDF
        try:
            with Image.open(pdf_path) as img:
                images.append(img.convert("RGB"))
        except Exception:
            raise ValueError(f"Unable to render PDF document: {e}")

    return images


def load_document_images(file_path: str) -> List[Image.Image]:
    """
    Loads images from a file path. Supports PDF, JPEG, PNG, WebP, TIFF, BMP.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return render_pdf_to_images(file_path)

    try:
        with Image.open(file_path) as img:
            # Handle multi-frame images (like TIFF)
            images = []
            try:
                for frame_idx in range(getattr(img, "n_frames", 1)):
                    img.seek(frame_idx)
                    images.append(img.copy().convert("RGB"))
            except EOFError:
                pass
            return images if images else [img.convert("RGB")]
    except Exception as e:
        raise ValueError(f"Failed to load image file {file_path}: {e}")


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Enhances an input image for robust text recognition:
    1. EXIF orientation correction
    2. Rescaling to optimal OCR bounds
    3. Contrast normalization & sharpening
    """
    # 1. EXIF orientation correction
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    if image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size

    # 2. Rescale to optimal OCR resolution
    max_dim = max(width, height)
    min_dim = min(width, height)

    if min_dim < MIN_OCR_DIM:
        scale = MIN_OCR_DIM / float(min_dim)
        new_width = int(round(width * scale))
        new_height = int(round(height * scale))
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    elif max_dim > MAX_OCR_DIM:
        scale = MAX_OCR_DIM / float(max_dim)
        new_width = int(round(width * scale))
        new_height = int(round(height * scale))
        image = image.resize((new_width, new_height), Image.Resampling.BILINEAR)

    # 3. Optional contrast enhancement via OpenCV if available
    try:
        import cv2
        np_img = np.array(image)
        # Convert RGB to BGR for cv2
        bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Contrast Limited Adaptive Histogram Equalization (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)

        # Mild bilateral filtering to denoise while keeping character edges sharp
        denoised = cv2.bilateralFilter(enhanced_gray, d=5, sigmaColor=50, sigmaSpace=50)

        # Convert back to RGB for OCR model
        enhanced_rgb = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)
        return Image.fromarray(enhanced_rgb)
    except Exception as e:
        logger.debug(f"OpenCV enhancement skipped: {e}. Using PIL fallback.")
        # Fallback enhancement using pure PIL
        enhancer = ImageOps.autocontrast(image, cutoff=1)
        return enhancer
