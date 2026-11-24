from django.contrib.auth import get_user_model
from django.test import TestCase

from qda.models import Analysis, Coding, CodingTheme, Project, Source, Theme
from qda.sync import DocumentError, apply_document, project_document

from .helpers import full_document, sample_project, sample_sources


class SyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("amina", "amina@example.org", "research-2026")
        self.project = Project(owner=self.user, client_id="proj_test_1")

    def store(self, doc=None, sources="default"):
        apply_document(self.project, doc or sample_project(), sample_sources() if sources == "default" else sources)

    def test_round_trip_is_exact(self):
        self.store()
        self.assertEqual(project_document(self.project), full_document())

    def test_columns_for_the_admin(self):
        self.store()
        p = self.project
        self.assertEqual((p.title, p.researcher, p.organization, p.topic), ("Kilosa Youth Study", "Amina", "SST", "Youth entrepreneurship"))
        kii = Source.objects.get(project=p, client_id="src_kii")
        self.assertEqual((kii.source_type, kii.respondent_id, kii.word_count), ("KII", "R01", 8))
        credit = Theme.objects.get(project=p, client_id="thm_credit")
        self.assertEqual(credit.parent.client_id, "thm_finance")
        self.assertIsNone(credit.analysis)  # sub-themes belong to their top theme's analysis
        self.assertEqual(credit.top_level().analysis.name, "Challenges")
        self.assertEqual(credit.path(), "Finance › No access to credit")
        cod = Coding.objects.get(project=p, client_id="cod_1")
        self.assertEqual(cod.source, kii)
        self.assertEqual((cod.start, cod.end, cod.weight), (0, 22, 8))
        self.assertEqual(sorted(t.client_id for t in cod.themes.all()), ["thm_credit", "thm_jobs"])
        self.assertIsNone(Coding.objects.get(project=p, client_id="cod_2").weight)

    def test_update_keeps_unchanged_rows_and_deletes_removed_ones(self):
        self.store()
        before = dict(Coding.objects.filter(project=self.project).values_list("client_id", "pk"))
        theme_pks = dict(Theme.objects.filter(project=self.project).values_list("client_id", "pk"))
        doc = sample_project()
        doc["codings"][0]["themeIds"] = ["thm_finance"]
        doc["codings"][0]["weight"] = 3
        doc["codings"].pop(1)
        doc["codings"].append({"id": "cod_3", "sourceId": "src_fgd", "themeIds": ["thm_jobs"], "start": 1, "end": 5, "quote": "x"})
        self.store(doc, sources=None)
        after = dict(Coding.objects.filter(project=self.project).values_list("client_id", "pk"))
        self.assertEqual(after["cod_1"], before["cod_1"])          # same row, updated in place
        self.assertNotIn("cod_2", after)
        self.assertIn("cod_3", after)
        self.assertEqual(dict(Theme.objects.filter(project=self.project).values_list("client_id", "pk")), theme_pks)
        cod1 = Coding.objects.get(pk=after["cod_1"])
        self.assertEqual(cod1.weight, 3)
        self.assertEqual([t.client_id for t in cod1.themes.all()], ["thm_finance"])
        self.assertEqual(CodingTheme.objects.filter(coding__project=self.project).count(), 2)
        expected = dict(doc, sources=sample_sources())
        self.assertEqual(project_document(self.project), expected)

    def test_sources_left_out_are_kept(self):
        self.store()
        doc = sample_project()
        doc["title"] = "Renamed"
        self.store(doc, sources=None)
        self.assertEqual(project_document(self.project)["sources"], sample_sources())
        self.assertEqual(self.project.title, "Renamed")

    def test_removing_a_source_removes_its_rows(self):
        self.store()
        doc = sample_project()
        doc["codings"] = [c for c in doc["codings"] if c["sourceId"] != "src_fgd"]
        self.store(doc, sources=sample_sources()[:1])
        self.assertEqual(list(Source.objects.filter(project=self.project).values_list("client_id", flat=True)), ["src_kii"])
        self.assertEqual(list(Coding.objects.filter(project=self.project).values_list("client_id", flat=True)), ["cod_1"])

    def test_unknown_fields_and_dangling_references_survive(self):
        doc = sample_project()
        doc["futureSetting"] = {"nested": [1, 2, 3]}
        doc["themes"][0]["icon"] = "star"
        doc["codings"][0]["themeIds"] = ["thm_credit", "thm_gone"]
        doc["codings"][1]["sourceId"] = "src_gone"
        self.store(doc)
        self.assertEqual(project_document(self.project), dict(doc, sources=sample_sources()))
        self.assertIsNone(Coding.objects.get(project=self.project, client_id="cod_2").source)

    def test_reordering_is_kept(self):
        self.store()
        doc = sample_project()
        doc["themes"].reverse()
        sources = sample_sources()
        sources.reverse()
        self.store(doc, sources=sources)
        result = project_document(self.project)
        self.assertEqual([t["id"] for t in result["themes"]], ["thm_jobs", "thm_credit", "thm_finance"])
        self.assertEqual([s["id"] for s in result["sources"]], ["src_fgd", "src_kii"])

    def test_bad_documents_are_refused(self):
        bad = []
        doc = sample_project(); doc["themes"].append(dict(doc["themes"][0])); bad.append(doc)       # duplicate id
        doc = sample_project(); del doc["codings"][0]["id"]; bad.append(doc)                       # missing id
        doc = sample_project(); doc["codings"][0]["id"] = 17; bad.append(doc)                       # id not text
        doc = sample_project(); doc["themes"] = {"thm": {}}; bad.append(doc)                        # not a list
        doc = sample_project(); doc["analyses"] = ["x"]; bad.append(doc)                            # entries not objects
        for doc in bad:
            with self.subTest(doc=doc):
                with self.assertRaises(DocumentError):
                    self.store(doc)
        with self.assertRaises(DocumentError):
            self.store(["not", "a", "project"])
        self.assertFalse(Project.objects.exists())

    def test_odd_numbers_do_not_break_storage(self):
        doc = sample_project()
        doc["codings"][0].update({"start": -4, "end": "12", "weight": 99999})
        self.store(doc)
        cod = Coding.objects.get(project=self.project, client_id="cod_1")
        self.assertEqual((cod.start, cod.end, cod.weight), (0, 0, None))
        self.assertEqual(project_document(self.project)["codings"][0]["end"], "12")  # still returned as sent

    def test_analysis_deleted_from_document(self):
        self.store()
        doc = sample_project()
        doc["analyses"] = doc["analyses"][:1]
        doc["themes"][2]["analysisId"] = "ana_main"
        self.store(doc, sources=None)
        self.assertEqual(Analysis.objects.filter(project=self.project).count(), 1)
        self.assertEqual(Theme.objects.get(project=self.project, client_id="thm_jobs").analysis.client_id, "ana_main")
