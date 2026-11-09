"""Tests for coordinate normalization functions."""

import pytest
from hypothesis import given, strategies as st

from poltergeist.normalize import (
    normalize_coordinates,
    denormalize_coordinates,
    validate_coordinate_space,
)


# Property-Based Tests


@given(
    raw_x=st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False),
    raw_y=st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False),
    scale_factor=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_normalization_preserves_information(raw_x: float, raw_y: float, scale_factor: float):
    """
    Property 1: Normalization Preserves Information
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    
    For any raw coordinates (x, y) with scale_factor > 0, normalizing to device points
    and denormalizing should recover the original coordinates within floating-point precision.
    """
    # Normalize coordinates
    normalized_x, normalized_y = normalize_coordinates(raw_x, raw_y, scale_factor)
    
    # Denormalize back to raw coordinates
    recovered_x, recovered_y = denormalize_coordinates(normalized_x, normalized_y, scale_factor)
    
    # Verify round-trip within floating-point tolerance
    assert abs(recovered_x - raw_x) < 0.001, f"X round-trip failed: {raw_x} -> {normalized_x} -> {recovered_x}"
    assert abs(recovered_y - raw_y) < 0.001, f"Y round-trip failed: {raw_y} -> {normalized_y} -> {recovered_y}"


# Unit Tests


def test_normalize_basic_example():
    """Test basic normalization example from spec: (400, 600) with scale 2.0 -> (200, 300)."""
    normalized_x, normalized_y = normalize_coordinates(400, 600, 2.0)
    assert normalized_x == 200.0
    assert normalized_y == 300.0


def test_denormalize_basic_example():
    """Test basic denormalization example: (200, 300) with scale 2.0 -> (400, 600)."""
    raw_x, raw_y = denormalize_coordinates(200.0, 300.0, 2.0)
    assert raw_x == 400.0
    assert raw_y == 600.0


def test_device_points_identity():
    """Test that device_points with scale 1.0 is identity transformation."""
    raw_x, raw_y = 150.0, 250.0
    normalized_x, normalized_y = normalize_coordinates(raw_x, raw_y, 1.0)
    assert normalized_x == raw_x
    assert normalized_y == raw_y


def test_negative_coordinates_preserved():
    """Test that negative coordinates are preserved through normalization."""
    raw_x, raw_y = -100.0, -200.0
    scale_factor = 2.0
    
    normalized_x, normalized_y = normalize_coordinates(raw_x, raw_y, scale_factor)
    assert normalized_x == -50.0
    assert normalized_y == -100.0
    
    # Verify round-trip
    recovered_x, recovered_y = denormalize_coordinates(normalized_x, normalized_y, scale_factor)
    assert recovered_x == raw_x
    assert recovered_y == raw_y


def test_normalize_zero_scale_factor_raises_error():
    """Test that scale_factor = 0 raises ValueError."""
    with pytest.raises(ValueError, match="scale_factor must be greater than 0"):
        normalize_coordinates(100, 200, 0)


def test_normalize_negative_scale_factor_raises_error():
    """Test that negative scale_factor raises ValueError."""
    with pytest.raises(ValueError, match="scale_factor must be greater than 0"):
        normalize_coordinates(100, 200, -1.0)


def test_denormalize_zero_scale_factor_raises_error():
    """Test that denormalize with scale_factor = 0 raises ValueError."""
    with pytest.raises(ValueError, match="scale_factor must be greater than 0"):
        denormalize_coordinates(100, 200, 0)


def test_denormalize_negative_scale_factor_raises_error():
    """Test that denormalize with negative scale_factor raises ValueError."""
    with pytest.raises(ValueError, match="scale_factor must be greater than 0"):
        denormalize_coordinates(100, 200, -1.0)


def test_validate_coordinate_space_valid():
    """Test that valid coordinate spaces pass validation."""
    validate_coordinate_space("device_points")
    validate_coordinate_space("screen_pixels")
    validate_coordinate_space("screenshot_pixels")


def test_validate_coordinate_space_invalid():
    """Test that invalid coordinate space raises ValueError."""
    with pytest.raises(ValueError, match="Invalid coordinate_space"):
        validate_coordinate_space("invalid_space")
    
    with pytest.raises(ValueError, match="Invalid coordinate_space"):
        validate_coordinate_space("")
    
    with pytest.raises(ValueError, match="Invalid coordinate_space"):
        validate_coordinate_space("Device_Points")  # Case sensitive
