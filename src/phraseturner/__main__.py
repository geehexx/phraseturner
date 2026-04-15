"""Entry point for phraseturner MCP server.

Allows running via ``python -m phraseturner`` or the ``phraseturner``
console script defined in ``pyproject.toml``.

Implements NFR-DIST-02.
"""

from __future__ import annotations

from phraseturner.server import mcp


def main() -> None:
    """Start the phraseturner MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
