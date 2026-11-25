import re

from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class SignInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amina", "Amina@Example.org", "research-2026")

    def test_username_or_email(self):
        self.assertEqual(authenticate(username="amina", password="research-2026"), self.user)
        self.assertEqual(authenticate(username=" amina@example.org ", password="research-2026"), self.user)
        self.assertIsNone(authenticate(username="amina@example.org", password="wrong"))
        self.assertIsNone(authenticate(username="nobody@example.org", password="research-2026"))

    def test_shared_email_picks_the_account_by_password(self):
        other = User.objects.create_user("amina2", "amina@example.org", "another-pass-2026")
        self.assertEqual(authenticate(username="amina@example.org", password="another-pass-2026"), other)
        self.assertEqual(authenticate(username="amina@example.org", password="research-2026"), self.user)

    def test_inactive_accounts_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(authenticate(username="amina@example.org", password="research-2026"))

    def test_site_login_page_accepts_email(self):
        r = self.client.post(reverse("accounts:login"), {"username": "amina@example.org", "password": "research-2026", "next": "/qda/"})
        self.assertRedirects(r, "/qda/", fetch_redirect_response=False)


class SignUpTests(TestCase):
    def form(self, **extra):
        data = {"username": "neema", "email": "neema@example.org", "institution": "UDSM",
                "password1": "neema-pass-2026", "password2": "neema-pass-2026"}
        data.update(extra)
        return data

    def test_sign_up_and_go_back_to_the_tool(self):
        r = self.client.post(reverse("accounts:signup"), self.form(next="/qda/workspace/"))
        self.assertRedirects(r, "/qda/workspace/", fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="neema").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_unsafe_next_is_ignored(self):
        r = self.client.post(reverse("accounts:signup"), self.form(next="https://evil.example/"))
        self.assertRedirects(r, reverse("datasets:catalog"), fetch_redirect_response=False)

    def test_next_is_carried_through_the_form(self):
        r = self.client.get(reverse("accounts:signup") + "?next=/qda/")
        self.assertContains(r, 'name="next" value="/qda/"')

    def test_email_must_be_new(self):
        User.objects.create_user("someone", "Neema@Example.org", "x-pass-2026-long")
        r = self.client.post(reverse("accounts:signup"), self.form())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "An account with this email already exists")
        self.assertFalse(User.objects.filter(username="neema").exists())


class PasswordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amina", "amina@example.org", "research-2026")

    def test_change_password(self):
        self.assertEqual(self.client.get(reverse("accounts:password_change")).status_code, 302)  # sign in first
        self.client.force_login(self.user)
        r = self.client.post(reverse("accounts:password_change"), {
            "old_password": "research-2026", "new_password1": "fresh-pass-2026", "new_password2": "fresh-pass-2026"})
        self.assertRedirects(r, reverse("accounts:password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("fresh-pass-2026"))
        self.assertIn("_auth_user_id", self.client.session)           # still signed in

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_by_email(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "AMINA@example.org"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"https?://\S+/accounts/password/reset/\S+/\S+/", mail.outbox[0].body).group(0)
        path = "/" + link.split("/", 3)[3]
        r = self.client.get(path, follow=True)                         # Django swaps the token into the session
        self.assertContains(r, "Choose a New Password")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "reset-pass-2026", "new_password2": "reset-pass-2026"})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("reset-pass-2026"))
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_link_shows_when_email_works(self):
        with self.settings(EMAIL_CONFIGURED=True):
            self.assertContains(self.client.get(reverse("accounts:login")), reverse("accounts:password_reset"))
        with self.settings(EMAIL_CONFIGURED=False):
            self.assertNotContains(self.client.get(reverse("accounts:login")), reverse("accounts:password_reset"))
