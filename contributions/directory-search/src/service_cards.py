"""Read-only, source-attributed access to the pinned reference CSV schema.

No network, fuzzy matching, geographic inference, contact repair, or entity merging.
Service matching intentionally uses the upstream three-field literal matcher.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import urlsplit


TABLES = {
    "service": "angebotSchema.csv",
    "facility": "einrichtungSchema.csv",
    "provider": "traegerSchema.csv",
    "address": "adresseSchema.csv",
}
MATCH_FIELDS = ("schema:name", "schema:category", "schema:audience")
FIELDS = {
    "service": {
        "name": "schema:name", "category": "schema:category",
        "code": "schema:codeValue", "audience": "schema:audience",
        "area_served": "schema:areaServed",
    },
    "facility": {
        "name": "schema:name", "alternate_name": "schema:alternateName",
        "telephone": "schema:telephone", "email": "schema:email",
        "homepage": "foaf:homepage", "source_page": "schema:mainEntityOfPage",
        "category": "schema:category", "service_description": "schema:availableService",
        "audience": "schema:audience", "accessibility": "schema:accessibilitySummary",
        "opening_hours": "schema:openingHours",
    },
    "provider": {"name": "schema:name", "homepage": "foaf:homepage"},
    "address": {
        "street": "schema:streetAddress", "postal_code": "schema:postalCode",
        "locality": "schema:addressLocality", "country": "schema:addressCountry",
        "latitude": "schema:latitude", "longitude": "schema:longitude",
    },
}
RELATIONSHIPS = {
    "service": {"provider": ("schema:provider", ("facility", "provider"))},
    "facility": {
        "parent_organization": ("schema:parentOrganization", ("provider",)),
        "address": ("schema:address", ("address",)),
    },
    "provider": {"address": ("schema:address", ("address",))},
    "address": {},
}


def present(value: str | None) -> str | None:
    """Keep nonblank values byte-for-byte; whitespace-only cells are unknown."""
    return value if value is not None and value.strip() else None


def telephone_quality(value: str | None) -> dict:
    if value is None:
        return {"status": "missing", "verified": False}
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", value.strip()):
        return {"status": "suspicious_scientific_notation", "verified": False,
                "note": "Source verification required; do not reconstruct this number."}
    if value.strip().isdigit():
        return {"status": "digit_only_prefix_unverified", "verified": False,
                "note": "Prefix and dialing format are unverified; no repair was applied."}
    return {"status": "unverified_format", "verified": False}


def url_quality(value: str | None) -> dict:
    """Classify syntax only. A syntactically absolute URL is not verified live."""
    if value is None:
        return {"status": "missing", "verified": False}
    if any(character.isspace() for character in value):
        return {"status": "malformed", "verified": False}
    try:
        parsed = urlsplit(value)
        if not parsed.scheme:
            status = "relative_unresolved" if value.startswith(("/", "#", "?")) else "missing_scheme"
        elif parsed.scheme not in ("http", "https"):
            status = "unsupported_scheme"
        elif not parsed.hostname or parsed.username is not None or parsed.password is not None:
            status = "malformed"
        else:
            status = "absolute_http_unverified"
    except ValueError:
        status = "malformed"
    return {"status": status, "verified": False}


class Directory:
    """One immutable in-memory view of four CSVs; duplicate IDs never pick a winner."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.rows: dict[str, list[dict[str, str]]] = {}
        self.index: dict[str, list[tuple[str, dict[str, str]]]] = {}
        for kind, filename in TABLES.items():
            with (self.data_dir / filename).open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                required = {"iri", *FIELDS[kind].values()}
                required.update(column for column, _ in RELATIONSHIPS[kind].values())
                missing = required - set(reader.fieldnames or ())
                if missing:
                    raise ValueError(f"{filename}: missing columns {sorted(missing)}")
                rows = list(reader)
            if any(None in row or any(value is None for value in row.values()) for row in rows):
                raise ValueError(f"{filename}: row width differs from header")
            self.rows[kind] = rows
            for row in rows:
                iri = present(row["iri"])
                if iri is None:
                    raise ValueError(f"{filename}: blank entity IRI")
                self.index.setdefault(iri, []).append((kind, row))

    @staticmethod
    def _evidence(kind: str, row: dict, column: str) -> dict:
        return {"table": TABLES[kind], "entity_id": row["iri"], "field": column}

    def _resolve(self, iri: str | None, expected: tuple[str, ...]) -> tuple[str, str | None, dict | None]:
        if iri is None:
            return "missing", None, None
        matches = self.index.get(iri, [])
        if not matches:
            return "dangling", None, None
        if len(matches) != 1:
            return "ambiguous", None, None
        kind, row = matches[0]
        if kind not in expected:
            return "type_mismatch", kind, None
        return "resolved", kind, row

    def _relation(self, kind: str, row: dict, column: str, expected: tuple[str, ...], seen: frozenset) -> dict:
        target_id = present(row[column])
        status, target_type, target_row = self._resolve(target_id, expected)
        relation = {
            "status": status, "target_id": target_id, "target_type": target_type,
            "evidence": self._evidence(kind, row, column), "entity": None,
        }
        if status == "resolved":
            if target_id in seen:
                relation["status"] = "cycle"
            else:
                relation["entity"] = self._card(target_type, target_row, seen)
        return relation

    def _card(self, kind: str, row: dict, seen: frozenset = frozenset()) -> dict:
        seen = seen | {row["iri"]}
        fields = {name: present(row[column]) for name, column in FIELDS[kind].items()}
        quality = {}
        if "telephone" in fields:
            quality["telephone"] = telephone_quality(fields["telephone"])
        for name in ("homepage", "source_page"):
            if name in fields:
                quality[name] = url_quality(fields[name])
        return {
            "status": "ok", "entity_type": kind, "id": row["iri"],
            "fields": fields,
            "field_evidence": {name: self._evidence(kind, row, column)
                               for name, column in FIELDS[kind].items()},
            "quality": quality,
            "missing_fields": [name for name, value in fields.items() if value is None],
            "verification": "source_record_only",
            "contact_scope": f"{kind}_record" if kind in ("facility", "provider") else None,
            "relationships": {
                name: self._relation(kind, row, column, expected, seen)
                for name, (column, expected) in RELATIONSHIPS[kind].items()
            },
        }

    def get_entity_card(self, iri: str) -> dict:
        """Return a service/facility/provider card with explicit, typed relationship evidence."""
        if not isinstance(iri, str):
            raise TypeError("iri must be a string")
        status, kind, row = self._resolve(iri, ("service", "facility", "provider"))
        if status == "resolved":
            return self._card(kind, row)
        return {"status": "not_found" if status == "dangling" else status,
                "entity_type": kind, "id": iri, "fields": {}, "relationships": {}}

    def search_directory(
        self, query: str = "", provider: str | None = None,
        has_telephone: bool | None = None, limit: int = 10, offset: int = 0,
    ) -> dict:
        """Search linked facility text with full-match, source-scoped summaries."""
        from src.directory_search import search_directory
        return search_directory(self, query, provider, has_telephone, limit, offset)

    def search_service_candidates(self, query: str, limit: int = 5, offset: int = 0) -> dict:
        """Match service name/category/audience by literal casefold substring.

        Empty queries match all services, as upstream does. Locality is evidence only,
        not a filter or a claim about geographic containment. Rows keep source order.
        """
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if type(limit) is not int or not 1 <= limit <= 25:
            raise ValueError("limit must be an integer from 1 to 25")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        needle = query.casefold()
        matches = [row for row in self.rows["service"]
                   if any(needle in row[column].casefold() for column in MATCH_FIELDS)]
        candidates = []
        for row in matches[offset:offset + limit]:
            target_id = present(row["schema:provider"])
            status, kind, provider = self._resolve(target_id, ("facility", "provider"))
            source_column = "schema:name" if present(row["schema:name"]) else "schema:category"
            name = present(row[source_column])
            location = {"status": "unknown", "label": None, "scope": None, "evidence": None}
            if provider is not None:
                addr_status, _, address = self._resolve(present(provider["schema:address"]), ("address",))
                locality = present(address["schema:addressLocality"]) if address else None
                location = {
                    "status": "known" if locality is not None else addr_status if addr_status != "resolved" else "missing",
                    "label": locality,
                    "scope": "facility_address" if kind == "facility" else "provider_organization_address",
                    "evidence": self._evidence("address", address, "schema:addressLocality") if address else None,
                    "address_relationship_evidence": self._evidence(kind, provider, "schema:address"),
                }
            candidates.append({
                "service_id": row["iri"], "name": name, "name_source": source_column,
                "name_is_fallback": source_column != "schema:name",
                "provider": {
                    "status": status, "id": target_id, "type": kind,
                    "name": present(provider["schema:name"]) if provider else None,
                    "relationship_evidence": self._evidence("service", row, "schema:provider"),
                    "name_evidence": self._evidence(kind, provider, "schema:name") if provider else None,
                },
                "location": location,
                "match_evidence": [self._evidence("service", row, column) for column in MATCH_FIELDS
                                   if needle in row[column].casefold()],
            })
        end = offset + len(candidates)
        return {
            "status": "ok", "query": query, "total": len(matches), "returned": len(candidates),
            "limit": limit, "offset": offset,
            "next_offset": end if end < len(matches) else None,
            "truncated": len(candidates) < len(matches), "candidates": candidates,
        }
