"""Integration tests for /human-click HTTP endpoint."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from mcp import Client


def get_server_path():
    """Get absolute path to server.py"""
    return Path(__file__).parent.parent / "poltergeist" / "server.py"


def lan_address():
    """This machine's non-loopback IPv4 address, or None when it has none."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # A UDP "connect" sends nothing; it only makes the OS pick a source address.
        probe.connect(("192.0.2.1", 9))
        address = probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()
    return None if address.startswith("127.") else address


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


def post_human_click(port, payload):
    """Send POST request to /human-click endpoint."""
    import urllib.request
    
    url = f"http://127.0.0.1:{port}/human-click"
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_valid_payload_records_human_action():
    """Test that valid payload records a human action visible through get_human_actions."""
    async def run_test():
        port = find_free_port()
        
        # Start server
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
            
            # POST human click
            status, response = post_human_click(port, {
                "x": 400.0,
                "y": 600.0,
                "coordinate_space": "screen_pixels",
                "scale_factor": 2.0,
                "ui_element": {
                    "role": "button",
                    "label": "Submit"
                }
            })
            
            assert status == 200
            assert response["status"] == "recorded"
            assert response["actor"] == "human"
            assert "timestamp" in response
            
            # Verify it's visible through get_human_actions
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                result = await client.call_tool("get_human_actions", {})
                result_dict = json.loads(result.content[0].text)
                
                assert len(result_dict["human_actions"]) == 1
                human_action = result_dict["human_actions"][0]
                assert human_action["actor"] == "human"
                assert human_action["raw_x"] == 400.0
                assert human_action["raw_y"] == 600.0
                assert human_action["normalized_x"] == 200.0  # 400 / 2.0
                assert human_action["normalized_y"] == 300.0  # 600 / 2.0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


def test_response_has_actor_human_and_timestamp():
    """Test that response includes actor=human and a timestamp."""
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
            
            status, response = post_human_click(port, {
                "x": 100.0,
                "y": 200.0,
                "coordinate_space": "device_points",
                "scale_factor": 1.0
            })
            
            assert status == 200
            assert response["actor"] == "human"
            assert "timestamp" in response
            # Verify timestamp format (ISO 8601 with milliseconds and Z)
            assert response["timestamp"].endswith("Z")
            assert "T" in response["timestamp"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


def test_invalid_json_returns_400():
    """Test that invalid JSON returns 400 Bad Request."""
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
            
            # Send invalid JSON
            import urllib.request
            url = f"http://127.0.0.1:{port}/human-click"
            req = urllib.request.Request(
                url,
                data=b"not json",
                headers={'Content-Type': 'application/json'}
            )
            
            try:
                urllib.request.urlopen(req)
                assert False, "Should have returned 400"
            except urllib.error.HTTPError as e:
                assert e.code == 400
                response = json.loads(e.read().decode('utf-8'))
                assert "error" in response
                assert "Invalid JSON" in response["error"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


def test_missing_fields_return_400():
    """Test that missing required fields return 400 Bad Request."""
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
            
            # Send payload missing required fields
            status, response = post_human_click(port, {
                "x": 100.0,
                # Missing y, coordinate_space, scale_factor
            })
            
            assert status == 400
            assert "error" in response
            assert "Missing required fields" in response["error"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())


def test_server_binds_localhost_only():
    """Test that the server binds to 127.0.0.1 only."""
    # This test verifies the default host is 127.0.0.1
    # We can't easily test that it's NOT accessible from other IPs in CI,
    # but we can verify the environment variable defaults to 127.0.0.1
    
    async def run_test():
        port = find_free_port()
        
        env = os.environ.copy()
        env["POLTERGEIST_TRANSPORT"] = "streamable-http"
        env["POLTERGEIST_PORT"] = str(port)
        # Don't set POLTERGEIST_HOST - should default to 127.0.0.1
        
        process = subprocess.Popen(
            [sys.executable, str(get_server_path().resolve())],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            assert wait_for_server(port), "Server did not start in time"
            
            # Verify we can connect to 127.0.0.1
            status, response = post_human_click(port, {
                "x": 100.0,
                "y": 200.0,
                "coordinate_space": "device_points",
                "scale_factor": 1.0
            })
            
            assert status == 200
            assert response["status"] == "recorded"

            # The same port must NOT answer on this machine's non-loopback address.
            lan_ip = lan_address()
            if lan_ip is not None:
                with pytest.raises((ConnectionRefusedError, OSError)):
                    with socket.create_connection((lan_ip, port), timeout=2):
                        pass
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    asyncio.run(run_test())
