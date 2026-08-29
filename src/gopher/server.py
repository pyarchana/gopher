"""Gopher: a single MCP server that fetches, caches, and digests context."""

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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
