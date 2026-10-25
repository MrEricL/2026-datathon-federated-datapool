![Three tools for better access to social-service data, by Eric Li, DSSG Berlin × NYC AI for Good Datathon 2026. Tool 1 returns opening hours and accessibility that the original tool left out. Tool 2 links a debt-counselling service to the office that runs it. Tool 3 finds 12 debt-counselling facilities, 6 more than tool 2.](contributions/directory-search/figures/00-three-tools.png)

**Eric Li** · Federated Data Pool contribution for the **DSSG Berlin × NYC AI for Good Datathon 2026**

I made social-service data easier for AI to use: connecting services to providers and surfacing details like opening hours and accessibility. Built on the [Federated Data Pool challenge](https://github.com/dssg-berlin/2026-datathon-federated-datapool)'s AWO MCP server, the tools handle more of the linking and filtering—so the AI has less detective work to do.

<sub>Thanks to Andreas for perspective on German users, Louis for reviewing some test questions, and Mrunal, also working on benchmarks, for talking through ideas with me.</sub>

**[Browse the code](contributions/directory-search/src/) · [Run it locally](contributions/directory-search/README.md) · [Read the evaluation](contributions/directory-search/docs/RESULTS.md)**

[Project Presentation](https://drive.google.com/file/d/1DpY78XSs_EPjHW4htEHuNRojDmREAMVO/view?usp=sharing)

## The three tools

### Tool 1 · Record card: `get_entity_card`

Returns every stored field of one record by its exact ID, including contact details, opening hours, accessibility and linked records. Each field names the CSV row it came from, and missing values are marked as missing.

**Example:** "What hours does Frauenladen list, and is it accessible?" The original `get_facility_details` returns the address, phone and email, but not the opening hours or accessibility. `get_entity_card` returns both for **Frauenladen – Drogennotdienst Berlin gGmbH**: drop-in hours on **Monday 11–14, Wednesday 15–18 and Thursday 12–15**, and *„Die Einrichtung ist nicht barrierefrei erreichbar.“* (The facility is not barrier-free.) Looking it up by ID also keeps it apart from a separate AWO facility called "Frauenladen".

### Tool 2 · Service search: `search_service_candidates`

Searches service names, categories and audiences, and returns each service with the facility or provider that runs it and that office's locality. Results come in pages.

**Example:** "Find debt-counselling services." `search_service_candidates(query="Schuldner")` returns 6 services, each with its office. The original `search_services` returns the same 6 services with no office attached. One is **Schuldnerberatung**, run by **Deutscher FamilienVerband e.V. – Schuldner- und Insolvenzberatung** in **Berlin-Tiergarten**.

### Tool 3 · Directory search: `search_directory`

Searches facility names, linked services and addresses in one call. It can filter by the organization that runs a facility, or to facilities with a phone number on record. Totals and missing-field counts cover all matches, including those past the current page.

**Example:** `search_directory(query="Schuldner")` finds **12 facilities**: the 6 that tool 2 reaches through service entries, and 6 more that match by facility name only. Adding `has_telephone=True` leaves one: **Schuldner- und Insolvenzberatung, Ritterstraße 3, Berlin-Kreuzberg**.

A typical sequence is to find services with tool 2, then open one with tool 1. Tool 3 is for questions that combine conditions or need a count.

## Results

Two models answered the same 8 new questions with each tool set, 48 answers in all. The table counts complete answers. Single run, small n.

| Model | Original 8 tools | + tools 1–2 | + tools 1–3 |
| --- | ---: | ---: | ---: |
| GPT-6 Luna (cheap), low effort | 4/8 | 6/8 | 7/8 |
| GPT-6.1 (strong), high effort | 3/8\* | 7/8 | 8/8 |

Neither model lost a complete answer when tool 3 was added.

\* One answer lost credit only for adding Berlin's leading 0 to a stored phone number (3025293540 → 030 25293540). Counting it, GPT-6.1 had 4 of 8.

[Results and charts](contributions/directory-search/docs/RESULTS.md) · [The 8 questions](contributions/directory-search/docs/transfer-prompts.jsonl) · [Paired outcomes](contributions/directory-search/docs/paired-outcomes.csv)

## What is included

| Item | Where to find it |
| --- | --- |
| Three Python modules for search, record cards and MCP registration | [Source code](contributions/directory-search/src/) |
| 24 regression tests on synthetic data | [Tests](contributions/directory-search/tests/) |
| Patch for the pinned AWO reference server | [Integration patch](contributions/directory-search/contribution-v3.patch) |
| MCP check over stdio, with no model calls or API key | [Smoke check](contributions/directory-search/scripts/smoke.py) |
| Setup steps and tested dependency versions | [Run it locally](contributions/directory-search/README.md) |
| Prompts, aggregate results, paired outcomes and charts | [Evaluation evidence](contributions/directory-search/docs/RESULTS.md) |

All 24 tests pass, the patch applies to a clean checkout of the reference server, and the smoke check passes with 11 tools.

The patch targets [Atrash87/awo-mcp-production at `d3842d2`](https://github.com/Atrash87/awo-mcp-production/tree/d3842d2974bf86f1ea906436e996e67d9a043a8e), whose Berlin sample has four CSV tables and 168 facilities. The CSVs come with that repository and aren't bundled here.

## Project context

The [Civic Data Lab's Federated Data Pool](https://civic-data.de/machen/werkstattboxen/foederierter-datenpool/) harmonizes social-service data from several welfare organizations. This contribution looks at how an AI model retrieves and uses a small snapshot of that data.

## Notes and limits

- **Grading:** an AI reviewer graded each answer, with one run per question. Some of the 8 questions overlap with material used during development.
- **GPT-6.1's 8/8** depends on one judgment call. A stricter reading of "complete" would make it 7/8.
- **Examples** show what the tools return from the pinned sample. They weren't checked against the services themselves.
- **Search** is literal text matching. It doesn't judge eligibility, distance or coverage.
- **Phone numbers** are returned as stored and aren't checked. Missing fields stay missing.
- **The sample has fewer phone numbers than the full federation:** 20% of the 168 sample facilities have one, compared with 75.5% of 37,341 facilities in a check of the live federation on 24 October 2026. [Exact counts](contributions/directory-search/docs/contact-coverage.csv) · [Count queries](contributions/directory-search/docs/federation-counts.sparql)
- **Not included:** the full evaluation runner, private traces, a hosted deployment, a federation-wide adapter and human review of answers.
- **Names in the evaluation files:** `codex-luna-low` is GPT-6 Luna and `codex-sol-high` is GPT-6.1. V2 ("improved") is + tools 1–2, and V3 ("improved-v3") is + tools 1–3.
