"""
Image optimization and compression utilities.
"""

from io import BytesIO
from typing import Tuple

from loguru import logger
from PIL import Image
from PIL.Image import Resampling

from .config import OptimizationConfig


def optimize_image(
    image_data: bytes, config: OptimizationConfig = OptimizationConfig()
) -> Tuple[bytes, dict]:
    """
    Optimize an image by resizing and compressing it according to configuration.

    Args:
        image_data: Raw image bytes
        config: Optimization configuration

    Returns:
        Tuple containing:
        - Optimized image bytes
        - Dictionary with optimization metadata
    """
    try:
        # Open image
        img = Image.open(BytesIO(image_data))
        original_format = img.format
        original_size = len(image_data)

        # Convert RGBA to RGB if alpha channel is not needed
        if img.mode == "RGBA" and not _needs_alpha(img):
            img = img.convert("RGB")

        # Resize if needed
        if max(img.size) > config.max_dimension:
            img = _resize_image(img, config.max_dimension)

        # Determine output format
        output_format = config.force_format or original_format

        # Apply format-specific optimizations
        output_buffer = BytesIO()
        optimize_kwargs = _get_optimization_params(output_format, config)

        # Save optimized image
        img.save(output_buffer, format=output_format, **optimize_kwargs)
        optimized_data = output_buffer.getvalue()

        metadata = {
            "original_size": original_size,
            "optimized_size": len(optimized_data),
            "original_format": original_format,
            "output_format": output_format,
            "dimensions": img.size,
            "compression_ratio": len(optimized_data) / original_size,
        }

        return optimized_data, metadata

    except Exception as e:
        logger.error(f"Image optimization failed: {e}")
        return image_data, {"error": str(e)}


def _needs_alpha(img: Image.Image) -> bool:
    """Check if image actually uses alpha channel."""
    if "A" not in img.getbands():
        return False

    # Check if alpha channel has any non-fully-opaque pixels
    alpha = img.getchannel("A")
    return alpha.getextrema()[0] < 255


def _resize_image(img: Image.Image, max_dimension: int) -> Image.Image:
    """Resize image maintaining aspect ratio."""
    ratio = max_dimension / max(img.size)
    if ratio < 1:
        new_size = tuple(int(dim * ratio) for dim in img.size)
        return img.resize(new_size, Resampling.LANCZOS)
    return img


def _get_optimization_params(format: str, config: OptimizationConfig) -> dict:
    """Get format-specific optimization parameters."""
    params = {"optimize": True}

    if format == "JPEG":
        params["quality"] = config.jpeg_quality
    elif format == "PNG":
        params["compress_level"] = config.png_compression
    elif format == "WEBP":
        params["quality"] = config.webp_quality

    return params
