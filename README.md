# Federated Data Pool — MCP Server for German Welfare Data

**DSSG Berlin Datathon 2026**  
23–25 October 2026 · Remote · in collaboration with DSSG NYC

This repository is the working space for the **Federated Data Pool** challenge of the 8th DSSG Berlin Datathon.

## Linked directory search contribution

[Linked directory search for the AWO MCP server](contributions/directory-search/README.md) adds three tools for linked search, attributable entity cards and facility-level filtering with full-match totals. It includes portable source, 24 synthetic regression tests, a patch for the pinned AWO reference server, a real MCP smoke check, and evaluation charts with their limitations.

Start with the contribution README to run the tests or try the patched reference locally.

## Project Overview

The [Federated Data Pool](https://civic-data.de/machen/werkstattboxen/foederierter-datenpool/) (Föderierter Datenpool) is a collaborative initiative by **Caritas**, **AWO**, and other German welfare organizations. Its goal is to harmonize and make social-service data findable and usable across Germany — without building yet another central directory that needs constant manual maintenance.

Data about support services stays with the original providers. It is deterministically harmonized into a shared, openly usable data layer so that people in need (and the systems that help them) can discover relevant offers more reliably.

### Datathon Goal

Build a **hosted Model Context Protocol (MCP) server** that lets agentic AI systems interact with these complex semantic data structures in a standardized way.

During the Datathon, volunteers work in specialized sub-teams to:

- Design and implement the MCP server architecture
- Develop custom **tools**, **resources**, and **prompts**
- Create interactive UI showcases / demos
- Explore how AI agents can query and reason over federated welfare data

## What is the Model Context Protocol (MCP)?

[MCP](https://modelcontextprotocol.io/) is an open standard (originally introduced by Anthropic, now under the Linux Foundation’s Agentic AI Foundation) that standardizes how AI applications connect to external tools and data sources.

Think of it as a universal connector: an MCP server exposes:

| Primitive   | Description                                      |
|-------------|--------------------------------------------------|
| **Tools**   | Actions the AI can invoke (search, filter, …)   |
| **Resources** | Data the AI can read (datasets, schemas, …)   |
| **Prompts** | Reusable prompt templates / workflows           |

This makes it possible for AI agents (Claude, ChatGPT, custom agents, etc.) to work with the Federated Data Pool without custom one-off integrations.

## Partners & Context

- **Data partners**: Caritas, AWO (Arbeiterwohlfahrt), Deutsche Hauptstelle für Suchtfragen, Sozialplattform, and others
- **Infrastructure concept**: Civic Data Lab – [Föderierter Datenpool](https://civic-data.de/machen/werkstattboxen/foederierter-datenpool/)
- **Related open repositories**:
  - [foederierter-datenpool/sosuse-directory-builder](https://github.com/foederierter-datenpool/sosuse-directory-builder)
  - [foederierter-datenpool organization](https://github.com/foederierter-datenpool)

## Repository Structure (to be filled during the Datathon)

```
.
├── README.md                 # This file
├── docs/                     # Architecture notes, decisions, prompts
├── mcp-server/               # MCP server implementation
│   ├── tools/                # Custom tools
│   ├── resources/            # Data resources
│   └── prompts/              # Prompt templates
├── ui/                       # Interactive demos / showcases
├── data/                     # Sample or derived datasets (if any)
└── notebooks/                # Exploration notebooks
```

> Exact layout will evolve as sub-teams start working. Feel free to propose improvements via PRs.

## Getting Started

1. **Join the Datathon communication channels** (Slack / Google Meet – links shared with participants).
2. **Clone this repository**:
   ```bash
   git clone https://github.com/dssg-berlin/2026-datathon-federated-datapool.git
   cd 2026-datathon-federated-datapool
   ```
3. Check the issue tracker and any `#start-here` or `#subteam-*` issues for your assigned track.
4. Follow the setup instructions that will be added by the project leads / mentors (Python environment, MCP SDK, etc.).

## Suggested Sub-Teams

During the Datathon we expect to form focused groups around:

- **MCP Core** – server scaffolding, protocol compliance, hosting
- **Tools & Resources** – search, filtering, schema exploration, data access
- **Prompts & Agent Workflows** – useful prompt patterns for social-service discovery
- **UI / Demo** – interactive showcase that lets people try the MCP server
- **Data & Schema** – understanding and documenting the federated data model

## Contribution Guidelines

- Work in feature branches and open pull requests.
- Prefer small, reviewable PRs with a clear description.
- Document decisions in `docs/` (Architecture Decision Records welcome).
- Respect data privacy and the sensitive nature of social-service information — do not commit real personal data.
- Follow the [Berlin Code of Conduct](https://berlincodeofconduct.org/).

## Useful Links

| Resource | Link |
|----------|------|
| Datathon Event Page | [Eventbrite](https://www.eventbrite.de/e/virtual-ai-for-good-datathon-hosted-by-dssg-berlin-dssg-nyc-tickets-1993605979150) |
| DSSG Berlin | [https://dssg-berlin.github.io/](https://dssg-berlin.github.io/) |
| Federated Data Pool (Civic Data Lab) | [Project page](https://civic-data.de/machen/werkstattboxen/foederierter-datenpool/) |
| MCP Specification | [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| MCP GitHub | [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) |
| sosuse-directory-builder | [GitHub](https://github.com/foederierter-datenpool/sosuse-directory-builder) |

## Contact

- **DSSG Berlin**: dssgber@gmail.com
- **DSSG NYC**: dssgnyc@gmail.com

---

*Built with ❤️ for social good during the DSSG Berlin × DSSG NYC Datathon 2026.*
