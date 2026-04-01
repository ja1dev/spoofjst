"""Pydantic models for API request/response."""

from pydantic import BaseModel


class LocationRequest(BaseModel):
    lat: float
    lon: float


class LocationResponse(BaseModel):
    success: bool
    lat: float | None = None
    lon: float | None = None
    error: str | None = None


class ClearResponse(BaseModel):
    success: bool
    error: str | None = None
