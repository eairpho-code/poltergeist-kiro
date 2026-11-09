"""Integration tests for MCP server tools over stdio and HTTP transports."""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters


def get_server_path():
    """Get absolute path to server.py"""
    return Path(__file__).parent.parent / "poltergeist" / "server.py"


# --- Stdio Transport Tests ---

def test_record_agent_click_stdio():
    """Test record_agent_click tool over stdio transport."""
    async def run_test():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(get_server_path().resolve())],
        )
        
        async with Client(server_params) as client:
            result = await client.call_tool("record_agent_click", {
                "x": 100.0,
                "y": 200.0,
                "coordinate_space": "device_points",
                "scale_factor": 1.0,
                "ui_element_role": "button",
                "ui_element_label": "Submit"
            })
            
            # Check result structure
            assert result.content[0].text is not None
            result_dict = json.loads(result.content[0].text)
            assert result_dict["status"] == "recorded"
            assert result_dict["actor"] == "agent"
            assert "timestamp" in result_dict
    
    asyncio.run(run_test())


def test_get_human_actions_stdio():
    """Test get_human_actions tool over stdio transport."""
    async def run_test():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(get_server_path().resolve())],
        )
        
        async with Client(server_params) as client:
            # Record an agent click and human click first
            await client.call_tool("record_agent_click", {
                "x": 100.0,
                "y": 200.0,
                "coordinate_space": "device_points",
                "scale_factor": 1.0
            })
            
            # Query human actions (should be empty since we only recorded agent)
            result = await client.call_tool("get_human_actions", {})
            
            result_dict = json.loads(result.content[0].text)
            assert "human_actions" in result_dict
            assert "mismatches" in result_dict
            assert "coordinate_scale_problem" in result_dict
    
    asyncio.run(run_test())


def test_clear_action_log_stdio():
    """Test clear_action_log tool over stdio transport."""
    async def run_test():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(get_server_path().resolve())],
        )
        
        async with Client(server_params) as client:
            # Record some actions
            await client.call_tool("record_agent_click", {
                "x": 100.0,
                "y": 200.0,
                "coordinate_space": "device_points",
                "scale_factor": 1.0
            })
            
            # Clear all
            result = await client.call_tool("clear_action_log", {})
            
            result_dict = json.loads(result.content[0].text)
            assert "removed_count" in result_dict
            assert result_dict["removed_count"] == 1
    
    asyncio.run(run_test())


# --- HTTP Transport Tests ---

def find_free_port():
    """Find a free port for testing."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_server(port, timeout=10):
    """Wait until the server accepts connections."""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', port))
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


def test_record_agent_click_http():
    """Test record_agent_click tool over Streamable HTTP transport."""
    async def run_test():
        port = find_free_port()
        
        # Start server as subprocess
        env = os.environ.copy()
        env["POLTERGEIST_TRANSPORT"] = "streamable-http"
        env["POLTERGEIST_PORT"] = str(port)
        
        process = subprocess.Popen(
            [sys.executable, str(get_server_path().resolve())],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            # Wait for server to start
            assert wait_for_server(port), "Server did not start in time"
            
            # Connect with HTTP client
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                result = await client.call_tool("record_agent_click", {
                    "x": 100.0,
                    "y": 200.0,
                    "coordinate_space": "device_points",
                    "scale_factor": 1.0,
                    "ui_element_role": "button",
                    "ui_element_label": "Submit"
                })
                
                result_dict = json.loads(result.content[0].text)
                assert result_dict["status"] == "recorded"
                assert result_dict["actor"] == "agent"
        finally:
            # Always terminate the server
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


def test_get_human_actions_http():
    """Test get_human_actions tool over Streamable HTTP transport."""
    async def run_test():
        port = find_free_port()
        
        env = os.environ.copy()
        env["POLTERGEIST_TRANSPORT"] = "streamable-http"
        env["POLTERGEIST_PORT"] = str(port)
        
        process = subprocess.Popen(
            [sys.executable, str(get_server_path().resolve())],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            assert wait_for_server(port), "Server did not start in time"
            
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                result = await client.call_tool("get_human_actions", {})
                
                result_dict = json.loads(result.content[0].text)
                assert "human_actions" in result_dict
                assert "mismatches" in result_dict
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


def test_clear_action_log_http():
    """Test clear_action_log tool over Streamable HTTP transport."""
    async def run_test():
        port = find_free_port()
        
        env = os.environ.copy()
        env["POLTERGEIST_TRANSPORT"] = "streamable-http"
        env["POLTERGEIST_PORT"] = str(port)
        
        process = subprocess.Popen(
            [sys.executable, str(get_server_path().resolve())],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            assert wait_for_server(port), "Server did not start in time"
            
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                result = await client.call_tool("clear_action_log", {})
                
                result_dict = json.loads(result.content[0].text)
                assert "removed_count" in result_dict
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


# --- Error Handling Tests ---


def _call_over_stdio(tool, arguments):
    """Call one tool on a fresh stdio server and return the raw result."""
    async def run_test():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(get_server_path().resolve())],
        )
        async with Client(server_params) as client:
            return await client.call_tool(tool, arguments)

    return asyncio.run(run_test())


def test_invalid_coordinate_space_error():
    """An invalid coordinate_space is a tool error whose message reaches the agent."""
    result = _call_over_stdio("record_agent_click", {
        "x": 100.0,
        "y": 200.0,
        "coordinate_space": "invalid_space",
        "scale_factor": 1.0,
    })
    assert result.is_error
    assert "Invalid coordinate_space" in result.content[0].text


def test_zero_scale_factor_error():
    """A scale_factor of 0 is a tool error whose message reaches the agent."""
    result = _call_over_stdio("record_agent_click", {
        "x": 100.0,
        "y": 200.0,
        "coordinate_space": "device_points",
        "scale_factor": 0.0,
    })
    assert result.is_error
    assert "scale_factor must be greater than 0" in result.content[0].text


def test_invalid_timestamp_format_error():
    """A bad timestamp is a tool error whose message reaches the agent."""
    result = _call_over_stdio("get_human_actions", {"since_timestamp": "not-a-timestamp"})
    assert result.is_error
    assert "timestamp must be UTC ISO 8601" in result.content[0].text


def test_clear_with_invalid_timestamp_error():
    """clear_action_log rejects a bad timestamp the same way."""
    result = _call_over_stdio("clear_action_log", {"before_timestamp": "yesterday"})
    assert result.is_error
    assert "timestamp must be UTC ISO 8601" in result.content[0].text
