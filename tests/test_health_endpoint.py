"""Integration test for health endpoint."""

import asyncio
import pytest
from aiohttp import ClientSession


@pytest.mark.asyncio
async def test_health_endpoint_integration():
    """Test that health endpoint returns correct response structure."""
    import os
    import sys
    import threading
    import time
    
    # Bootstrap path
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    
    # Set env vars
    os.environ["DB_MODE"] = "sqlite"
    
    # Import after path setup
    from scripts.run_local import _run_health_server_thread
    
    # Start health server in background
    port = 8081  # Use different port to avoid conflicts
    health_thread = threading.Thread(
        target=_run_health_server_thread,
        args=(port,),
        daemon=True,
        name="test-health-server"
    )
    health_thread.start()
    
    # Give server time to start
    time.sleep(1)
    
    # Test endpoint
    async with ClientSession() as session:
        async with session.get(f"http://localhost:{port}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            
            # Validate response structure
            assert "status" in data
            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert "version" in data
            
            # Validate timestamp is ISO 8601 format
            from datetime import datetime
            datetime.fromisoformat(data["timestamp"].replace("+00:00", ""))
            
            # Version should be from pyproject.toml
            assert data["version"] in ["0.1.0", "unknown"]


def test_health_response_structure():
    """Test health handler response structure without server."""
    import os
    import sys
    
    # Bootstrap path
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    
    os.environ["DB_MODE"] = "sqlite"
    
    from scripts.run_local import _health_handler
    
    # Mock request object
    class MockRequest:
        pass
    
    # Test handler
    result = asyncio.run(_health_handler(MockRequest()))
    
    # Check it's a web.Response
    from aiohttp import web
    assert isinstance(result, web.Response)
