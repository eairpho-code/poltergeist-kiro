# MCP SDK 2.x Reference

This document contains verified patterns for MCP SDK 2.3.0 based on successful implementation.

## Server Setup

### Basic Server
```python
from mcp.server import MCPServer

mcp = MCPServer("server-name")
```

**Note:** `FastMCP` does not exist in SDK 2.x. Use `MCPServer` instead.

**Note:** The old 1.x API `from mcp.server import Server` is deprecated and does not work in 2.x.

## Tools

### Defining Tools
```python
@mcp.tool()
def tool_name(param: str) -> str:
    """Tool description."""
    return "result"
```

Tools are automatically registered with the server using the `@mcp.tool()` decorator.

## Transports

### Stdio Transport
```python
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

This is the default transport for local development and testing with MCP Inspector.

### HTTP Transport
```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8765)
```

Use Streamable HTTP for deployment where agents connect over HTTP.

## Custom HTTP Routes

For custom HTTP endpoints (e.g., for human click ingestion), use the `@mcp.custom_route()` decorator:

```python
from starlette.requests import Request
from starlette.responses import JSONResponse

@mcp.custom_route("/human-click", methods=["POST"])
async def handle_human_click(request: Request):
    data = await request.json()
    # Process the click data
    return JSONResponse({"status": "recorded"})
```

## Clients

### Stdio Client
```python
from mcp import Client, StdioServerParameters

server_params = StdioServerParameters(
    command=sys.executable,
    args=["/absolute/path/to/server.py"],
)

async with Client(server_params) as client:
    result = await client.call_tool("tool_name", {"param": "value"})
```

### HTTP Client
```python
from mcp import Client

async with Client("http://127.0.0.1:8765/mcp") as client:
    result = await client.call_tool("tool_name", {"param": "value"})
```

## Starting servers

The `mcp` command line tool needs `mcp[cli]`, so this project starts servers directly with Python:

```bash
venv/bin/python poltergeist/server.py
```

## Testing

### Testing with pytest
Use the `mcp` client library to test servers over stdio:

```python
import asyncio
import sys
from pathlib import Path
from mcp import Client, StdioServerParameters


def test_tool():
    async def run_test():
        server_path = Path(__file__).parent.parent / "server.py"
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_path.resolve())],
        )
        
        async with Client(server_params) as client:
            result = await client.call_tool("tool_name", {"param": "value"})
            assert "expected" in str(result)
    
    asyncio.run(run_test())
```

**Note:** If `pytest-asyncio` is not installed, use `asyncio.run()` inside a normal test function instead of async test functions.

## Key Differences from 1.x API

- **Import:** Use `from mcp.server import MCPServer` (not `Server`)
- **Decorator:** Use `@mcp.tool()` (not `@server.call_tool()` and `@server.list_tools()`)
- **Run:** Use `mcp.run(transport="stdio")` (not `asyncio.run(server.run(...))`)
- **Schema:** Tool schemas are automatically generated from type hints
