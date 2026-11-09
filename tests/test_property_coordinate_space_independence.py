"""Property test: Coordinate space independence (Property 7).

For any click target in device points, the normalized position should be
invariant across different coordinate_space labels and corresponding scale_factors
that represent the same physical location.
"""

import pytest
from hypothesis import given, strategies as st

from poltergeist.action_log import ActionLog


@given(
    device_x=st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    device_y=st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    scale=st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False),
)
def test_coordinate_space_independence(device_x, device_y, scale):
    """
    The same physical point expressed in different coordinate spaces with
    matching scale factors normalizes to the same device point.
    """
    log = ActionLog()
    
    # Record the same physical point using different coordinate spaces
    # Case 1: Already in device points (scale = 1.0)
    log.record_agent_click(
        x=device_x,
        y=device_y,
        coordinate_space="device_points",
        scale_factor=1.0
    )
    
    # Case 2: In screen_pixels with given scale factor
    raw_x = device_x * scale
    raw_y = device_y * scale
    log.record_agent_click(
        x=raw_x,
        y=raw_y,
        coordinate_space="screen_pixels",
        scale_factor=scale
    )
    
    # Case 3: In screenshot_pixels with same scale factor
    log.record_agent_click(
        x=raw_x,
        y=raw_y,
        coordinate_space="screenshot_pixels",
        scale_factor=scale
    )
    
    # All three should normalize to the same device point position
    # (within floating-point tolerance)
    tolerance = 0.001
    
    click1 = log._actions[0]
    click2 = log._actions[1]
    click3 = log._actions[2]
    
    assert abs(click1.normalized_x - device_x) < tolerance
    assert abs(click1.normalized_y - device_y) < tolerance
    
    assert abs(click2.normalized_x - device_x) < tolerance
    assert abs(click2.normalized_y - device_y) < tolerance
    
    assert abs(click3.normalized_x - device_x) < tolerance
    assert abs(click3.normalized_y - device_y) < tolerance
    
    # Verify they're all the same (within tolerance)
    assert abs(click1.normalized_x - click2.normalized_x) < tolerance
    assert abs(click1.normalized_y - click2.normalized_y) < tolerance
    
    assert abs(click2.normalized_x - click3.normalized_x) < tolerance
    assert abs(click2.normalized_y - click3.normalized_y) < tolerance
