import hashlib
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Union

import filetype
from PIL import ExifTags
from PIL import Image as PILImage

from .models import Image


class ImageService:
    """
    Service responsible for processing, storing, and retrieving images
    using a hierarchical file system and metadata indexing.
    """

    def __init__(self, storage_root: Union[str, Path]) -> None:
        """
        Initialize the image service with the given root storage directory.

        Args:
            storage_root (Union[str, Path]): Root directory to store image files.
        """
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
        Extracts EXIF metadata from a PIL image object.

        Args:
            image (PIL.Image.Image): Image to extract EXIF metadata from.

        Returns:
            Dict[str, Any]: Parsed EXIF metadata.
        """
        exif_data = image._getexif()
        if not exif_data:
            return {}

        parsed_exif = {}
        for tag, value in exif_data.items():
            tag_name = ExifTags.TAGS.get(tag, tag)

            # Convert numeric tuples or rational types to float
            if isinstance(value, tuple):
                value = tuple(float(x) if hasattr(x, "__float__") else x for x in value)
            elif hasattr(value, "__float__"):
                value = float(value)

            # Decode bytes to string
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8")
                except UnicodeDecodeError:
                    value = value.decode("latin-1")

            parsed_exif[tag_name] = value
        return parsed_exif

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

        Args:
            file_content (bytes): Raw binary content of the image file.
            original_filename (str): Name of the uploaded file.
            **extra_metadata: Additional metadata to store with the image.

        Returns:
            Image: Saved Image document.
        """
        file_type = filetype.guess(file_content)
        if not file_type:
            raise ValueError("Unrecognized file type.")

        extension = Path(original_filename).suffix.lower()
        if not extension:
            extension = f".{file_type.extension}"

        md5_hash = self._calculate_md5(file_content)
        existing_image = await Image.find_one({"md5": md5_hash})
        if existing_image:
            return existing_image

        image_id = str(uuid.uuid4())
        file_path = self._build_file_path(image_id, extension)

        try:
            file_path.write_bytes(file_content)
        except Exception as e:
            raise IOError(f"Failed to write image to disk: {e}")

        try:
            with PILImage.open(BytesIO(file_content)) as img:
                exif_metadata = self._extract_exif(img)
                width, height = img.size
        except Exception as e:
            raise ValueError(f"Unable to read image content: {e}")

        metadata = {
            **exif_metadata,
            "width": width,
            "height": height,
            **extra_metadata,
        }

        image = Image(
            id=image_id,
            file_name=file_path.stem,
            file_extension=extension,
            file_size=len(file_content),
            md5=md5_hash,
            file_path=str(file_path.relative_to(self.storage_root)),
            mime_type=file_type.mime,
            metadata=metadata,
        )

        await image.insert()
        return image

    async def get_image_by_id(self, image_id: str) -> Optional[Image]:
        """
        Retrieve image metadata from the database by its ID.

        Args:
            image_id (str): Image UUID.

        Returns:
            Optional[Image]: Image document if found, otherwise None.
        """
        return await Image.get(image_id)

    async def get_image_file_path(self, image_id: str) -> Optional[Path]:
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

    async def delete_image(self, image_id: str) -> bool:
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
