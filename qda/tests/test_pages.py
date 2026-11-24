import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from qda.models import Project

APP_PAGES = ["dashboard", "projects", "workspace", "analysis", "clouds", "export", "account"]


def tb_config(response):
    match = re.search(r'<script id="tb-config" type="application/json">(.*?)</script>', response.content.decode(), re.S)
    return json.loads(match.group(1))


class GateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("amina", "Amina@Example.org", "research-2026")

    def test_visitors_start_on_the_sign_in_page(self):
        r = self.client.get(reverse("qda:dashboard"))
        self.assertRedirects(r, reverse("qda:welcome"), fetch_redirect_response=False)
        r = self.client.get(reverse("qda:workspace") + "?source=src_1")
        self.assertRedirects(r, reverse("qda:welcome") + "?next=%2Fqda%2Fworkspace%2F%3Fsource%3Dsrc_1", fetch_redirect_response=False)
        for name in ("welcome", "guide", "about"):
            self.assertEqual(self.client.get(reverse(f"qda:{name}")).status_code, 200, name)

    def test_every_app_page_opens_once_signed_in(self):
        self.client.force_login(self.user)
        for name in APP_PAGES:
            r = self.client.get(reverse(f"qda:{name}"))
            self.assertEqual(r.status_code, 200, name)
            config = tb_config(r)
            self.assertEqual(config["user"]["id"], self.user.pk)
            self.assertEqual(config["projectsApi"], reverse("qda:api_projects"))
            self.assertEqual(config["urls"]["workspace"], reverse("qda:workspace"))

    def test_continue_without_an_account(self):
        r = self.client.post(reverse("qda:welcome"), {"action": "guest", "next": "/qda/analysis/"})
        self.assertRedirects(r, "/qda/analysis/", fetch_redirect_response=False)
        cookie = r.cookies["tb_guest"]
        self.assertEqual(cookie.value, "1")
        self.assertEqual(cookie["max-age"], "")                       # gone when the browser closes
        self.assertTrue(cookie["httponly"])
        for name in APP_PAGES:
            r = self.client.get(reverse(f"qda:{name}"))
            self.assertEqual(r.status_code, 200, name)
            self.assertIsNone(tb_config(r)["user"])

    @override_settings(QDA_ALLOW_GUESTS=False)
    def test_guests_can_be_switched_off(self):
        r = self.client.get(reverse("qda:welcome"))
        self.assertNotContains(r, "Continue without an account")
        self.client.post(reverse("qda:welcome"), {"action": "guest"})
        self.client.cookies["tb_guest"] = "1"
        self.assertEqual(self.client.get(reverse("qda:dashboard")).status_code, 302)

    def test_sign_in_with_username_or_email(self):
        for login in ("amina", "amina@example.org"):
            with self.subTest(login=login):
                self.client.cookies["tb_guest"] = "1"
                r = self.client.post(reverse("qda:welcome"), {"username": login, "password": "research-2026", "next": "/qda/projects/"})
                self.assertRedirects(r, "/qda/projects/", fetch_redirect_response=False)
                self.assertEqual(r.cookies["tb_guest"].value, "")   # the guest choice ends at sign-in
                self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
                self.client.logout()

    def test_wrong_password(self):
        r = self.client.post(reverse("qda:welcome"), {"username": "amina", "password": "nope"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Please enter a correct username or email and password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_must_stay_on_this_site(self):
        for target in ("https://evil.example/", "//evil.example/", "/qda/welcome/?next=/qda/"):
            with self.subTest(target=target):
                r = self.client.post(reverse("qda:welcome"), {"username": "amina", "password": "research-2026", "next": target})
                self.assertRedirects(r, reverse("qda:dashboard"), fetch_redirect_response=False)
                self.client.logout()

    def test_signed_in_visitors_skip_the_sign_in_page(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("qda:welcome") + "?next=/qda/export/")
        self.assertRedirects(r, "/qda/export/", fetch_redirect_response=False)

    def test_sign_up_link_comes_back_to_the_tool(self):
        r = self.client.get(reverse("qda:welcome") + "?next=/qda/workspace/")
        self.assertContains(r, 'href="/accounts/signup/?next=%2Fqda%2Fworkspace%2F"')

    def test_old_addresses_redirect(self):
        r = self.client.get("/qda/workspace.html?source=src_1")
        self.assertRedirects(r, "/qda/workspace/?source=src_1", fetch_redirect_response=False)
        r = self.client.get("/qda/wordfrequency.html")
        self.assertRedirects(r, "/qda/clouds/", fetch_redirect_response=False)

    def test_account_page_counts_projects(self):
        Project.objects.create(owner=self.user, client_id="a", title="One")
        Project.objects.create(owner=self.user, client_id="b", title="Two", deleted=True)
        self.client.force_login(self.user)
        r = self.client.get(reverse("qda:account"))
        self.assertContains(r, "1 project in your account (1 in the trash)")
        self.assertContains(r, reverse("accounts:password_change"))
