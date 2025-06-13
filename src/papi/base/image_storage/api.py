from pathlib import Path
from uuid import UUID

from fastapi import File, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import UUID4, BaseModel

from papi.core.exceptions import APIException
from papi.core.models.response import APIResponse, create_response
from papi.core.router import RESTRouter

from .cache import get_cached_image_info, invalidate_image_cache, set_cached_image_info
from .models import Image, ImageMetadata
from .service import ImageService

router = RESTRouter(prefix="/images", tags=["Images"])

image_service = ImageService()


class ImageResponse(BaseModel):
    """
    Response model for exposing public image information via the API.
    """

    id: UUID4
    md5: str
    file_size: int
    mime_type: str
    metadata: ImageMetadata

    class Config:
        from_attributes = True


@router.get("/", response_model=APIResponse, expose_as_mcp_tool=True)
async def list_images():
    """
    List all stored images with their metadata.

    Returns:
        APIResponse: A paginated list of images with their metadata.
            {
                "data": {
                    "items": [
                        {
                            "id": "uuid",
                            "md5": "hash-string",
                            "file_size": 12345,
                            "mime_type": "image/jpeg",
                            "metadata": {
                                "width": 800,
                                "height": 600,
                                "format": "JPEG"
                            }
                        }
                    ],
                    "total": 10
                },
                "message": "Images retrieved successfully."
            }

    Raises:
        APIException: If there's an error accessing the image storage.
            Status codes:
            - 500: Internal server error while retrieving images.

    Example:
        ```http
        GET /images/
        ```
    """
    query = Image.find()
    images = await query.to_list()
    total = len(images)
    return create_response(
        data={"items": images, "total": total}, message="Images retrieved successfully."
    )


@router.get("/{image_id}")
async def get_image_file(image_id: str):
    """
    Retrieve the binary file of an image by its ID.

    This endpoint returns the actual image file. The response includes appropriate
    Content-Type and Content-Disposition headers for browser handling. The file path
    is cached in Redis to improve performance.

    Args:
        image_id (str): UUID of the image to retrieve.

    Returns:
        FileResponse: The binary image file with appropriate headers.
            Content-Type will match the image's mime_type.
            Content-Disposition will be set to 'inline' for browser display.

    Raises:
        APIException:
            - 404: Image not found
                {
                    "code": "NOT_FOUND",
                    "message": "Image file not found."
                }
            - 500: Error accessing image storage

    Example:
        ```http
        GET /images/123e4567-e89b-12d3-a456-426614174000
        ```

        Response headers:
        ```
        Content-Type: image/jpeg
        Content-Disposition: inline; filename="image.jpg"
        ```
    """
    # Try to get file path from cache
    cached_data = await get_cached_image_info(image_id)
    if cached_data and "file_path" in cached_data:
        file_path = Path(cached_data["file_path"])
        if file_path.exists():
            return FileResponse(
                file_path,
                headers={
                    "Cache-Control": "public, max-age=31536000",  # 1 year
                    "ETag": cached_data.get("md5", ""),  # Use MD5 as ETag
                },
            )

    # If not in cache or file doesn't exist, get from service
    file_path = await image_service.get_image_file_path(UUID(image_id))
    if not file_path or not file_path.exists():
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="Image file not found.",
        )

    # Get image metadata for caching and ETag
    image = await image_service.get_image_by_id(UUID(image_id))
    if image:
        cache_data = image.model_dump()
        cache_data["file_path"] = str(file_path)
        await set_cached_image_info(image_id, cache_data)
        etag = image.md5
    else:
        etag = ""

    return FileResponse(
        file_path,
        headers={
            "Cache-Control": "public, max-age=31536000",  # 1 year
            "ETag": etag,
        },
    )


@router.get("/{image_id}/metadata", response_model=APIResponse)
async def get_image_info(image_id: str):
    """
    Get the metadata for a specific image by its ID.

    This endpoint returns detailed metadata about the image including its
    dimensions, format, size, and other technical information. Results are cached
    in Redis for improved performance.

    Args:
        image_id (str): UUID of the image to retrieve metadata for.

    Returns:
        APIResponse: Detailed image metadata.
            {
                "data": {
                    "id": "uuid",
                    "md5": "hash-string",
                    "file_size": 12345,
                    "mime_type": "image/jpeg",
                    "metadata": {
                        "width": 800,
                        "height": 600,
                        "format": "JPEG",
                        "color_space": "RGB",
                        "bits_per_pixel": 24
                    }
                },
                "message": "Image metadata retrieved successfully."
            }

    Raises:
        APIException:
            - 404: Image not found
                {
                    "code": "NOT_FOUND",
                    "message": "Image file not found."
                }
            - 500: Error accessing metadata

    Example:
        ```http
        GET /images/123e4567-e89b-12d3-a456-426614174000/metadata
        ```

    Note:
        Results are cached for 1 hour to improve performance.
    """
    # Try to get from cache first
    cached_data = await get_cached_image_info(image_id)
    if cached_data:
        return create_response(
            data=ImageResponse.model_validate(cached_data),
            message="Image metadata retrieved successfully from cache.",
        )

    # If not in cache, get from database
    image = await image_service.get_image_by_id(UUID(image_id))
    if not image:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="Image file not found.",
        )

    # Cache the result
    image_data = image.model_dump()
    await set_cached_image_info(image_id, image_data)

    return create_response(
        data=ImageResponse.model_validate(image),
        message="Image metadata retrieved successfully.",
    )


@router.post("/", response_model=APIResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    Upload and store a new image file.

    The endpoint accepts multipart/form-data with an image file. The image will be
    validated, processed, and stored. Metadata like dimensions and format will be
    automatically extracted.

    Args:
        file (UploadFile): The image file to upload.
            Supported formats: JPEG, PNG, GIF, WebP
            Max file size: 10MB

    Returns:
        APIResponse: The saved image metadata.
            {
                "data": {
                    "id": "uuid",
                    "md5": "hash-string",
                    "file_size": 12345,
                    "mime_type": "image/jpeg",
                    "metadata": {
                        "width": 800,
                        "height": 600,
                        "format": "JPEG"
                    }
                },
                "message": "Image uploaded successfully."
            }

    Raises:
        APIException:
            - 400: Invalid image file or format
                {
                    "code": "INVALID_IMAGE",
                    "message": "Invalid Image File"
                }
            - 413: File too large
            - 500: Error saving image
                {
                    "code": "IMAGE_SAVE_ERROR",
                    "message": "Error saving image, due to unexpected server error."
                }

    Example:
        ```bash
        curl -X POST /images/ \\
             -H "Content-Type: multipart/form-data" \\
             -F "file=@image.jpg"
        ```
    """
    if not file.filename:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            message="File name not provided.",
        )

    try:
        file_content = await file.read()
        image = await image_service.process_and_save_image(
            file_content=file_content,
            original_filename=file.filename,
        )
        return create_response(
            data=ImageResponse.model_validate(image),
            message="Image uploaded successfully.",
        )
    except ValueError as e:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_IMAGE",
            message="Invalid Image File",
            detail=str(e),
        )
    except Exception:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="IMAGE_SAVE_ERROR",
            message="Error saving image, due to unexpected server error.",
        )


@router.delete("/{image_id}", response_model=APIResponse)
async def delete_image(image_id: str):
    """
    Delete an image by its ID.

    This operation permanently removes both the image file and its associated metadata,
    and invalidates any cached data. The operation cannot be undone.

    Args:
        image_id (str): UUID of the image to delete.

    Returns:
        APIResponse: Success response with deletion confirmation.
            {
                "message": "Image deleted successfully."
            }

    Raises:
        APIException:
            - 404: Image not found
                {
                    "code": "NOT_FOUND",
                    "message": "Image not found or could not be deleted."
                }
            - 500: Error during deletion process

    Example:
        ```http
        DELETE /images/123e4567-e89b-12d3-a456-426614174000
        ```

    Note:
        - This operation requires appropriate permissions
        - The deletion is permanent and cannot be undone
        - Both the file and database records will be removed
    """
    # Delete the image and invalidate cache
    if await image_service.delete_image(UUID(image_id)):
        await invalidate_image_cache(image_id)
        return create_response(message="Image deleted successfully.")
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code="NOT_FOUND",
        message="Image not found or could not be deleted.",
    )
