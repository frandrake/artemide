"""Single FastMCP instance shared by all tool modules.

Kept separate from server.py so that `tools/*.py` can register against
`mcp` without creating a circular import.
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP(name="artemide")
