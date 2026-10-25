"""Synthetic contract tests; no upstream directory data is redistributed."""

import csv
import tempfile
import unittest
from pathlib import Path

from src.service_cards import Directory, telephone_quality, url_quality


HEADERS = {
    "angebotSchema.csv": "iri,schema:name,schema:category,schema:codeValue,schema:audience,schema:areaServed,schema:provider",
    "einrichtungSchema.csv": "iri,schema:name,schema:alternateName,schema:telephone,schema:email,foaf:homepage,schema:mainEntityOfPage,schema:category,schema:availableService,schema:audience,schema:accessibilitySummary,schema:openingHours,schema:parentOrganization,cdf:parentOrgClassification,schema:address",
    "traegerSchema.csv": "iri,schema:name,foaf:homepage,schema:address",
    "adresseSchema.csv": "iri,schema:streetAddress,schema:postalCode,schema:addressLocality,schema:addressCountry,schema:latitude,schema:longitude",
}


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name)
        self.data = {
            "angebotSchema.csv": [
                {"iri": "s1", "schema:name": "Schuldnerberatung", "schema:category": "Beratung", "schema:provider": "f1"},
                {"iri": "s2", "schema:category": "Suchtberatung", "schema:audience": "Erwachsene", "schema:provider": "f2"},
                {"iri": "s3", "schema:category": "Geschäftsstellen", "schema:provider": "p1"},
                {"iri": "s4", "schema:name": "Straße [A]", "schema:category": "Beratung", "schema:provider": "f2"},
            ],
            "einrichtungSchema.csv": [
                {"iri": "f1", "schema:name": "Beratungsstelle", "schema:telephone": "3.06663E+12",
                 "schema:email": "one@example.invalid", "schema:openingHours": "Mo 11–14; Termine nach Vereinbarung",
                 "schema:accessibilitySummary": "Nicht barrierefrei", "schema:audience": "Erwachsene",
                 "schema:mainEntityOfPage": "/lookup?id=one", "schema:parentOrganization": "p1", "schema:address": "a1"},
                {"iri": "f2", "schema:name": "Beratungsstelle", "schema:telephone": "030123456",
                 "schema:email": "two@example.invalid", "schema:address": "a2"},
            ],
            "traegerSchema.csv": [
                {"iri": "p1", "schema:name": "Parent Organization", "foaf:homepage": "https://example.invalid", "schema:address": "a2"},
            ],
            "adresseSchema.csv": [
                {"iri": "a1", "schema:streetAddress": "Example Street 1", "schema:postalCode": "00123", "schema:addressLocality": "Berlin-Wedding"},
                {"iri": "a2", "schema:streetAddress": "Headquarters Street 2", "schema:postalCode": "10115", "schema:addressLocality": "Berlin"},
            ],
        }
        self.write_data()

    def write_data(self):
        for filename, rows in self.data.items():
            with (self.data_dir / filename).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADERS[filename].split(","))
                writer.writeheader()
                writer.writerows(rows)

    def directory(self):
        self.write_data()
        return Directory(self.data_dir)

    def test_explicit_service_facility_address_chain_and_field_attribution(self):
        service = self.directory().get_entity_card("s1")
        relation = service["relationships"]["provider"]
        self.assertEqual((relation["status"], relation["target_type"], relation["target_id"]), ("resolved", "facility", "f1"))
        self.assertEqual(relation["evidence"], {"table": "angebotSchema.csv", "entity_id": "s1", "field": "schema:provider"})
        facility = relation["entity"]
        self.assertEqual(facility["fields"]["email"], "one@example.invalid")
        self.assertEqual(facility["field_evidence"]["email"], {"table": "einrichtungSchema.csv", "entity_id": "f1", "field": "schema:email"})
        address = facility["relationships"]["address"]["entity"]
        self.assertEqual(address["fields"]["postal_code"], "00123")
        self.assertEqual(address["fields"]["street"], "Example Street 1")

    def test_parent_data_does_not_fill_facility_fields_or_address(self):
        card = self.directory().get_entity_card("f1")
        self.assertIsNone(card["fields"]["homepage"])
        self.assertIn("homepage", card["missing_fields"])
        parent = card["relationships"]["parent_organization"]["entity"]
        self.assertEqual(parent["fields"]["homepage"], "https://example.invalid")
        self.assertEqual(card["contact_scope"], "facility_record")
        self.assertEqual(parent["contact_scope"], "provider_record")
        self.assertEqual(card["relationships"]["address"]["entity"]["fields"]["street"], "Example Street 1")
        self.assertEqual(parent["relationships"]["address"]["entity"]["fields"]["street"], "Headquarters Street 2")

    def test_service_can_point_directly_to_provider_without_fabricated_facility(self):
        result = self.directory().search_service_candidates("Geschäftsstellen")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["provider"]["type"], "provider")
        self.assertEqual(candidate["location"]["scope"], "provider_organization_address")
        relation = self.directory().get_entity_card("s3")["relationships"]["provider"]
        self.assertEqual(relation["entity"]["entity_type"], "provider")
        self.assertNotIn("telephone", relation["entity"]["fields"])

    def test_same_name_does_not_merge_distinct_ids(self):
        directory = self.directory()
        self.assertEqual(directory.get_entity_card("f1")["fields"]["name"], directory.get_entity_card("f2")["fields"]["name"])
        self.assertNotEqual(directory.get_entity_card("f1")["fields"]["email"], directory.get_entity_card("f2")["fields"]["email"])
        self.assertEqual(directory.get_entity_card("Beratungsstelle")["status"], "not_found")

    def test_duplicate_id_is_ambiguous_not_last_row_wins(self):
        self.data["einrichtungSchema.csv"].append({"iri": "f1", "schema:name": "Conflicting Name"})
        directory = self.directory()
        self.assertEqual(directory.get_entity_card("f1")["status"], "ambiguous")
        relation = directory.get_entity_card("s1")["relationships"]["provider"]
        self.assertEqual(relation["status"], "ambiguous")
        self.assertIsNone(relation["entity"])
        candidate = directory.search_service_candidates("Schuld")["candidates"][0]
        self.assertEqual(candidate["provider"]["status"], "ambiguous")
        self.assertIsNone(candidate["location"]["label"])

    def test_cross_table_id_collision_is_ambiguous(self):
        self.data["traegerSchema.csv"].append({"iri": "f1", "schema:name": "Conflicting Type"})
        self.assertEqual(self.directory().get_entity_card("s1")["relationships"]["provider"]["status"], "ambiguous")

    def test_missing_dangling_and_wrong_type_relationships_stay_distinct(self):
        self.data["angebotSchema.csv"][0]["schema:provider"] = "unknown-id"
        directory = self.directory()
        self.assertEqual(directory.get_entity_card("s1")["relationships"]["provider"]["status"], "dangling")
        self.assertEqual(directory.get_entity_card("f2")["relationships"]["parent_organization"]["status"], "missing")
        self.data["angebotSchema.csv"][0]["schema:provider"] = "a1"
        relation = self.directory().get_entity_card("s1")["relationships"]["provider"]
        self.assertEqual(relation["status"], "type_mismatch")
        self.assertIsNone(relation["entity"])

    def test_raw_hours_accessibility_and_audience_are_exposed_without_interpretation(self):
        card = self.directory().get_entity_card("f1")
        self.assertEqual(card["fields"]["opening_hours"], "Mo 11–14; Termine nach Vereinbarung")
        self.assertEqual(card["fields"]["accessibility"], "Nicht barrierefrei")
        self.assertEqual(card["fields"]["audience"], "Erwachsene")
        self.assertEqual(card["verification"], "source_record_only")
        self.assertNotIn("open_now", card["fields"])

    def test_literal_casefold_matching_and_deterministic_order(self):
        directory = self.directory()
        self.assertEqual([c["service_id"] for c in directory.search_service_candidates("BERATUNG")["candidates"]], ["s1", "s2", "s4"])
        self.assertEqual([c["service_id"] for c in directory.search_service_candidates("STRASSE")["candidates"]], ["s4"])
        self.assertEqual(directory.search_service_candidates("[A]")["total"], 1)
        self.assertEqual(directory.search_service_candidates(".*")["total"], 0)
        self.assertEqual(directory.search_service_candidates(" Beratung ")["total"], 0)

    def test_category_fallback_and_match_source_are_labeled(self):
        candidate = self.directory().search_service_candidates("Erwachsene")["candidates"][0]
        self.assertEqual(candidate["name"], "Suchtberatung")
        self.assertEqual(candidate["name_source"], "schema:category")
        self.assertTrue(candidate["name_is_fallback"])
        self.assertEqual(candidate["match_evidence"], [{"table": "angebotSchema.csv", "entity_id": "s2", "field": "schema:audience"}])

    def test_pagination_empty_query_and_out_of_bounds(self):
        directory = self.directory()
        first = directory.search_service_candidates("", limit=2)
        self.assertEqual((first["total"], first["returned"], first["next_offset"]), (4, 2, 2))
        self.assertTrue(first["truncated"])
        second = directory.search_service_candidates("", limit=2, offset=first["next_offset"])
        self.assertEqual([c["service_id"] for c in second["candidates"]], ["s3", "s4"])
        self.assertIsNone(second["next_offset"])
        beyond = directory.search_service_candidates("", offset=99)
        self.assertEqual(beyond["returned"], 0)
        self.assertIsNone(beyond["next_offset"])

    def test_invalid_pagination_is_rejected(self):
        directory = self.directory()
        for kwargs in ({"limit": 0}, {"limit": 26}, {"limit": True}, {"offset": -1}, {"offset": 0.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                directory.search_service_candidates("", **kwargs)

    def test_phone_values_remain_raw_and_never_verified(self):
        directory = self.directory()
        one = directory.get_entity_card("f1")
        two = directory.get_entity_card("f2")
        self.assertEqual(one["fields"]["telephone"], "3.06663E+12")
        self.assertEqual(one["quality"]["telephone"]["status"], "suspicious_scientific_notation")
        self.assertEqual(two["fields"]["telephone"], "030123456")
        self.assertEqual(two["quality"]["telephone"]["status"], "digit_only_prefix_unverified")
        self.assertFalse(telephone_quality("+49 30 123456")["verified"])

    def test_url_syntax_checks_do_not_resolve_or_verify_urls(self):
        expected = {
            None: "missing", "/lookup?id=one": "relative_unresolved",
            "www.example.invalid": "missing_scheme", "javascript:alert(1)": "unsupported_scheme",
            "https://example.invalid": "absolute_http_unverified", "https://": "malformed",
            "https://exa mple.invalid": "malformed", "https://[broken": "malformed",
        }
        for value, status in expected.items():
            with self.subTest(value=value):
                self.assertEqual(url_quality(value), {"status": status, "verified": False})
        card = self.directory().get_entity_card("f1")
        self.assertEqual(card["fields"]["source_page"], "/lookup?id=one")

    def test_missing_schema_or_bad_row_width_fails_with_location(self):
        with (self.data_dir / "angebotSchema.csv").open("w", encoding="utf-8") as handle:
            handle.write("iri,schema:name\ns1,Example\n")
        with self.assertRaisesRegex(ValueError, "angebotSchema.csv: missing columns"):
            Directory(self.data_dir)
        self.write_data()
        with (self.data_dir / "angebotSchema.csv").open("a", encoding="utf-8") as handle:
            handle.write("broken,row\n")
        with self.assertRaisesRegex(ValueError, "row width"):
            Directory(self.data_dir)


if __name__ == "__main__":
    unittest.main()
