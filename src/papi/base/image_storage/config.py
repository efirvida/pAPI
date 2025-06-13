"""
Configuration schema for image storage
"""

from typing import Optional

from pydantic import BaseModel

from papi.core.settings import get_config


class OptimizationConfig(BaseModel):
    """Configuration for image optimization."""

    max_dimension: int = 2048  # Maximum width/height
    jpeg_quality: int = 85  # JPEG quality (0-100)
    png_compression: int = 6  # PNG compression level (0-9)
    webp_quality: int = 80  # WebP quality (0-100)
    force_format: Optional[str] = None  # Target format to convert to (e.g., 'WEBP')


class ImageStorageConfig(BaseModel):
    """Configuration for image storage module."""

    image_optimization: OptimizationConfig = OptimizationConfig()
    cache_ttl: int = 3600  # Cache TTL in seconds
    cache_prefix: str = "pAPI:image_storage:"  # Redis cache prefix
    max_image_size: int = 10 * 1024 * 1024  # Maximum image size in bytes (10 MB)
    allowed_formats: list[str] = [
        "JPEG",
        "PNG",
        "WEBP",
        "GIF",
    ]  # Supported image formats

    # Only local is implemented
    storage_backend: str = "local"  # Storage backend type (e.g., 'local', 's3')
    s3_bucket: Optional[str] = None  # S3 bucket name if using S3 backend
    s3_region: Optional[str] = None  # S3 region if using S3 backend
    s3_access_key: Optional[str] = None  # S3 access key if using S3 backend
    s3_secret_key: Optional[str] = None  # S3 secret key if using S3 backend


config = get_config()
main_config = config.addons.config.get("image_storage", {})
images_settings = ImageStorageConfig(**main_config)
image_optimization_settings = images_settings.image_optimization
