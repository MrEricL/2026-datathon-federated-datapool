"""Check the patched, pinned AWO server through a real stdio MCP connection."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "count_facilities", "search_facilities", "get_facility_details",
    "search_services", "generate_statistics", "check_completeness",
    "detect_duplicates", "compare_facilities", "search_service_candidates",
    "get_entity_card", "search_directory",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def call(session, name: str, arguments: dict):
    result = await asyncio.wait_for(session.call_tool(name, arguments), 20)
    require(not result.isError, f"MCP tool failed: {name}")
    value = result.structuredContent
    if value is None:
        value = "\n".join(block.text for block in result.content if block.type == "text")
    if isinstance(value, dict) and set(value) == {"result"}:
        value = value["result"]
    return json.loads(value) if isinstance(value, str) else value


async def run(reference: Path) -> dict:
    reference = reference.resolve()
    require((reference / "server.py").is_file(), "Reference server.py is missing; follow the README setup.")
    params = StdioServerParameters(
        command=sys.executable, args=[str(reference / "server.py")], cwd=str(reference),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            require(names == EXPECTED_TOOLS, f"Expected 11 tools; observed {sorted(names)}")
            await call(session, "search_services", {"query": "Schuldner"})
            candidates = await call(session, "search_service_candidates", {"query": "Geschäftsstellen"})
            require(candidates["total"] == 3, "Pinned sample must contain three matching office services.")
            await call(session, "get_entity_card", {"iri": candidates["candidates"][0]["service_id"]})
            debt = await call(session, "search_directory", {"query": "Schuldner"})
            require(debt["total"] == debt["summary_denominator"] == 12, "Expected 12 debt-query facility matches.")
            all_facilities = await call(session, "search_directory", {})
            require(all_facilities["total"] == 168, "Expected 168 facilities in the pinned sample.")
            missing = {key: all_facilities["missing_counts"][key] for key in ("telephone", "email", "openingHours")}
            require(missing == {"telephone": 134, "email": 134, "openingHours": 139}, "Unexpected missing-field counts.")
            first = await call(session, "search_directory", {"has_telephone": True, "limit": 25})
            require(first["total"] == 34 and first["next_offset"] == 25, "Unexpected first phone page.")
            second = await call(session, "search_directory", {"has_telephone": True, "limit": 25, "offset": 25})
            require(second["returned"] == 9 and second["next_offset"] is None, "Unexpected second phone page.")
            require(first["phone_format_counts"] == second["phone_format_counts"], "Page summaries must cover all matches.")
            hits = first["hits"] + second["hits"]
            require(len({hit["iri"] for hit in hits}) == 34, "Phone pages must contain 34 distinct facilities.")
            require(all(isinstance(hit["telephone"], str) for hit in hits), "Raw telephone values must remain strings.")
    return {"status": "passed", "transport": "stdio", "tools": 11,
            "facilities": 168, "debt_query_matches": 12, "nonblank_phone_records": 34}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(asyncio.wait_for(run(args.reference), 90))))
