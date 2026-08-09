"""
RUDRA AI - Automation Router
API endpoints for desktop automation tasks.
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from app.services.automation_service import automation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/automation", tags=["Automation"])


class AppRequest(BaseModel):
    name: str = Field(..., description="Application name")


class FileSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    directory: Optional[str] = Field(None, description="Directory to search in")
    max_results: int = Field(20, ge=1, le=100)


class CreateFolderRequest(BaseModel):
    path: str = Field(..., description="Full path for new folder")


class RenameRequest(BaseModel):
    path: str = Field(..., description="Current file/folder path")
    new_name: str = Field(..., description="New name")


class VolumeRequest(BaseModel):
    level: int = Field(..., ge=0, le=100, description="Volume level 0-100")


class CameraPhotoRequest(BaseModel):
    filename: str | None = Field(None, description="Optional filename for the captured photo")


@router.post("/app/open")
async def open_app(request: AppRequest):
    """Open an application."""
    return await automation_service.open_application(request.name)


@router.post("/app/close")
async def close_app(request: AppRequest):
    """Close an application."""
    return await automation_service.close_application(request.name)


@router.post("/file/search")
async def search_files(request: FileSearchRequest):
    """Search for files."""
    return await automation_service.search_files(
        request.query, request.directory, request.max_results
    )


@router.post("/file/create-folder")
async def create_folder(request: CreateFolderRequest):
    """Create a new folder."""
    return await automation_service.create_folder(request.path)


@router.post("/file/rename")
async def rename_file(request: RenameRequest):
    """Rename a file or folder."""
    return await automation_service.rename_file(request.path, request.new_name)


@router.post("/system/screenshot")
async def take_screenshot():
    """Take a screenshot."""
    return await automation_service.take_screenshot()


@router.post("/camera/photo")
async def capture_camera_photo(request: CameraPhotoRequest):
    """Capture a photo from the system camera."""
    return await automation_service.capture_camera_photo(request.filename)


@router.post("/camera/search-person")
async def search_person_from_photo(request: CameraPhotoRequest):
    """Capture a photo and start an image search page for the captured person."""
    return await automation_service.search_person_from_photo(request.filename)


@router.post("/system/volume")
async def set_volume(request: VolumeRequest):
    """Set system volume."""
    return await automation_service.set_volume(request.level)
