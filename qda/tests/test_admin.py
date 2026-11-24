import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from qda.models import Coding, Project, Theme
from qda.sync import apply_document, project_document

from .helpers import sample_project, sample_sources


class AdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@example.org", "admin-pass-2026")
        self.amina = User.objects.create_user("amina", "amina@example.org", "research-2026")
        self.p1 = Project(owner=self.amina, client_id="proj_1", revision=1)
        apply_document(self.p1, sample_project("proj_1"), sample_sources())
        self.p2 = Project(owner=self.amina, client_id="proj-demo-community-perceptions", revision=1)
        apply_document(self.p2, sample_project("proj-demo-community-perceptions"), sample_sources())
        self.client.force_login(self.admin)

    def test_pages_open(self):
        theme = Theme.objects.filter(project=self.p1).first()
        coding = Coding.objects.filter(project=self.p1).first()
        urls = [
            reverse("admin:qda_project_changelist"),
            reverse("admin:qda_project_changelist") + "?demo=no",
            reverse("admin:qda_project_change", args=[self.p1.pk]),
            reverse("admin:qda_source_changelist") + "?q=loans",
            reverse("admin:qda_source_change", args=[self.p1.sources.first().pk]),
            reverse("admin:qda_theme_changelist"),
            reverse("admin:qda_theme_change", args=[theme.pk]),
            reverse("admin:qda_coding_changelist") + f"?project__id__exact={self.p1.pk}",
            reverse("admin:qda_coding_changelist") + f"?themes__id__exact={theme.pk}",
            reverse("admin:qda_coding_change", args=[coding.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.get(reverse("admin:qda_project_changelist") + "?demo=no")
        self.assertContains(r, f'value="{self.p1.pk}" class="action-select"')
        self.assertNotContains(r, f'value="{self.p2.pk}" class="action-select"')   # the demo copy

    def test_content_is_read_only(self):
        self.assertEqual(self.client.get(reverse("admin:qda_coding_add")).status_code, 403)
        r = self.client.post(reverse("admin:qda_theme_change", args=[Theme.objects.first().pk]), {"name": "Hacked"})
        self.assertEqual(r.status_code, 403)

    def action(self, name, *projects):
        return self.client.post(reverse("admin:qda_project_changelist"), {
            "action": name, "_selected_action": [p.pk for p in projects],
        })

    def test_trash_and_restore(self):
        self.action("move_to_trash", self.p1)
        self.p1.refresh_from_db()
        self.assertTrue(self.p1.deleted)
        self.assertEqual((self.p1.revision, self.p1.last_writer), (2, "admin"))
        self.action("restore_from_trash", self.p1)
        self.p1.refresh_from_db()
        self.assertFalse(self.p1.deleted)
        self.assertEqual(self.p1.revision, 3)

    def test_backup_download(self):
        r = self.action("download_backup", self.p1)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertIn("kilosa-youth-study-project-backup.json", r["Content-Disposition"])
        self.assertEqual(json.loads(r.content), project_document(self.p1))
        r = self.action("download_backup", self.p1, self.p2)
        self.assertEqual(r["Content-Type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            first = json.loads(archive.read(sorted(archive.namelist())[0]))
            self.assertIn(first["id"], {"proj_1", "proj-demo-community-perceptions"})

    def test_hard_delete_still_available(self):
        r = self.action("delete_selected", self.p1)
        self.assertEqual(r.status_code, 200)                       # confirmation page
        self.client.post(reverse("admin:qda_project_changelist"), {
            "action": "delete_selected", "_selected_action": [self.p1.pk], "post": "yes",
        })
        self.assertFalse(Project.objects.filter(pk=self.p1.pk).exists())
