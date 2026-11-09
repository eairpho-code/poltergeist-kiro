"""Coordinate normalization functions.

Raw coordinates arrive in various coordinate spaces (screenshot pixels, screen
pixels, device points). The system converts all positions to device points using
the provided scale factor:

    device_x = raw_x / scale_factor

This keeps distance calculations consistent regardless of the original coordinate
system while preserving the raw data for debugging.
"""

from typing import Tuple

# The coordinate spaces the system recognizes. Matching is case-sensitive.
VALID_COORDINATE_SPACES = ("device_points", "screen_pixels", "screenshot_pixels")


def validate_coordinate_space(coordinate_space: str) -> None:
    """Validate that a coordinate_space is one of the supported identifiers.

    Raises:
        ValueError: If the coordinate_space is not a recognized identifier.
    """
    if coordinate_space not in VALID_COORDINATE_SPACES:
        raise ValueError(
            "Invalid coordinate_space. Must be one of: "
            + ", ".join(VALID_COORDINATE_SPACES)
        )


def _validate_scale_factor(scale_factor: float) -> None:
    if scale_factor <= 0:
        raise ValueError("scale_factor must be greater than 0")


def normalize_coordinates(
    raw_x: float, raw_y: float, scale_factor: float
) -> Tuple[float, float]:
    """Convert raw coordinates to device points.

    device_x = raw_x / scale_factor

    Raises:
        ValueError: If scale_factor is not greater than 0.
    """
    _validate_scale_factor(scale_factor)
    return raw_x / scale_factor, raw_y / scale_factor


def denormalize_coordinates(
    normalized_x: float, normalized_y: float, scale_factor: float
) -> Tuple[float, float]:
    """Convert device point coordinates back to raw coordinates.

    raw_x = normalized_x * scale_factor

    Raises:
        ValueError: If scale_factor is not greater than 0.
    """
    _validate_scale_factor(scale_factor)
    return normalized_x * scale_factor, normalized_y * scale_factor
