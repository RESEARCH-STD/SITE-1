import gzip
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from qda.models import Project, Source

from .helpers import full_document, sample_project, sample_sources

LIST = reverse("qda:api_projects")


def detail(client_id):
    return reverse("qda:api_project", args=[client_id])


class ApiTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.amina = User.objects.create_user("amina", "amina@example.org", "research-2026")
        self.baraka = User.objects.create_user("baraka", "baraka@example.org", "research-2026")
        self.client.force_login(self.amina)

    def put(self, client_id, body, client=None, **extra):
        return (client or self.client).put(detail(client_id), data=json.dumps(body), content_type="application/json", **extra)

    def create(self, client_id="proj_test_1", writer="w1", client=None):
        body = {"base": None, "writer": writer, "deleted": False, "project": sample_project(client_id), "sources": sample_sources()}
        return self.put(client_id, body, client=client)


class SignedOutTests(TestCase):
    def test_everything_needs_a_session(self):
        for response in (
            self.client.get(LIST),
            self.client.get(detail("proj_x")),
            self.client.put(detail("proj_x"), data="{}", content_type="application/json"),
        ):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["error"], "signed_out")


class UploadTests(ApiTestCase):
    def test_create_then_read_back(self):
        r = self.create()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json(), {"rev": 1})
        heads = self.client.get(LIST).json()["projects"]
        self.assertEqual(heads, [{"id": "proj_test_1", "rev": 1, "deleted": False}])
        full = self.client.get(LIST, {"ids": "proj_test_1,proj_missing"}).json()["projects"]
        self.assertEqual(len(full), 1)
        row = full[0]
        self.assertEqual((row["id"], row["rev"], row["deleted"], row["title"]), ("proj_test_1", 1, False, "Kilosa Youth Study"))
        self.assertEqual(dict(row["project"], sources=row["sources"]), full_document())
        self.assertNotIn("sources", row["project"])
        self.assertIsInstance(row["updated"], int)
        one = self.client.get(detail("proj_test_1")).json()
        self.assertEqual(one["project"], row["project"])
        self.assertEqual(self.client.get(detail("proj_test_1"), {"head": 1}).json(), {"id": "proj_test_1", "rev": 1, "deleted": False})
        self.assertEqual(self.client.get(detail("nope")).status_code, 404)

    def test_update_needs_the_current_revision(self):
        self.create()
        doc = sample_project()
        doc["title"] = "Second version"
        r = self.put("proj_test_1", {"base": 1, "writer": "w1", "project": doc})
        self.assertEqual((r.status_code, r.json()), (200, {"rev": 2}))
        doc["title"] = "Stale edit from another computer"
        r = self.put("proj_test_1", {"base": 1, "writer": "w2", "project": doc})
        self.assertEqual(r.status_code, 409)
        current = r.json()["current"]
        self.assertEqual((current["rev"], current["title"]), (2, "Second version"))
        self.assertEqual(Project.objects.get().title, "Second version")

    def test_transcripts_kept_when_left_out(self):
        self.create()
        doc = sample_project()
        doc["codings"].append({"id": "cod_9", "sourceId": "src_kii", "themeIds": ["thm_jobs"], "start": 3, "end": 9, "quote": "cannot"})
        self.assertEqual(self.put("proj_test_1", {"base": 1, "writer": "w1", "project": doc}).status_code, 200)
        row = self.client.get(detail("proj_test_1")).json()
        self.assertEqual(row["sources"], sample_sources())
        self.assertEqual(len(row["project"]["codings"]), 3)

    def test_resending_a_lost_upload_is_accepted(self):
        self.create(writer="laptop")
        doc = sample_project()
        doc["title"] = "Edit whose answer was lost"
        self.assertEqual(self.put("proj_test_1", {"base": 1, "writer": "laptop", "project": doc}).json(), {"rev": 2})
        # The laptop never heard back, so it still thinks the account holds rev 1.
        doc["title"] = "Edit plus a bit more"
        r = self.put("proj_test_1", {"base": 1, "writer": "laptop", "project": doc})
        self.assertEqual((r.status_code, r.json()), (200, {"rev": 3}))
        # Another computer making the same claim is a real conflict.
        r = self.put("proj_test_1", {"base": 1, "writer": "lab", "project": doc})
        self.assertEqual(r.status_code, 409)

    def test_resending_a_lost_first_upload(self):
        self.create(writer="laptop")
        r = self.create(writer="laptop")
        self.assertEqual((r.status_code, r.json()), (200, {"rev": 2}))
        self.assertEqual(Project.objects.count(), 1)
        r = self.create(writer="lab")              # someone else's first upload of the same id
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["current"]["rev"], 2)

    def test_delete_restore_and_conflicts(self):
        self.create()
        r = self.put("proj_test_1", {"base": 1, "writer": "w1", "deleted": True})
        self.assertEqual((r.status_code, r.json()), (200, {"rev": 2}))
        self.assertEqual(self.client.get(LIST).json()["projects"], [{"id": "proj_test_1", "rev": 2, "deleted": True}])
        tomb = self.client.get(detail("proj_test_1")).json()
        self.assertTrue(tomb["deleted"])
        self.assertEqual(len(tomb["sources"]), 2)                     # kept, for the admin's trash
        # Edits made elsewhere bring it back.
        r = self.put("proj_test_1", {"base": 2, "writer": "w2", "project": sample_project(), "sources": sample_sources()})
        self.assertEqual((r.status_code, r.json()), (200, {"rev": 3}))
        self.assertFalse(Project.objects.get().deleted)
        # Deleting from a stale copy is refused, with the newer copy.
        r = self.put("proj_test_1", {"base": 2, "writer": "w1", "deleted": True})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()["current"]["deleted"])

    def test_deleting_something_never_uploaded(self):
        r = self.put("proj_never", {"base": None, "writer": "w1", "deleted": True})
        self.assertEqual((r.status_code, r.json()), (200, {"rev": None}))
        self.assertFalse(Project.objects.exists())

    def test_project_gone_from_the_account(self):
        r = self.put("proj_gone", {"base": 4, "writer": "w1", "project": sample_project("proj_gone")})
        self.assertEqual((r.status_code, r.json()["current"]), (409, None))

    def test_new_project_without_sources(self):
        r = self.put("proj_test_1", {"base": None, "writer": "w1", "project": sample_project()})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Source.objects.count(), 0)

    def test_people_only_see_their_own_projects(self):
        self.create()
        other = Client()
        other.force_login(self.baraka)
        self.assertEqual(other.get(LIST).json()["projects"], [])
        self.assertEqual(other.get(detail("proj_test_1")).status_code, 404)
        # The same id (every browser seeds the same demo id) is a separate project.
        self.assertEqual(self.create(client=other).status_code, 201)
        self.assertEqual(Project.objects.filter(client_id="proj_test_1").count(), 2)
        doc = sample_project()
        doc["title"] = "Baraka's version"
        self.assertEqual(self.put("proj_test_1", {"base": 1, "writer": "w9", "project": doc}, client=other).status_code, 200)
        self.assertEqual(Project.objects.get(owner=self.amina).title, "Kilosa Youth Study")

    def test_page_opened_for_someone_else(self):
        r = self.client.get(LIST, HTTP_X_TB_USER=str(self.baraka.pk))
        self.assertEqual((r.status_code, r.json()["error"]), (409, "user_changed"))
        self.assertEqual(self.client.get(LIST, HTTP_X_TB_USER=str(self.amina.pk)).status_code, 200)

    def test_bad_uploads(self):
        r = self.client.put(detail("proj_test_1"), data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.put("proj_test_1", {"base": "1", "project": sample_project()})
        self.assertEqual(r.status_code, 400)
        doc = sample_project()
        doc["codings"].append(doc["codings"][0])
        r = self.put("proj_test_1", {"base": None, "project": doc})
        self.assertEqual((r.status_code, r.json()["error"]), (400, "bad_document"))
        r = self.put("x" * 101, {"base": None, "project": sample_project()})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Project.objects.exists())

    def test_gzipped_upload(self):
        body = {"base": None, "writer": "w1", "project": sample_project(), "sources": sample_sources()}
        r = self.client.put(detail("proj_test_1"), data=gzip.compress(json.dumps(body).encode()),
                            content_type="application/json", HTTP_CONTENT_ENCODING="gzip")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Source.objects.count(), 2)
        r = self.client.put(detail("proj_test_2"), data=b"not gzip at all",
                            content_type="application/json", HTTP_CONTENT_ENCODING="gzip")
        self.assertEqual(r.status_code, 400)

    @override_settings(QDA_MAX_UPLOAD_BYTES=2000)
    def test_size_limit(self):
        body = {"base": None, "writer": "w1", "project": sample_project(), "sources": sample_sources() * 1}
        body["sources"][0]["text"] = "word " * 1000
        self.assertEqual(self.put("proj_big", body).status_code, 413)
        # A small gzip that unpacks to something too big is refused as well.
        bomb = gzip.compress(json.dumps(body).encode())
        self.assertLess(len(bomb), 2000)
        r = self.client.put(detail("proj_big"), data=bomb, content_type="application/json", HTTP_CONTENT_ENCODING="gzip")
        self.assertEqual(r.status_code, 413)
        self.assertFalse(Project.objects.exists())

    def test_responses_are_gzipped_for_slow_connections(self):
        self.create()
        r = self.client.get(LIST, {"ids": "proj_test_1"}, HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(r.headers.get("Content-Encoding"), "gzip")
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")


class CsrfTests(ApiTestCase):
    def test_uploads_need_the_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.amina)
        body = json.dumps({"base": None, "writer": "w1", "project": sample_project()})
        r = client.put(detail("proj_test_1"), data=body, content_type="application/json")
        self.assertEqual(r.status_code, 403)
        page = client.get(reverse("qda:dashboard"))                 # pages set the CSRF cookie
        token = page.cookies["csrftoken"].value
        r = client.put(detail("proj_test_1"), data=body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 201)
