# backend/preprocessing/utils.py
import os
import logging
from typing import Optional, Dict, Any
import pytesseract
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_file(file_path: str, expected_extensions: set) -> bool:
    """
    Validate if the file exists and has an allowed extension.

    Args:
        file_path: Path to the file.
        expected_extensions: Set of allowed file extensions (e.g., {".txt", ".pdf"}).

    Returns:
        bool: True if the file is valid, False otherwise.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in expected_extensions:
        logger.error(f"Unsupported file extension: {ext}")
        return False

    return True

def setup_ocr() -> None:
    """
    Set up Tesseract OCR (pytesseract) with the correct path if needed.
    """
    # If Tesseract is not in your PATH, specify its location here
    # Example for Windows: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    # Example for Linux/Mac: Usually not needed if installed via package manager
    pass

def extract_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract basic metadata from a file (e.g., size, last modified).

    Args:
        file_path: Path to the file.

    Returns:
        dict: Metadata about the file.
    """
    if not os.path.exists(file_path):
        return {}

    stat = os.stat(file_path)
    return {
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
        "extension": os.path.splitext(file_path)[1].lower(),
    }

def preprocess_image_for_ocr(image_path: str, output_path: Optional[str] = None) -> str:
    """
    Preprocess an image to improve OCR accuracy (e.g., convert to grayscale, thresholding).

    Args:
        image_path: Path to the input image.
        output_path: Path to save the processed image. If None, overwrites the input.

    Returns:
        str: Path to the processed image.
    """
    if output_path is None:
        output_path = image_path

    try:
        img = Image.open(image_path)
        # Convert to grayscale
        img = img.convert("L")
        # Apply thresholding to binarize the image
        img = img.point(lambda x: 0 if x < 128 else 255, "1")
        img.save(output_path)
        return output_path
    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        return image_path

def log_chunk_info(chunk, source: str) -> None:
    """
    Log information about a chunk for debugging.

    Args:
        chunk: The Chunk object.
        source: Source of the chunk (e.g., file name).
    """
    logger.info(
        f"Chunk from {source} | Speaker: {chunk.speaker} | "
        f"Text length: {len(chunk.text)} | Metadata: {chunk.metadata or 'None'}"
    )