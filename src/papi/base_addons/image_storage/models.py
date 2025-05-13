from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from beanie import Document
from pydantic import UUID4, BaseModel, Field, computed_field


class ImageMetadata(BaseModel):
    """
    Model to store optional metadata extracted from the image, such as dimensions.

    Extra fields are allowed to accommodate additional EXIF data or custom metadata.
    """

    width: Optional[int] = None
    height: Optional[int] = None

    class Config:
        populate_by_name = True
        extra = "allow"  # Allow additional keys beyond the declared ones


class Image(Document):
    """
    Document model representing an image stored in the system.

    Fields:
    - id: UUID of the image document.
    - file_name: Name of the file (without extension).
    - file_extension: File extension (e.g., .jpg, .png).
    - file_size: Size of the file in bytes.
    - mime_type: MIME type of the image (e.g., image/jpeg).
    - md5: MD5 hash of the file content for deduplication.
    - metadata: Optional metadata including image dimensions and EXIF data.
    - file_path: Relative path where the image is stored.
    - created_at: Timestamp of creation.
    - updated_at: Timestamp of last update.
    """

    id: UUID4 = Field(default_factory=uuid4, alias="_id")

    file_name: str
    file_extension: str
    file_size: int
    mime_type: str
    md5: str
    metadata: ImageMetadata = Field(default_factory=ImageMetadata)
    file_path: str

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "images"  # Name of the MongoDB collection

    @computed_field
    @property
    def url(self) -> str:
        """
        Returns a public-facing URL for accessing the image.
        """
        return f"/images/{self.id}"

    def storage_path(self, storage_root: Path) -> Path:
        """
        Returns the absolute path to the stored image on disk.

        Args:
            storage_root (Path): Root path of the image storage.

        Returns:
            Path: Full path to the image file.
        """
        return storage_root / self.file_path
