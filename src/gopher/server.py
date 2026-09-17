"""Gopher: a single MCP server that fetches, caches, and digests context."""

import logging
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP

from gopher.cache import tools as cache_tools
from gopher.digest import tools as digest_tools
from gopher.fetch import tools as fetch_tools

load_dotenv()

mcp = FastMCP("Gopher")

fetch_tools.register(mcp)
cache_tools.register(mcp)
digest_tools.register(mcp)

_HANDLER_NAME = "gopher-stderr"


def configure_logging() -> logging.Logger:
    """Send gopher's own log lines to stderr, and only there.

    On a stdio MCP server stdout is the protocol channel, so one stray line
    written to it corrupts the session. MCP clients generally surface a
    server's stderr in their logs, which is where these belong.

    Safe to call more than once. Done in main() rather than at import, so
    importing gopher as a library or under test prints nothing.
    """
    logger = logging.getLogger("gopher")
    if not any(h.get_name() == _HANDLER_NAME for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(logging.Formatter("gopher: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Without this the same line can print twice if the client or FastMCP
    # has configured the root logger too.
    logger.propagate = False
    return logger


def main() -> None:
    configure_logging()
    mcp.run()


if __name__ == "__main__":
    main()
