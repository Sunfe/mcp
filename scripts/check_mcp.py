"""Check a real MCP stdio connection, its tool catalog, and a knowledge search."""

import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def tool_payload(result) -> dict:
    text = "\n".join(item.text for item in result.content if item.type == "text")
    if result.isError:
        raise RuntimeError(text)
    return json.loads(text)


async def check(command: list[str], query: str):
    parameters = StdioServerParameters(command=command[0], args=command[1:], env=os.environ.copy())
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=40)) as session:
            initialized = await session.initialize()
            print(f"[OK] MCP initialized: {initialized.serverInfo.name}", flush=True)
            tools = (await session.list_tools()).tools
            required = {"list_documents", "search_documents", "get_document"}
            if not required.issubset({tool.name for tool in tools}):
                raise RuntimeError("MCP is missing required document tools")
            print("[OK] Tools: " + ", ".join(tool.name for tool in tools), flush=True)
            documents = tool_payload(await session.call_tool("list_documents", {}))["items"]
            print(f"[OK] Indexed documents: {len(documents)}", flush=True)
            results = tool_payload(await session.call_tool("search_documents", {"query": query, "limit": 5}))["items"]
            print(f"[OK] Search {query!r}: {len(results)} result(s)", flush=True)
            for item in results:
                print(f"  {item['title']} document_id={item['document_id']} chunk_id={item['chunk_id']}", flush=True)
            if not results:
                print("[NOTE] Connection works, but this query has no indexed matches.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="P5-35", help="Keyword to search after initialization")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Optional command after --, e.g. ssh -T knowledge-server bash /path/scripts/mcp_stdio.sh")
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        command = ["bash", str(Path(__file__).resolve().parent / "mcp_stdio.sh")]
    try:
        anyio.run(check, command, args.query)
    except Exception as error:
        # Keep nested MCP transport failures visible, including API connection errors.
        def messages(exception):
            children = getattr(exception, "exceptions", ())
            if children:
                return "; ".join(messages(child) for child in children)
            return str(exception)
        print(f"[ERROR] {messages(error)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
