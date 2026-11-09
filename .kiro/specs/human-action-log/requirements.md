# Requirements Document

## Introduction

Poltergeist is a system that makes human interventions visible to AI agents operating UIs (browsers, iOS simulator). When a human clicks something during an agent session—to dismiss a popup the agent cannot handle or correct a missed target—the agent currently remains unaware. This feature implements a human action log that records both human and agent clicks, exposes them through an MCP server, and flags mismatches where human corrections occurred.

## Glossary

- **Action_Log**: The in-memory data store that records click actions from both humans and agents
- **Click_Action**: A recorded event containing timestamp, normalized position (x, y coordinates in device points), raw coordinates, coordinate space, scale factor, actor type (human or agent), and the UI element identifier
- **MCP_Server**: The Model Context Protocol server that exposes the action log to agents and accepts agent click recordings
- **Mismatch**: A situation where an agent click is followed within 5 seconds by a human click, suggesting the human corrected the agent
- **UI_Element**: An identifier for the target of a click containing role and short label only, never long on-screen text
- **Coordinate_Scale_Problem**: A pattern where multiple Mismatches show a consistent offset ratio, suggesting systematic coordinate scaling issues
- **Device_Points**: The normalized coordinate space used for all position comparisons and offset calculations
- **Coordinate_Space**: The original coordinate system of a click (e.g., "screenshot_pixels", "screen_pixels", "device_points")
- **Scale_Factor**: The conversion ratio used to normalize raw coordinates into device points

## Requirements

### Requirement 1: Normalize Coordinates to Device Points

**User Story:** As a system operator, I want all click coordinates normalized to a single coordinate space, so that agent and human clicks can be compared accurately regardless of their original coordinate systems.

#### Acceptance Criteria

1. THE Action_Log SHALL store all Click_Action positions in device points
2. WHEN a Click_Action is recorded, THE Action_Log SHALL store the raw x-y coordinates, the Coordinate_Space identifier, and the Scale_Factor used for normalization
3. THE Action_Log SHALL normalize raw coordinates to device points by applying the Scale_Factor before storage
4. THE Action_Log SHALL support the following Coordinate_Space identifiers: "screenshot_pixels", "screen_pixels", "device_points"
5. WHEN raw coordinates are already in device points, THE Action_Log SHALL record a Scale_Factor of 1.0

### Requirement 2: Ingest Agent Click Actions

**User Story:** As an AI agent, I want to record my clicks through an MCP tool, so that my actions enter the same Action_Log as human clicks.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a tool named "record_agent_click"
2. WHEN "record_agent_click" is called with x, y, coordinate_space, scale_factor, and optional ui_element parameters, THE Action_Log SHALL record a Click_Action with actor type "agent"
3. THE Action_Log SHALL record the timestamp as UTC ISO 8601 with millisecond precision at the moment the click is ingested
4. THE Action_Log SHALL normalize the provided coordinates to device points using the provided Scale_Factor
5. THE Action_Log SHALL preserve the raw coordinates, Coordinate_Space, and Scale_Factor in the Click_Action

### Requirement 3: Ingest Human Click Actions

**User Story:** As a human observer component, I want to record human clicks through a programmatic interface, so that human interventions enter the Action_Log.

#### Acceptance Criteria

1. THE Action_Log SHALL expose a function named "record_human_click"
2. WHEN "record_human_click" is called with x, y, coordinate_space, scale_factor, and optional ui_element parameters, THE Action_Log SHALL record a Click_Action with actor type "human"
3. THE Action_Log SHALL record the timestamp as UTC ISO 8601 with millisecond precision at the moment the click is ingested
4. THE Action_Log SHALL normalize the provided coordinates to device points using the provided Scale_Factor
5. THE Action_Log SHALL preserve the raw coordinates, Coordinate_Space, and Scale_Factor in the Click_Action
6. THE Action_Log SHALL preserve the chronological order of all Click_Actions

### Requirement 4: Redact UI Element Information

**User Story:** As a privacy-conscious operator, I want to limit what UI element text is stored, so that sensitive on-screen content is not logged.

#### Acceptance Criteria

1. WHEN a UI_Element is recorded, THE Action_Log SHALL store only the role (e.g., "button", "link") and a short label (maximum 50 characters)
2. THE Action_Log SHALL NOT store long on-screen text in the UI_Element identifier
3. THE Action_Log SHALL support a redaction switch that, when enabled, omits the short label and stores only the role
4. WHEN the redaction switch is enabled, THE Action_Log SHALL record UI_Element with role only
5. WHEN the redaction switch is disabled, THE Action_Log SHALL record UI_Element with role and short label

### Requirement 5: Expose Human Actions via MCP Tool

**User Story:** As an AI agent, I want to query human actions since a given time, so that I can discover when a human intervened in my workflow.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a tool named "get_human_actions"
2. WHEN "get_human_actions" is called with a timestamp parameter (UTC ISO 8601 with millisecond precision), THE MCP_Server SHALL return all Click_Actions with actor type "human" recorded after that timestamp (exclusive)
3. WHEN "get_human_actions" is called without a timestamp parameter, THE MCP_Server SHALL return all human Click_Actions in the Action_Log
4. THE MCP_Server SHALL return Click_Actions in chronological order (oldest first)
5. THE MCP_Server SHALL include timestamp, normalized position (device points), raw coordinates, Coordinate_Space, Scale_Factor, and UI_Element identifier for each returned Click_Action

### Requirement 6: Detect Agent-Human Click Mismatches

**User Story:** As an AI agent, I want to be notified when my click was followed by a human click, so that I can learn my action failed or missed the target.

#### Acceptance Criteria

1. WHEN an agent Click_Action is followed within 5 seconds (exclusive) by a human Click_Action, THE MCP_Server SHALL flag a Mismatch
2. WHEN multiple agent clicks occur within the 5-second window before a human click, THE MCP_Server SHALL match the human click to the closest agent click by distance (using normalized device point coordinates)
3. THE MCP_Server SHALL calculate the offset vector (delta_x, delta_y) in device points between the agent click position and the human click position for each Mismatch
4. THE MCP_Server SHALL NOT filter Mismatches by distance threshold; large offsets SHALL still be flagged as Mismatches
5. THE MCP_Server SHALL include the Mismatch flag, offset vector, and both Click_Actions when returning results that contain a flagged pair
6. WHEN the same UI_Element is targeted by both clicks but positions differ, THE MCP_Server SHALL include the UI_Element identifier in the Mismatch report

### Requirement 7: Detect Coordinate Scale Problems

**User Story:** As an AI agent, I want to know if my click misses show a consistent scaling pattern, so that I can correct systematic coordinate errors rather than guessing.

#### Acceptance Criteria

1. FOR EACH Mismatch, THE MCP_Server SHALL compute scale_x = agent_x / human_x and scale_y = agent_y / human_y
2. THE MCP_Server SHALL exclude samples from scale calculation where the human coordinate is near zero
3. WHEN at least three valid scale samples exist with a relative spread (standard deviation divided by mean) of 10% or less in both dimensions, THE MCP_Server SHALL flag a Coordinate_Scale_Problem
4. THE MCP_Server SHALL calculate the average scale factor (mean of scale ratios) for x and y dimensions separately
5. THE MCP_Server SHALL include the scale factors (scale_x, scale_y) and sample size in the Coordinate_Scale_Problem report
6. WHEN "get_human_actions" returns results containing a Coordinate_Scale_Problem, THE MCP_Server SHALL include the Coordinate_Scale_Problem report alongside the Mismatch data

### Requirement 8: Persist Action Log In Memory Only

**User Story:** As a system operator, I want the Action_Log to exist only in memory during a session, so that no persistent files accumulate on disk.

#### Acceptance Criteria

1. THE Action_Log SHALL store all Click_Actions in memory only
2. THE Action_Log SHALL NOT persist Click_Actions to disk or any file system
3. WHEN the MCP_Server process terminates, THE Action_Log SHALL be lost

### Requirement 9: Clear Action Log

**User Story:** As a system operator, I want to clear old action logs, so that the system does not accumulate unbounded data across sessions.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a tool named "clear_action_log"
2. WHEN "clear_action_log" is called with a timestamp parameter (UTC ISO 8601 with millisecond precision), THE Action_Log SHALL remove all Click_Actions recorded before that timestamp (exclusive)
3. WHEN "clear_action_log" is called without a timestamp parameter, THE Action_Log SHALL remove all Click_Actions
4. THE MCP_Server SHALL return the count of removed Click_Actions after clearing

