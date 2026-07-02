"""
ed-galaxy-mcp MCP Server — Elite Dangerous Galaxy Data Tools

Provides tools to query Elite Dangerous galaxy data:
  - Spansh: system/body/station data (public, no auth)
  - INARA: commander profiles, community goals (needs API key)
  - Frontier CAPI: personal profile, fleet carrier (needs OAuth2)

Run:  python -m ed_galaxy_mcp.server
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "ed-galaxy-mcp",
    instructions="""Elite Dangerous Galaxy data server. 
Use these tools to look up star systems, bodies, stations, markets, shipyards, 
and outfitting across the Elite Dangerous galaxy.

SPANSH tools (no key needed): get_system, get_body, get_station, 
  search_stations_nearby, search_systems, plot_neutron_route, plot_exobiology_route

INARA tools (needs INARA_API_KEY): get_commander_profile, get_community_goals

FRONTIER CAPI tools (needs Frontier OAuth2 token): get_my_profile, get_my_fleet_carrier
""",
)

# ---------------------------------------------------------------------------
# Config — read from environment
# ---------------------------------------------------------------------------

INARA_API_KEY = os.environ.get("INARA_API_KEY", "")
INARA_APP_NAME = os.environ.get("INARA_APP_NAME", "ed-galaxy-mcp")
INARA_APP_VERSION = os.environ.get("INARA_APP_VERSION", "1.0.0")
FRONTIER_TOKEN = os.environ.get("FRONTIER_TOKEN", "")
FRONTIER_EMAIL = os.environ.get("FRONTIER_EMAIL", "")

SPANSH_BASE = "https://spansh.co.uk/api"
INARA_BASE = "https://inara.cz/inapi/v1/"
FRONTIER_BASE = "https://companion.orerve.net"

# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=httpx.Timeout(30.0))
    return _client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_id64(name: str) -> int | None:
    """Resolve a system name to its ID64 using EDSM."""
    try:
        resp = _get_client().get(
            "https://www.edsm.net/api-v1/system",
            params={"systemName": name, "showId": 1},
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(10.0),
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("id64")
    except Exception:
        pass
    return None


def _resolve_system(name_or_id64: str) -> dict[str, Any] | None:
    """Fetch full system data: try as ID64 first, then resolve name via EDSM."""
    # Try as ID64 first
    try:
        id64 = int(name_or_id64)
        return _spansh_dump(id64)
    except ValueError:
        pass

    # Resolve name → id64 via EDSM
    id64 = _resolve_id64(name_or_id64)
    if id64:
        return _spansh_dump(id64)
    return None


def _spansh_dump(id64: int) -> dict[str, Any] | None:
    """Fetch full system dump from Spansh."""
    try:
        resp = _get_client().get(
            f"{SPANSH_BASE}/dump/{id64}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _resolve_body(name_or_id64: str) -> dict[str, Any] | None:
    """Resolve body data from Spansh."""
    try:
        id64 = int(name_or_id64)
        resp = _get_client().get(
            f"{SPANSH_BASE}/body/{id64}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _resolve_station(market_id_or_name: str) -> dict[str, Any] | None:
    """Resolve station data from Spansh."""
    try:
        mid = int(market_id_or_name)
        resp = _get_client().get(
            f"{SPANSH_BASE}/station/{mid}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


# ==========================================================================
# SPANSH TOOLS
# ==========================================================================


@mcp.tool()
def get_system(name_or_id64: str) -> str:
    """Fetch all data about a star system: bodies, stations, BGS, factions, Thargoid war state.

    Args:
        name_or_id64: System name (e.g. 'Sol', 'Diaguandri') or numeric ID64.
    Returns:
        JSON with system data including:
        - coords (x, y, z)
        - bodies (type, subType, atmosphere, gravity, materials, signals, isLandable)
        - stations (name, type, services, market, shipyard, outfitting)
        - controllingFaction, factions (allegiance, influence, states)
        - thargoidWar state
        - powers, powerState
    """
    data = _resolve_system(name_or_id64)
    if data:
        return json.dumps(data, indent=2, default=str)
    return json.dumps({"error": f"System '{name_or_id64}' not found"}, indent=2)


@mcp.tool()
def get_body(name_or_id64: str) -> str:
    """Fetch detailed data about a planet/star/body.

    Args:
        name_or_id64: Body name (e.g. 'Sol 1') or numeric ID64.
    Returns:
        JSON with body data: type, subType, distanceToArrival, gravity, 
        surfaceTemperature, atmosphereType, isLandable, materials, signals, 
        rings, volcanismType, terraformingState, etc.
    """
    try:
        id64 = int(name_or_id64)
        data = _resolve_body(str(id64))
    except ValueError:
        data = _resolve_body(name_or_id64)
    
    if data:
        return json.dumps(data, indent=2, default=str)
    return json.dumps({"error": f"Body '{name_or_id64}' not found"}, indent=2)


@mcp.tool()
def get_station(market_id: str) -> str:
    """Fetch station data: services, market prices, shipyard, outfitting.

    Args:
        market_id: The station's Market ID (numeric) — e.g. '128666762'.
            Find this via get_system() first, look in system.stations[].id
    Returns:
        JSON with station data: services, type, controllingFaction, 
        market (commodities, prices, stock/demand), shipyard (ships for sale), 
        outfitting (available modules).
    """
    data = _resolve_station(market_id)
    if data:
        return json.dumps(data, indent=2, default=str)
    return json.dumps({"error": f"Station with market ID '{market_id}' not found"}, indent=2)


@mcp.tool()
def search_stations_nearby(
    system_name: str,
    item_name: str | None = None,
    ship_name: str | None = None,
    station_type: str | None = None,
    max_distance_ly: float = 50.0,
) -> str:
    """Find stations near a system that have a specific module, ship, or commodity.
    
    Uses the system's data to find nearby stations. For broader searches
    across many systems, you'll need INARA or EDSM.

    Args:
        system_name: Reference system name.
        item_name: Module or commodity name to search for (e.g. 'SCO', 'Caustic Sink').
        ship_name: Ship name to find for sale.
        station_type: Filter by type (e.g. 'Orbis', 'Coriolis', 'Planetary', 'fleetcarrier').
        max_distance_ly: Max LY range to search (default 50).
    Returns:
        JSON with matching stations.
    """
    data = _resolve_system(system_name)
    if not data:
        return json.dumps({"error": f"System '{system_name}' not found"}, indent=2)
    
    system_data = data.get("system", data)
    stations = system_data.get("stations", [])
    
    if not stations:
        return json.dumps({"error": f"No stations found in system '{system_name}'"}, indent=2)
    
    results = []
    for station in stations:
        # Filter by station type
        if station_type and station.get("type", "").lower() != station_type.lower():
            continue
        
        match = {"station": station.get("name"), "type": station.get("type"),
                 "distance": station.get("distanceToArrival"),
                 "services": station.get("services", [])}
        
        # Check shipyard
        if ship_name:
            shipyard = station.get("shipyard", {})
            ships = shipyard.get("ships", [])
            matches = [s for s in ships if ship_name.lower() in s.get("name", "").lower()]
            if matches:
                match["ships_found"] = [s.get("name") for s in matches]
            else:
                continue
        
        # Check outfitting
        if item_name:
            outfitting = station.get("outfitting", {})
            modules = outfitting.get("modules", [])
            matches = [m for m in modules if item_name.lower() in m.get("name", "").lower()]
            if matches:
                match["modules_found"] = [m.get("name") for m in matches]
            else:
                continue
        
        # Check market
        if item_name and not ship_name:
            market = station.get("market", {})
            commodities = market.get("commodities", [])
            matches = [c for c in commodities if item_name.lower() in c.get("name", "").lower()]
            if matches:
                match["market_found"] = [c.get("name") for c in matches]
        
        results.append(match)
    
    return json.dumps({
        "system": system_name,
        "stations_total": len(stations),
        "results": results,
    }, indent=2, default=str)


@mcp.tool()
def search_systems(query: str) -> str:
    """Search for star systems by name.

    Args:
        query: Partial system name to search (e.g. 'Diagu', 'Sol', 'HIP 1').
    Returns:
        JSON with matching system names.
    """
    try:
        resp = _get_client().get(
            f"{SPANSH_BASE}/systems",
            params={"q": query},
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            systems = resp.json()
            if isinstance(systems, list) and systems:
                return json.dumps({
                    "query": query,
                    "count": len(systems),
                    "systems": systems[:20],
                }, indent=2, default=str)
            return json.dumps({"query": query, "count": 0, "systems": []}, indent=2)
        return json.dumps({"error": f"Search failed: HTTP {resp.status_code}"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ==========================================================================
# ROUTE PLANNING
# ==========================================================================


@mcp.tool()
def plot_neutron_route(
    from_system: str,
    to_system: str,
    jump_range: float = 50.0,
    efficiency: float = 1.0,
) -> str:
    """Plot a neutron-boosted route between two systems using Spansh.
    
    Spansh's neutron plotter POST endpoint accepts:
      - source system name or coords
      - destination system name or coords
      - jump range
      - efficiency (use neutron stars, white dwarfs, or both)

    Args:
        from_system: Starting system name.
        to_system: Destination system name.
        jump_range: Maximum jump range in LY (default 50.0).
        efficiency: Neutron efficiency (1.0 = use all, 0.0 = none).
    Returns:
        JSON with route: total jumps, total distance, waypoints.
    """
    try:
        payload = {
            "source": from_system,
            "destination": to_system,
            "range": jump_range,
            "efficiency": efficiency,
        }
        resp = _get_client().post(
            f"{SPANSH_BASE}/route",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(60.0),
        )
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2, default=str)
        return json.dumps({
            "error": f"Route request failed: HTTP {resp.status_code}",
            "body": resp.text[:500],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def plot_exobiology_route(
    from_system: str,
    range_ly: float = 500.0,
    min_bio_signals: int = 3,
    max_systems: int = 20,
) -> str:
    """Plan an exobiology route from a starting system.
    
    Uses Spansh's exobiology route planner to find high-value
    biology planets within range.
    
    Args:
        from_system: Starting system name.
        range_ly: Maximum travel distance in LY (default 500).
        min_bio_signals: Minimum number of biological signals (default 3).
        max_systems: Maximum systems in the route (default 20).
    Returns:
        JSON with route: systems, bodies with bio signals, estimated value.
    """
    try:
        payload = {
            "source": from_system,
            "range": range_ly,
            "min_bio": min_bio_signals,
            "max_systems": max_systems,
        }
        resp = _get_client().post(
            f"{SPANSH_BASE}/exobiology",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(60.0),
        )
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2, default=str)
        return json.dumps({
            "error": f"Exobiology route request failed: HTTP {resp.status_code}",
            "body": resp.text[:500],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ==========================================================================
# INARA TOOLS (needs API key)
# ==========================================================================


def _inara_request(events: list[dict]) -> dict | None:
    """Send a batch request to INARA API."""
    if not INARA_API_KEY:
        return None

    payload = {
        "header": {
            "appName": INARA_APP_NAME,
            "appVersion": INARA_APP_VERSION,
            "isBeingDeveloped": True,
            "APIkey": INARA_API_KEY,
        },
        "events": events,
    }
    try:
        resp = _get_client().post(
            INARA_BASE,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


@mcp.tool()
def get_commander_profile(cmdr_name: str) -> str:
    """Look up a commander's public profile on INARA.

    Requires INARA_API_KEY environment variable.

    Args:
        cmdr_name: Commander's in-game name.
    Returns:
        JSON with: ranks (combat, trade, exploration, CQC, empire, federation),
        squadron membership, main ship, preferred power, avatar URL.
    """
    result = _inara_request([
        {
            "eventName": "getCommanderProfile",
            "eventTimestamp": None,
            "eventData": {"searchName": cmdr_name},
        }
    ])
    if result is None:
        return json.dumps(
            {"error": "INARA API not configured. Set INARA_API_KEY environment variable."},
            indent=2,
        )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_community_goals() -> str:
    """Get recent community goals from INARA.

    Requires INARA_API_KEY environment variable.

    Returns:
        JSON with active/recent community goals: name, system, station,
        expiry, tier reached, contributors, total contributions.
    """
    result = _inara_request([
        {
            "eventName": "getCommunityGoalsRecent",
            "eventTimestamp": None,
            "eventData": {},
        }
    ])
    if result is None:
        return json.dumps(
            {"error": "INARA API not configured. Set INARA_API_KEY environment variable."},
            indent=2,
        )
    return json.dumps(result, indent=2, default=str)


# ==========================================================================
# FRONTIER CAPI TOOLS (needs OAuth2 token)
# ==========================================================================


def _frontier_request(path: str) -> str | None:
    """Make an authenticated request to Frontier CAPI."""
    if not FRONTIER_TOKEN:
        return None
    try:
        resp = _get_client().get(
            f"{FRONTIER_BASE}{path}",
            headers={
                "Authorization": f"Bearer {FRONTIER_TOKEN}",
                "Accept": "application/json",
            },
        )
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


@mcp.tool()
def get_my_profile() -> str:
    """Get your own commander profile from Frontier's Companion API.

    Requires FRONTIER_TOKEN environment variable (OAuth2 token).

    Returns:
        JSON with: current location (system, station), ship (name, modules,
        cargo, engineering), credits, ranks, all owned ships.
    """
    data = _frontier_request("/profile")
    if data is None:
        return json.dumps(
            {
                "error": "Frontier CAPI not configured. "
                "Set FRONTIER_TOKEN and optionally FRONTIER_EMAIL."
            },
            indent=2,
        )
    try:
        return json.dumps(json.loads(data), indent=2, default=str)
    except Exception:
        return data


@mcp.tool()
def get_my_fleet_carrier() -> str:
    """Get fleet carrier data from Frontier's Companion API.

    Requires FRONTIER_TOKEN environment variable.

    Returns:
        JSON with: carrier name, location, fuel, balance, capacity,
        itinerary, market orders, cargo, crew.
        Returns 204/empty if you don't own a fleet carrier.
    """
    data = _frontier_request("/fleetcarrier")
    if data is None:
        return json.dumps(
            {
                "error": "Frontier CAPI not configured. "
                "Set FRONTIER_TOKEN and optionally FRONTIER_EMAIL."
            },
            indent=2,
        )
    try:
        return json.dumps(json.loads(data), indent=2, default=str)
    except Exception:
        return data


# ==========================================================================
# ENTRYPOINT
# ==========================================================================

def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
