from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import uuid4

from beanie import Document
from pydantic import UUID4, BaseModel, Field, StringConstraints


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
    Represents an image stored in the system.
    """

    id: UUID4 = Field(default_factory=uuid4, alias="_id")

    file_name: str
    file_extension: str
    file_size: int
    mime_type: str
    md5: Annotated[str, StringConstraints(pattern="^[a-fA-F0-9]{32}$")]
    metadata: ImageMetadata = Field(default_factory=ImageMetadata)
    file_path: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "images"
        indexes = ["md5", "file_name", "mime_type"]
        unique_fields = ["md5"]

    def storage_path(self, storage_root: Path) -> Path:
        """
        Returns the full storage path for the image file.

        Args:
            storage_root (Path): Base directory for storage.

        Returns:
            Path: Absolute path to the image file.
        """
        return storage_root / self.file_path
