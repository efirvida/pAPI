from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from beanie import Document
from pydantic import BaseModel, ConfigDict, Field


class ImageMetadata(BaseModel):
    """
    Model to store optional metadata extracted from the image.
    """

    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    mode: Optional[str] = None
    exif: dict = Field(default_factory=dict)
    optimization: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class Image(Document):
    """Image document model for storing image metadata and file references."""

    id: UUID = Field(default_factory=uuid4, alias="_id")
    md5: str = Field(index=True)
    file_size: int
    mime_type: str
    metadata: ImageMetadata

    def storage_path(self, storage_root: Path) -> Path:
        """Get the physical storage path for this image."""
        image_id = str(self.id)
        file_name = f"{self.id}.{self.mime_type.split('/')[-1]}"
        subdirs = [image_id[:2], image_id[2:4], image_id[4:6]]
        return storage_root.joinpath(*subdirs, file_name)

    class Settings:
        name = "images"
        use_state_management = True
        use_uuid_primary_key = True

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "id": "654b7cc7-c578-4d53-a5ca-43396d62fdb8",
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
                "file_size": 1024,
                "mime_type": "image/png",
                "metadata": {
                    "width": 800,
                    "height": 600,
                    "format": "PNG",
                    "mode": "RGB",
                },
            }
        },
    )

    @classmethod
    async def get_image_by_id(cls, image_id: UUID) -> Optional["Image"]:
        """
        Retrieve image metadata from the database by its ID.

        Args:
            image_id (UUID): Image UUID.

        Returns:
            Optional[Image]: Image document if found, otherwise None.
        """
        return await cls.get(image_id)
