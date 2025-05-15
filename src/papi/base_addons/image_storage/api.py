from typing import List

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import UUID4, BaseModel

from papi.core.router import RESTRouter

from .models import Image, ImageMetadata
from .service import ImageService

router = RESTRouter(prefix="/images", tags=["images"])

image_service = ImageService()


class ImageResponse(BaseModel):
    """
    Response model for exposing public image information via the API.
    """

    id: UUID4
    md5: str
    url: str
    file_size: int
    mime_type: str
    metadata: ImageMetadata

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[ImageResponse], expose_as_mcp_tool=True)
async def list_images():
    """
    List all stored images with their metadata.
    """
    query = Image.find()
    images = await query.to_list()
    return images


@router.post("/save", response_model=ImageResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    Upload and store a new image file.

    Args:
        file (UploadFile): The image file to upload.

    Returns:
        ImageResponse: The saved image metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name not provided.")

    try:
        file_content = await file.read()
        image = await image_service.process_and_save_image(
            file_content=file_content,
            original_filename=file.filename,
        )
        return ImageResponse.from_orm(image)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Unexpected error saving image: {str(e)}"
        )


@router.get("/get/{image_id}")
async def get_image_file(image_id: str):
    """
    Retrieve the binary file of an image by its ID.

    Args:
        image_id (str): The ID of the image.

    Returns:
        FileResponse: The image file to be sent as a response.
    """
    file_path = await image_service.get_image_file_path(image_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(file_path)


@router.get("/meta/{image_id}", response_model=ImageResponse)
async def get_image_info(image_id: str):
    """
    Get the metadata for a specific image by its ID.

    Args:
        image_id (str): The ID of the image.

    Returns:
        ImageResponse: Metadata of the image.
    """
    image = await image_service.get_image_by_id(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found.")
    return image


@router.delete("/remove/{image_id}")
async def delete_image(image_id: str):
    """
    Delete an image by its ID.

    Args:
        image_id (str): The ID of the image to delete.

    Returns:
        dict: Success message if deletion succeeded.
    """
    if await image_service.delete_image(image_id):
        return {"message": "Image deleted successfully."}
    raise HTTPException(status_code=404, detail="Image not found.")
