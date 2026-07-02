"""Full-surface probe of Epic's official Unreal MCP server (UE 5.8+).

Usage: python scripts/probe_epic_mcp.py <out.json> [server_url]

Requires a running editor with the ModelContextProtocol plugin serving
(console: `ModelContextProtocol.StartServer`); enable the AllToolsets plugin
to expose the full shipped surface. list_toolsets returns lines of
`- <ToolsetName>: <description>`; describe_toolset takes {toolset_name} and
returns that toolset's complete JSON schema. The dump is the authoritative
input for docs/EPIC_MCP_MATRIX.md — rerun per engine version and diff.
"""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/mcp"


def content_text(res) -> str:
    return "\n".join(c.text for c in (getattr(res, "content", []) or []) if getattr(c, "text", None))


async def main(out_path: str) -> None:
    out: dict = {"url": URL}
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            out["protocol_version"] = init.protocolVersion
            tools = await session.list_tools()
            out["tools_list"] = [t.model_dump() for t in tools.tools]

            ts = await session.call_tool("list_toolsets", {})
            raw = content_text(ts)
            out["list_toolsets_raw"] = raw

            names = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("- ") and ":" in line:
                    names.append(line[2:].split(":", 1)[0].strip())
            out["toolset_names"] = names
            print(f"{len(names)} toolsets discovered")

            out["toolsets"] = {}
            tool_total = 0
            for name in names:
                try:
                    d = await session.call_tool("describe_toolset", {"toolset_name": name})
                    text = content_text(d)
                    if getattr(d, "isError", False):
                        out["toolsets"][name] = {"error": text}
                        continue
                    try:
                        schema = json.loads(text)
                        out["toolsets"][name] = schema
                        n = len(schema.get("tools", []))
                        tool_total += n
                        print(f"  {name}: {n} tools")
                    except (json.JSONDecodeError, ValueError):
                        out["toolsets"][name] = {"raw": text}
                        print(f"  {name}: (non-JSON payload, {len(text)} chars)")
                except Exception as e:
                    out["toolsets"][name] = {"exception": str(e)}
                    print(f"  {name}: EXCEPTION {e}")

            out["tool_total"] = tool_total
            print("TOTAL concrete tools:", tool_total)

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "probe_out_full.json"))
