import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import filetype
from loguru import logger
from PIL import Image as PILImage
from PIL.ExifTags import TAGS

from papi.core.settings import get_config

from .config import image_optimization_settings
from .models import Image, ImageMetadata
from .optimization import optimize_image


class ImageService:
    """
    Service responsible for processing, storing, and retrieving images
    using a hierarchical file system and metadata indexing.
    """

    def __init__(self) -> None:
        """
        Initialize the image service with configuration.
        """
        config = get_config()
        storage_root = config.storage.images or "data/images"

        # Initialize optimization config with defaults
        self.optimization_config = image_optimization_settings
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _calculate_md5(self, content: bytes) -> str:
        """
        Calculate the MD5 hash of the given binary content.

        Args:
            content (bytes): Binary content of the file.

        Returns:
            str: MD5 hash string.
        """
        return hashlib.md5(content).hexdigest()

    def _extract_exif(self, image: PILImage.Image) -> Dict[str, Any]:
        """
        Extract EXIF metadata from a PIL image object safely.
        """
        try:
            exif_data = {}
            if hasattr(image, "getexif") and callable(image.getexif):
                exif = image.getexif()
                if exif:
                    for tag_id in exif:
                        tag_name = TAGS.get(tag_id, tag_id)
                        value = exif[tag_id]
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8")
                            except UnicodeDecodeError:
                                value = value.hex()
                        exif_data[tag_name] = value
            return exif_data
        except Exception as e:
            logger.warning(f"Error extracting EXIF data: {e}")
            return {}

    def _build_file_path(self, image_id: str, extension: str) -> Path:
        """
        Build a hierarchical file path for the image using its ID.

        Args:
            image_id (str): Unique ID of the image.
            extension (str): File extension (e.g. '.jpg').

        Returns:
            Path: Full path where the image should be stored.
        """
        subdirs = [image_id[:2], image_id[2:4], image_id[4:6]]
        file_dir = self.storage_root.joinpath(*subdirs)
        file_dir.mkdir(parents=True, exist_ok=True)
        return file_dir / f"{image_id}{extension}"

    async def process_and_save_image(
        self,
        file_content: bytes,
        original_filename: str,
        **extra_metadata: Any,
    ) -> Image:
        """
        Process and save a new image, extracting metadata and avoiding duplicates.
        Now includes optimization and compression.

        Args:
            file_content (bytes): Raw binary content of the image file.
            original_filename (str): Name of the uploaded file.
            **extra_metadata: Additional metadata to store with the image.

        Returns:
            Image: Saved Image document.
        """
        # Optimize the image
        optimized_content, optimization_info = optimize_image(
            file_content, self.optimization_config
        )

        # Calculate MD5 of optimized content
        md5_hash = self._calculate_md5(optimized_content)

        # Check for duplicates
        existing_image = await Image.find_one({"md5": md5_hash})
        if existing_image:
            return existing_image

        # Load image for metadata extraction
        img = PILImage.open(BytesIO(optimized_content))

        # Create ImageMetadata instance
        metadata = ImageMetadata(
            width=img.width,
            height=img.height,
            format=img.format,
            mode=img.mode,
            optimization=optimization_info,
            exif=self._extract_exif(img),
            **extra_metadata,
        )

        # Get file type for mime type
        file_type = filetype.guess(optimized_content)
        mime_type = file_type.mime if file_type else "application/octet-stream"
        extension = file_type.extension if file_type else "bin"

        # Create and save image document to generate UUID
        image = Image(
            md5=md5_hash,
            file_size=len(optimized_content),
            mime_type=mime_type,
            metadata=metadata,
        )
        await image.save()

        # Save the physical file using the generated UUID
        file_path = self._build_file_path(str(image.id), f".{extension}")
        file_path.write_bytes(optimized_content)

        return image

    async def get_image_by_id(self, image_id: UUID) -> Optional[Image]:
        """
        Retrieve image metadata from the database by its ID.

        Args:
            image_id (str): Image UUID.

        Returns:
            Optional[Image]: Image document if found, otherwise None.
        """
        return await Image.get(image_id)

    async def get_image_file_path(self, image_id: UUID) -> Optional[Path]:
        """
        Retrieve the physical path of an image by its ID.

        Args:
            image_id (str): Image UUID.

        Returns:
            Optional[Path]: Path to the image file if found.
        """
        image = await self.get_image_by_id(image_id)
        if not image:
            return None
        return image.storage_path(storage_root=self.storage_root)

    async def delete_image(self, image_id: UUID) -> bool:
        """
        Delete both the image file and its metadata record.

        Args:
            image_id (str): Image UUID.

        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        image = await self.get_image_by_id(image_id)
        if not image:
            return False

        file_path = image.storage_path(self.storage_root)
        if file_path.exists():
            try:
                file_path.unlink()

                # Attempt to clean up empty parent directories
                for parent in file_path.parents:
                    if parent == self.storage_root:
                        break
                    if not any(parent.iterdir()):
                        parent.rmdir()
            except Exception:
                pass

        await image.delete()
        return True
