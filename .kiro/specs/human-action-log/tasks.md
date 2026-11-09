# Implementation Plan: Human Action Log

## Overview

This implementation builds an MCP server that records click actions from AI agents and human operators, normalizes coordinates to a common coordinate space (device points), and detects patterns where human clicks follow agent clicks—indicating the agent missed its target. The system uses in-memory storage, supports multiple coordinate systems, and exposes functionality through MCP tools and an HTTP endpoint.

## Tasks

- [ ] 1. Set up project structure and verify MCP SDK
  - Install MCP Python SDK: `pip install mcp` (version 2.3.0)
  - Create project directory structure: `poltergeist/server.py`, `poltergeist/action_log.py`, `tests/`
  - Set up pytest with Hypothesis for property tests: `pip install pytest hypothesis`
  - Create minimal hello-world MCP server using verified SDK patterns:
    - Server: `from mcp.server import MCPServer` (FastMCP no longer exists in 2.x)
    - Tools: `@mcp.tool()` decorator
    - Run with stdio: `mcp.run(transport="stdio")`
    - Run with HTTP: `mcp.run(transport="streamable-http", host="127.0.0.1", port=8765)` (default host is 127.0.0.1)
    - Custom HTTP routes: `@mcp.custom_route("/human-click", methods=["POST"])` with async handler `(request: Request) -> JSONResponse` (starlette)
  - Write one test that verifies the hello tool works over stdio:
    - Client imports: `from mcp import Client, StdioServerParameters`
    - Stdio client: `Client(StdioServerParameters(command=sys.executable, args=["server.py"]))`
    - HTTP client: `Client("http://127.0.0.1:8765/mcp")`
  - Document verified facts in `docs/mcp_sdk_reference.md`:
    - Installation: `pip install mcp` (CLI tools need `mcp[cli]`, but not required for server)
    - Run server: `python server.py` (do not rely on `mcp dev` or `mcp run` commands)
    - All verified imports, decorators, and initialization patterns
  - _Requirements: All (foundation for implementation)_

- [x] 2. Implement core data models
  - [x] 2.1 Create UIElement, ClickAction, Mismatch, CoordinateScaleProblem, and HumanActionsResponse dataclasses
    - Define dataclasses with proper type hints
    - Include all fields from design specification
    - Add serialization helpers (asdict compatibility)
    - _Requirements: 1.1, 1.2, 2.3, 3.3, 4.1, 4.2, 6.5, 7.5_
  
  - [ ]* 2.2 Write unit tests for data models
    - Test dataclass instantiation
    - Test field validation
    - Test serialization to dict/JSON
    - _Requirements: 1.1, 1.2, 2.3, 3.3_

- [x] 3. Implement coordinate normalization
  - [x] 3.1 Create coordinate normalization functions
    - Implement normalize_coordinates(raw_x, raw_y, scale_factor) -> (normalized_x, normalized_y)
    - Implement denormalize_coordinates for round-trip testing
    - Add validation for scale_factor > 0
    - Support coordinate_space enum: "device_points", "screen_pixels", "screenshot_pixels"
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [x] 3.2 Write property test for coordinate normalization
    - **Property 1: Normalization Preserves Information**
    - **Validates: Requirements 1.1, 1.3, 1.4, 1.5**
    - Use Hypothesis to generate random coordinates, coordinate spaces, and scale factors
    - Verify normalize → denormalize round-trip recovers original coordinates
    - _Requirements: 1.1, 1.3, 1.4, 1.5_
  
  - [ ]* 3.3 Write unit tests for coordinate normalization
    - Test examples: (400, 600) with scale 2.0 → (200, 300)
    - Test device_points with scale 1.0 (identity)
    - Test scale_factor = 0 raises validation error
    - Test negative coordinates are preserved
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 4. Checkpoint - Coordinate normalization validated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Action Log Store
  - [x] 5.1 Create ActionLog class with in-memory storage
    - Initialize empty list for storing ClickActions
    - Add redaction flag (configurable via environment variable)
    - Implement timestamp generation (UTC ISO 8601 with milliseconds)
    - _Requirements: 3.6, 4.3, 4.4, 8.1_
  
  - [x] 5.2 Implement record_agent_click method
    - Accept x, y, coordinate_space, scale_factor, optional ui_element
    - Generate timestamp at ingestion time
    - Normalize coordinates using scale_factor
    - Create ClickAction with actor="agent"
    - Store raw coordinates, coordinate_space, scale_factor
    - Apply UI element redaction if enabled
    - Append to action log list
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4_
  
  - [x] 5.3 Implement record_human_click method
    - Accept x, y, coordinate_space, scale_factor, optional ui_element
    - Generate timestamp at ingestion time
    - Normalize coordinates using scale_factor
    - Create ClickAction with actor="human"
    - Store raw coordinates, coordinate_space, scale_factor
    - Apply UI element redaction if enabled
    - Append to action log list
    - Preserve chronological order
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4_
  
  - [ ]* 5.4 Write unit tests for action recording
    - Test agent click recording creates correct ClickAction
    - Test human click recording creates correct ClickAction
    - Test timestamp format (ISO 8601 with milliseconds, UTC)
    - Test UI element redaction enabled/disabled
    - Test label truncation to 50 characters
    - Test chronological order preservation
    - _Requirements: 2.2, 2.3, 3.2, 3.3, 3.6, 4.1, 4.2, 4.3, 4.4_

- [x] 6. Implement mismatch detection algorithm
  - [x] 6.1 Create detect_mismatches pure function
    - Accept List[ClickAction] as input (chronologically ordered)
    - For each human click, scan backward 5 seconds (exclusive) for agent clicks
    - Implement one-to-one matching (agent clicks matched once only)
    - Calculate Euclidean distance in device points
    - Select closest agent click when multiple candidates exist
    - Calculate offset vector (human_x - agent_x, human_y - agent_y)
    - Return List[Mismatch]
    - Implement as pure function (no clock reads, deterministic)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [x] 6.2 Write property test for one-to-one human click matching
    - **Property 2: One-to-One Human Click Matching**
    - **Validates: Requirements 6.1, 6.2**
    - Generate random action lists with Hypothesis
    - Verify each human click matches at most one agent click
    - _Requirements: 6.1, 6.2_
  
  - [x] 6.3 Write property test for one-to-one agent click matching
    - **Property 3: One-to-One Agent Click Matching**
    - **Validates: Requirements 6.1, 6.2**
    - Generate random action lists with Hypothesis
    - Verify each agent click matches at most one human click
    - _Requirements: 6.1, 6.2_
  
  - [x] 6.4 Write property test for minimum distance matching
    - **Property 4: Minimum Distance Matching**
    - **Validates: Requirements 6.2**
    - Generate human click with 2-5 agent clicks in window
    - Verify matched agent click is closest by Euclidean distance
    - _Requirements: 6.2_
  
  - [x] 6.5 Write property test for temporal window boundary
    - **Property 6: Temporal Window Boundary**
    - **Validates: Requirements 6.1**
    - Generate agent and human clicks with time delta ≥ 5 seconds
    - Verify no mismatch created (exclusive boundary)
    - _Requirements: 6.1_
  
  - [x] 6.6 Write unit tests for mismatch detection
    - Test agent click followed 2s later by human click creates mismatch
    - Test agent click followed 6s later by human click creates no mismatch
    - Test human click with no prior agent clicks creates no mismatch
    - Test multiple agent clicks in window—closest is matched
    - Test agent click matched once is not re-matched
    - Test identical positions create zero-offset mismatch
    - Test exact 5-second boundary (exclusive)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 7. Implement coordinate scale problem detection
  - [x] 7.1 Create detect_scale_problem pure function
    - Accept List[Mismatch] as input
    - Calculate scale_x = agent_x / human_x, scale_y = agent_y / human_y for each mismatch
    - Exclude samples where |human_x| < 1.0 or |human_y| < 1.0
    - Calculate mean and standard deviation of scale ratios
    - Calculate relative spread (std_dev / mean)
    - Flag scale problem if ≥3 samples AND relative spread ≤ 10% in both dimensions
    - Return Optional[CoordinateScaleProblem]
    - Implement as pure function
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  
  - [x] 7.2 Write property test for scale factor recovery
    - **Property 5: Scale Factor Recovery**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    - Generate agent clicks and scale factor k with Hypothesis
    - Generate human corrections at agent_position / k
    - Constrain generator so every human coordinate is at least 1.0 (otherwise sample is skipped as near zero)
    - Verify scale problem IS flagged (exact data, zero relative spread)
    - Verify detected scale_x and scale_y recover k within 1% error
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [x] 7.3 Write unit tests for scale problem detection
    - Test 3 mismatches with consistent 2x ratio flag scale problem
    - Test 3 mismatches with inconsistent ratios (>10% spread) do not flag
    - Test 2 mismatches do not trigger detection (need 3+)
    - Test mismatches with human coordinates near zero are excluded
    - Test all mismatches near zero produce no scale problem
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. Checkpoint - Core algorithms validated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement ActionLog query methods
  - [x] 9.1 Implement get_human_actions method
    - Accept optional since_timestamp parameter (UTC ISO 8601)
    - Filter human clicks after timestamp (exclusive)
    - If no timestamp, return all human actions
    - Call detect_mismatches on full action list
    - Call detect_scale_problem on mismatches
    - Return HumanActionsResponse with chronological order (oldest first)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.5, 6.6, 7.6_
  
  - [x] 9.2 Implement clear method
    - Accept optional before_timestamp parameter (UTC ISO 8601)
    - Remove actions before timestamp (exclusive)
    - If no timestamp, remove all actions
    - Return count of removed actions
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x]* 9.3 Write unit tests for query methods
    - Test get_human_actions filters by timestamp correctly
    - Test get_human_actions with no timestamp returns all
    - Test chronological ordering (oldest first)
    - Test clear with timestamp removes correct actions
    - Test clear without timestamp removes all
    - Test clear on empty log returns 0
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 9.1, 9.2, 9.3, 9.4_
  
  - [x] 9.4 Write property test for coordinate space independence
    - **Property 7: Coordinate Space Independence**
    - **Validates: Requirements 1.1, 1.4**
    - Generate same device point target with different coordinate spaces
    - Verify normalized positions are identical
    - _Requirements: 1.1, 1.4_

- [x] 10. Implement MCP server with tools
  - [x] 10.1 Create MCP server initialization
    - Use verified SDK import paths from Phase 0
    - Initialize MCPServer("poltergeist-human-action-log")
    - Create global ActionLog instance
    - Configure redaction from environment variable POLTERGEIST_REDACT_UI_LABELS
    - _Requirements: 2.1, 4.3_
  
  - [x] 10.2 Implement record_agent_click MCP tool
    - Define tool with @mcp.tool() decorator
    - Accept x, y, coordinate_space, scale_factor, optional ui_element_role, ui_element_label
    - Validate coordinate_space enum
    - Validate scale_factor > 0
    - Call action_log.record_agent_click
    - Return success response with timestamp
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [x] 10.3 Implement get_human_actions MCP tool
    - Define tool with @mcp.tool() decorator
    - Accept optional since_timestamp parameter
    - Validate timestamp format if provided
    - Call action_log.get_human_actions
    - Serialize HumanActionsResponse to dict
    - Return human_actions, mismatches, coordinate_scale_problem
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.5, 7.6_
  
  - [x] 10.4 Implement clear_action_log MCP tool
    - Define tool with @mcp.tool() decorator
    - Accept optional before_timestamp parameter
    - Validate timestamp format if provided
    - Call action_log.clear
    - Return removed_count
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x]* 10.5 Write integration tests for MCP tools
    - Test record_agent_click over stdio transport
    - Test get_human_actions over stdio transport
    - Test clear_action_log over stdio transport
    - Test all tools over Streamable HTTP transport
    - Test invalid coordinate_space returns error
    - Test invalid timestamp format returns error
    - Test zero scale_factor returns error
    - _Requirements: 2.1, 2.2, 5.1, 5.2, 9.1, 9.2_

- [x] 11. Implement HTTP endpoint for human clicks
  - [x] 11.1 Add HTTP POST /human-click endpoint
    - Configure HTTP server to bind to 127.0.0.1 (localhost only)
    - Accept JSON payload with x, y, coordinate_space, scale_factor, optional ui_element
    - Validate required fields and types
    - Validate coordinate_space enum
    - Validate scale_factor > 0
    - Call action_log.record_human_click
    - Return JSON response with status="recorded", actor="human", timestamp
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [x]* 11.2 Write integration tests for HTTP endpoint
    - Test POST valid payload records human action
    - Test response includes timestamp and actor="human"
    - Test invalid JSON returns 400 Bad Request
    - Test missing required fields returns 400 Bad Request
    - Test endpoint binds to 127.0.0.1 only
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 12. Checkpoint - Server implementation complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Add error handling and logging
  - [x] 13.1 Implement validation error handling
    - Add error messages for invalid coordinate_space
    - Add error messages for invalid scale_factor
    - Add error messages for invalid timestamp format
    - Ensure UI element labels are truncated to 50 characters
    - Log warnings for truncated labels
    - _Requirements: 4.2_
  
  - [x] 13.2 Add logging configuration
    - Configure logging to stderr
    - Set log level from POLTERGEIST_LOG_LEVEL environment variable (default: INFO)
    - Log INFO for tool invocations
    - Log WARNING for validation failures
    - Log ERROR for runtime exceptions
    - _Requirements: All (observability)_
  
  - [x]* 13.3 Write tests for error handling
    - Test invalid coordinate_space error message
    - Test zero scale_factor error message
    - Test invalid timestamp error message
    - Test label truncation to 50 characters
    - _Requirements: 4.2_

- [x] 14. End-to-end workflow tests
  - [x]* 14.1 Write full workflow integration test
    - Record agent click at (100, 100)
    - Wait 2 seconds (simulated with timestamp manipulation)
    - POST human click at (110, 105) to /human-click
    - Call get_human_actions
    - Verify 1 human action, 1 mismatch with offset (10, 5)
    - Verify no coordinate scale problem (only 1 mismatch)
    - _Requirements: 2.1, 3.1, 5.1, 6.1, 6.2, 6.3_
  
  - [x]* 14.2 Write coordinate scale problem end-to-end test
    - Record 5 agent clicks with systematic 2x offset
    - POST 5 human corrections via /human-click
    - Call get_human_actions
    - Verify coordinate scale problem flagged
    - Verify scale_x ≈ 2.0, scale_y ≈ 2.0
    - Verify relative spread < 10%
    - _Requirements: 6.1, 6.2, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [ ] 15. Create deployment configuration
  - [ ] 15.1 Create package configuration
    - Create setup.py or pyproject.toml
    - Specify dependencies (mcp SDK, Python 3.11+)
    - Define entry points for server
    - _Requirements: All (deployment)_
  
  - [ ] 15.2 Document deployment and usage
    - Document installation steps (pip install)
    - Document how to run with stdio transport (mcp dev)
    - Document how to run with HTTP transport (mcp run)
    - Document environment variables (POLTERGEIST_REDACT_UI_LABELS, POLTERGEIST_LOG_LEVEL)
    - Provide client integration examples (Python MCP client)
    - Document HTTP endpoint usage examples (curl, Swift URLSession, JavaScript fetch)
    - _Requirements: All (documentation)_

- [x] 16. Final checkpoint - Complete system validated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties from design
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end workflows
- The system uses Python 3.11+ with the MCP Python SDK
- All coordinate normalization and mismatch detection logic is implemented as pure functions for testability
- HTTP endpoint binds to 127.0.0.1 by default for security

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1"]
    },
    {
      "id": 1,
      "tasks": ["2.1"]
    },
    {
      "id": 2,
      "tasks": ["2.2", "3.1"]
    },
    {
      "id": 3,
      "tasks": ["3.2", "3.3"]
    },
    {
      "id": 4,
      "tasks": ["5.1"]
    },
    {
      "id": 5,
      "tasks": ["5.2", "5.3"]
    },
    {
      "id": 6,
      "tasks": ["5.4", "6.1"]
    },
    {
      "id": 7,
      "tasks": ["6.2", "6.3", "6.4", "6.5", "6.6", "7.1"]
    },
    {
      "id": 8,
      "tasks": ["7.2", "7.3"]
    },
    {
      "id": 9,
      "tasks": ["9.1", "9.2"]
    },
    {
      "id": 10,
      "tasks": ["9.3", "9.4", "10.1"]
    },
    {
      "id": 11,
      "tasks": ["10.2", "10.3", "10.4"]
    },
    {
      "id": 12,
      "tasks": ["10.5", "11.1"]
    },
    {
      "id": 13,
      "tasks": ["11.2", "13.1", "13.2"]
    },
    {
      "id": 14,
      "tasks": ["13.3", "14.1", "14.2", "15.1"]
    },
    {
      "id": 15,
      "tasks": ["15.2"]
    }
  ]
}
```
