"""Behavioral contracts for V3 directory search on small synthetic tables."""
import csv
import tempfile
import unittest
from pathlib import Path

from src.service_cards import Directory, FIELDS, RELATIONSHIPS, TABLES


class DirectorySearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.rows = {
            "facility": [
                {"iri": "f1", "schema:name": "Frauenberatung", "schema:alternateName": "Nordstelle",
                 "schema:availableService": "Beratung für Angehörige", "schema:telephone": " 3.06663E+12 ",
                 "schema:email": "one@example.invalid", "schema:openingHours": "Montag vormittags",
                 "schema:accessibilitySummary": "barrierefrei erreichbar", "schema:parentOrganization": "p1",
                 "schema:address": "a1"},
                {"iri": "f2", "schema:name": "Haus B", "schema:telephone": "30123456",
                 "schema:parentOrganization": "p1", "schema:address": "a2"},
                {"iri": "f3", "schema:name": "Haus C", "schema:telephone": "  ",
                 "schema:parentOrganization": "unknown", "schema:address": "not-address"},
                {"iri": "f4", "schema:name": "Haus D", "schema:telephone": "+49 30 12345"},
            ],
            "service": [
                {"iri": "s1", "schema:name": "Suchtberatung", "schema:category": "Therapie",
                 "schema:audience": "Erwachsene", "schema:areaServed": "Berlin", "schema:provider": "f1"},
                {"iri": "s2", "schema:name": "Suchtberatung", "schema:provider": "f1"},
                {"iri": "s3", "schema:name": "Jugendberatung", "schema:provider": "f2"},
                {"iri": "s4", "schema:name": "Provider-only keyword", "schema:provider": "p1"},
                {"iri": "s5", "schema:name": "Dangling keyword", "schema:provider": "ghost"},
                {"iri": "s6", "schema:name": "Wrongtype keyword", "schema:provider": "a1"},
            ],
            "provider": [
                {"iri": "p1", "schema:name": "AWO Kreisverband Berlin-Mitte", "schema:address": "a2"},
                {"iri": "not-address", "schema:name": "Not an address"},
            ],
            "address": [
                {"iri": "a1", "schema:streetAddress": "Beispielstraße 1", "schema:postalCode": "00123",
                 "schema:addressLocality": "Wedding"},
                {"iri": "a2", "schema:streetAddress": "Andere Straße 2", "schema:postalCode": "10115",
                 "schema:addressLocality": "Berlin"},
            ],
        }

    def directory(self):
        for kind, filename in TABLES.items():
            columns = ["iri", *FIELDS[kind].values(), *(x[0] for x in RELATIONSHIPS[kind].values())]
            with (self.folder / filename).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, list(dict.fromkeys(columns)))
                writer.writeheader()
                for row in self.rows[kind]:
                    writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
        return Directory(self.folder)

    def test_terms_can_match_different_typed_fields_with_casefold_and_whitespace(self):
        page = self.directory().search_directory("  SUCHTBERATUNG\tBEISPIELSTRASSE  ")
        self.assertEqual(page["total"], 1)
        hit = page["hits"][0]
        self.assertEqual(hit["iri"], "f1")
        refs = {(x["table"], x["entity_id"], x["field"]) for x in hit["matched_fields"]}
        self.assertIn(("angebotSchema.csv", "s1", "schema:name"), refs)
        self.assertIn(("adresseSchema.csv", "a1", "schema:streetAddress"), refs)
        self.assertEqual(self.directory().search_directory("Suchtberatung not-present")["total"], 0)

    def test_every_specified_field_is_searchable_and_match_is_literal(self):
        directory = self.directory()
        for query in ("Nordstelle", "Angehörige", "Montag", "barrierefrei", "Erwachsene", "Therapie", "00123"):
            with self.subTest(query=query):
                self.assertEqual(directory.search_directory(query)["hits"][0]["iri"], "f1")
        self.assertEqual(directory.search_directory(".*")["total"], 0)

    def test_provider_filter_is_separate_and_typed(self):
        directory = self.directory()
        self.assertEqual(directory.search_directory("Mitte")["total"], 0)
        self.assertEqual(directory.search_directory(provider="BERLIN-MITTE")["total"], 2)
        self.assertEqual(directory.search_directory("Frauen", provider="Berlin-Mitte")["total"], 1)
        self.assertEqual(directory.search_directory(provider="unknown")["total"], 0)

    def test_multiple_services_do_not_duplicate_facility_and_invalid_links_do_not_join(self):
        directory = self.directory()
        self.assertEqual(directory.search_directory("Suchtberatung")["total"], 1)
        for query in ("Provider-only", "Dangling keyword", "Wrongtype"):
            with self.subTest(query=query):
                self.assertEqual(directory.search_directory(query)["total"], 0)

    def test_pagination_summaries_cover_full_filtered_population(self):
        directory = self.directory()
        page = directory.search_directory("", limit=1)
        self.assertEqual((page["total"], page["returned"], page["next_offset"]), (4, 1, 1))
        self.assertEqual(page["summary_denominator"], 4)
        self.assertEqual(page["summary_scope"], "all_matching_facility_records")
        self.assertEqual(page["missing_counts"], {"telephone": 1, "email": 3, "openingHours": 3, "accessibilitySummary": 3})
        self.assertEqual(page["phone_format_counts"], {"missing": 1, "digit_only_prefix_unverified": 1,
                         "suspicious_scientific_notation": 1, "unverified_format": 1})
        second = directory.search_directory(limit=2, offset=1)
        self.assertEqual([x["iri"] for x in second["hits"]], ["f2", "f3"])
        self.assertEqual(second["missing_counts"], page["missing_counts"])
        beyond = directory.search_directory(offset=99)
        self.assertEqual((beyond["returned"], beyond["next_offset"]), (0, None))

    def test_nonblank_phone_filter_and_raw_characters(self):
        directory = self.directory()
        page = directory.search_directory(has_telephone=True, limit=1)
        self.assertEqual(page["total"], 3)
        self.assertEqual(page["hits"][0]["telephone"], " 3.06663E+12 ")
        self.assertEqual(page["missing_counts"]["telephone"], 0)
        self.assertEqual(page["phone_format_counts"]["missing"], 0)
        self.assertEqual(page["phone_format_verification"], "unverified_syntax_only")
        self.assertEqual(directory.search_directory(has_telephone=False)["hits"][0]["iri"], "f3")

    def test_provider_summary_preserves_no_link_and_unresolved_link(self):
        page = self.directory().search_directory(limit=1)
        groups = {(x["status"], x["id"]): x for x in page["by_provider"]}
        self.assertEqual(groups[("resolved", "p1")]["count"], 2)
        self.assertEqual(groups[("resolved", "p1")]["name"], "AWO Kreisverband Berlin-Mitte")
        self.assertEqual(groups[("dangling", "unknown")]["label"], "unresolved provider link")
        self.assertEqual(groups[("missing", None)]["label"], "no provider link")
        bad_address = self.directory().search_directory("Haus C")["hits"][0]
        self.assertEqual(bad_address["address_status"], "type_mismatch")
        self.assertIsNone(bad_address["street"])

    def test_ambiguous_ids_are_not_arbitrary_join_winners(self):
        self.rows["facility"].append({"iri": "f1", "schema:name": "Contradiction"})
        directory = self.directory()
        page = directory.search_directory()
        self.assertEqual(page["total"], 3)
        self.assertEqual(page["excluded_ambiguous_facility_ids"], ["f1"])
        self.assertEqual(directory.search_directory("Suchtberatung")["total"], 0)
        self.rows["provider"].append({"iri": "p1", "schema:name": "Different provider"})
        page = self.directory().search_directory("Haus B")
        self.assertEqual(page["by_provider"][0]["status"], "ambiguous")
        self.assertIsNone(page["by_provider"][0]["name"])

    def test_validation_rejects_bad_types_and_pagination(self):
        directory = self.directory()
        for kwargs in ({"query": None}, {"provider": 1}, {"has_telephone": 1}, {"has_telephone": "true"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                directory.search_directory(**kwargs)
        for kwargs in ({"limit": 0}, {"limit": 26}, {"limit": True}, {"offset": -1}, {"offset": False}, {"offset": 0.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                directory.search_directory(**kwargs)


if __name__ == "__main__":
    unittest.main()
