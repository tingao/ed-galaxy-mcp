# ed-galaxy-mcp — Elite Dangerous Galaxy MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that provides Elite Dangerous galaxy data as tools for AI agents.

Built for use with **Hermes Agent**, Claude Desktop, or any MCP-compatible client.

## Tools

### Spansh (no API key needed)

| Tool | Description |
|------|-------------|
| `get_system` | Full system data: bodies, stations, BGS, factions, Thargoid war state |
| `get_body` | Body details: atmosphere, gravity, signals, materials, rings, isLandable |
| `get_station` | Station: services, market prices, shipyard, outfitting |
| `search_systems` | Name autocomplete search |
| `search_stations_nearby` | Find stations with specific modules/ships near a system |
| `plot_neutron_route` | Neutron-boosted route between two systems |
| `plot_exobiology_route` | Exobiology route planner |

### INARA (needs `INARA_API_KEY` env)

| Tool | Description |
|------|-------------|
| `get_commander_profile` | Look up a CMDR on Inara — ranks, squadron, ships |
| `get_community_goals` | Recent Community Goals |

### Frontier CAPI (needs `FRONTIER_TOKEN` env)

| Tool | Description |
|------|-------------|
| `get_my_profile` | Your CMDR: location, ship, modules, cargo, credits |
| `get_my_fleet_carrier` | Your fleet carrier: location, fuel, balance, market |

## Quick Start

```bash
# Clone
git clone https://github.com/tingao/ed-galaxy-mcp
cd ed-galaxy-mcp

# Install
uv sync

# Run (stdio transport)
uv run ed-galaxy-mcp
```

## Configuration

No API keys are needed for basic Spansh tools. Optional integrations:

| Variable | Required for | Where to get it |
|----------|-------------|-----------------|
| `INARA_API_KEY` | INARA tools | https://inara.cz/settings-api/ |
| `FRONTIER_TOKEN` | Frontier CAPI tools | Frontier OAuth2 — see https://user.frontierstore.net/ |

## Architecture

```
Name → id64:  EDSM api-v1/system?systemName=X&showId=1
Full system:  Spansh /dump/{id64}
Body:         Spansh /body/{id64}
Station:      Spansh /station/{marketId}
Routes:       Spansh POST endpoints
INARA:        Batch JSON POST to /inapi/v1/
Frontier CAPI: OAuth2 → companion.orerve.net
```

## License

MIT
