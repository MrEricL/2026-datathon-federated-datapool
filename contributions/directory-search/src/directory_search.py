"""Broad lexical facility retrieval without changing the V2 service matcher."""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.service_cards import Directory


FACILITY_FIELDS = (
    "schema:name", "schema:alternateName", "schema:category",
    "schema:availableService", "schema:audience", "schema:accessibilitySummary",
    "schema:openingHours",
)
SERVICE_FIELDS = ("schema:name", "schema:category", "schema:audience", "schema:areaServed")
ADDRESS_FIELDS = ("schema:streetAddress", "schema:postalCode", "schema:addressLocality")
MISSING_FIELDS = {
    "telephone": "schema:telephone", "email": "schema:email",
    "openingHours": "schema:openingHours", "accessibilitySummary": "schema:accessibilitySummary",
}
PHONE_STATUSES = (
    "missing", "digit_only_prefix_unverified", "suspicious_scientific_notation", "unverified_format",
)


def search_directory(
    directory: Directory, query: str = "", provider: str | None = None,
    has_telephone: bool | None = None, limit: int = 10, offset: int = 0,
) -> dict:
    """Return stable pages and whole-population summaries of lexical facility matches."""
    # Import lazily so Directory can expose a thin method without a module cycle.
    from src.service_cards import present, telephone_quality

    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if provider is not None and not isinstance(provider, str):
        raise TypeError("provider must be a string or None")
    if has_telephone is not None and type(has_telephone) is not bool:
        raise TypeError("has_telephone must be a boolean or None")
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError("limit must be an integer from 1 to 25")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")

    terms = list(dict.fromkeys(query.casefold().split()))
    provider_term = provider.casefold() if provider is not None else None

    # Only typed, unambiguous service -> facility links contribute searchable text.
    services_by_facility: dict[str, list[dict[str, str]]] = {}
    for service in directory.rows["service"]:
        service_status, _, resolved_service = directory._resolve(service["iri"], ("service",))
        if service_status != "resolved":
            continue
        target = present(resolved_service["schema:provider"])
        target_status, _, facility = directory._resolve(target, ("facility",))
        if target_status == "resolved":
            services_by_facility.setdefault(facility["iri"], []).append(resolved_service)

    matches = []
    seen = set()
    excluded_ambiguous_ids = []
    for raw_facility in directory.rows["facility"]:
        iri = raw_facility["iri"]
        if iri in seen:
            continue
        seen.add(iri)
        status, _, facility = directory._resolve(iri, ("facility",))
        if status != "resolved":
            excluded_ambiguous_ids.append(iri)
            continue

        parent_id = present(facility["schema:parentOrganization"])
        parent_status, _, parent = directory._resolve(parent_id, ("provider",))
        parent_name = present(parent["schema:name"]) if parent is not None else None
        if provider_term is not None and (parent_name is None or provider_term not in parent_name.casefold()):
            continue
        raw_phone = facility["schema:telephone"]
        phone_present = present(raw_phone) is not None
        if has_telephone is not None and phone_present != has_telephone:
            continue

        address_status, _, address = directory._resolve(present(facility["schema:address"]), ("address",))
        searchable = [("facility", facility, column) for column in FACILITY_FIELDS]
        if address is not None:
            searchable.extend(("address", address, column) for column in ADDRESS_FIELDS)
        for service in services_by_facility.get(iri, []):
            searchable.extend(("service", service, column) for column in SERVICE_FIELDS)
        if not all(any(term in row[column].casefold() for _, row, column in searchable) for term in terms):
            continue

        matched_fields = []
        for kind, row, column in searchable:
            matched_terms = [term for term in terms if term in row[column].casefold()]
            if matched_terms:
                matched_fields.append({**directory._evidence(kind, row, column), "matched_terms": matched_terms})
        parent_summary = {
            "status": parent_status, "id": parent_id, "name": parent_name,
            "label": parent_name if parent_status == "resolved" else "no provider link" if parent_status == "missing" else "unresolved provider link",
        }
        hit = {
            "iri": iri, "name": facility["schema:name"], "matched_fields": matched_fields,
            "street": present(address["schema:streetAddress"]) if address is not None else None,
            "postal_code": present(address["schema:postalCode"]) if address is not None else None,
            "locality": present(address["schema:addressLocality"]) if address is not None else None,
            "address_status": address_status,
            "telephone": raw_phone, "has_email": present(facility["schema:email"]) is not None,
            "parent_provider": parent_summary,
        }
        matches.append((facility, hit))

    total = len(matches)
    missing_counts = {name: sum(present(row[column]) is None for row, _ in matches)
                      for name, column in MISSING_FIELDS.items()}
    phone_counts = Counter(telephone_quality(present(row["schema:telephone"]))["status"] for row, _ in matches)
    by_provider = {}
    for _, hit in matches:
        parent = hit["parent_provider"]
        key = (parent["status"], parent["id"])
        if key not in by_provider:
            by_provider[key] = {**parent, "count": 0}
        by_provider[key]["count"] += 1

    hits = [hit for _, hit in matches[offset:offset + limit]]
    end = offset + len(hits)
    return {
        "status": "ok", "query": query, "provider": provider, "has_telephone": has_telephone,
        "record_unit": "facility_records", "total": total, "returned": len(hits),
        "limit": limit, "offset": offset, "next_offset": end if end < total else None,
        "truncated": len(hits) < total, "hits": hits,
        "summary_scope": "all_matching_facility_records", "summary_denominator": total,
        "missing_counts": missing_counts, "by_provider": list(by_provider.values()),
        "phone_format_counts": {status: phone_counts[status] for status in PHONE_STATUSES},
        "phone_format_verification": "unverified_syntax_only",
        "excluded_ambiguous_facility_ids": excluded_ambiguous_ids,
    }
