"""Profile-local stdio transport for the Artemide MCP toolset.

Hermes Agent launches this module as a long-lived subprocess.  It initializes
(or migrates) the database selected by ``ARTEMIDE_DB_PATH`` and then exposes the
same service-backed tools as the HTTP deployment, without a network listener or
bearer token.
"""
from __future__ import annotations

from ..db import init_db
from .server import mcp


def main() -> None:
    init_db()
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
