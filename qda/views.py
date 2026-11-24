"""
Pages of the TakwimuBridge QDA tool.

The tool opens on its sign-in page (`welcome`). Anyone who is signed in, or
who chose "Continue without an account" in this browser session (a session
cookie, only when settings.QDA_ALLOW_GUESTS is on), can use the app pages;
everyone else is sent to the sign-in page first and brought back after.
The User Guide and About pages are open to all.

The pages themselves are mostly the original front-end: the analysis runs in
the browser (static/qda/js/), and static/qda/js/cloud.js syncs projects to
the account through qda/api.py.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.forms import StyledAuthenticationForm

from .models import Project

GUEST_COOKIE = "tb_guest"

# name -> (template, page title, subtitle). Order doesn't matter.
APP_PAGES = {
    "dashboard": (
        "Dashboard",
        "Your active project at a glance — coding progress, the themes emerging from your data, and the evidence behind them.",
    ),
    "projects": (
        "Projects",
        "One project per study. Create, switch, back up or restore — projects you work on while signed in are kept in your account.",
    ),
    "workspace": (
        "Coding Workspace",
        "Read each transcript once: select a passage, then tick every theme it speaks to — in every thematic analysis you're running — in one go.",
    ),
    "analysis": (
        "Theme Analysis",
        "Frequency, respondent coverage and weighted importance — at theme, sub-theme or code level. Every number links back to its quotations.",
    ),
    "clouds": (
        "Theme & Word Cloud",
        "The theme cloud sizes each theme by how often it was coded; the word cloud shows raw vocabulary. Words are not codes, and codes are not themes.",
    ),
    "export": (
        "Export",
        "Everything generates in your browser — nothing is uploaded anywhere to produce these files.",
    ),
    "account": (
        "My Account",
        "Who you're signed in as, where your projects are kept, and signing out of this computer.",
    ),
}
PUBLIC_PAGES = {
    "guide": ("Simple User Guide", "How the qualitative data analysis tool works — no statistics background required."),
    "about": ("About & Scope", "What TakwimuBridge QDA is, who built it, and where your data is kept."),
}


def can_use_app(request):
    if request.user.is_authenticated:
        return True
    return settings.QDA_ALLOW_GUESTS and request.COOKIES.get(GUEST_COOKIE) == "1"


def _safe_next(request, url):
    """`url` if it's a page on this site (and not the sign-in page), else the dashboard."""
    dashboard = reverse("qda:dashboard")
    if not url or url.startswith(reverse("qda:welcome")):
        return dashboard
    if url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return dashboard


def _config(request):
    """Settings for the front-end, embedded in every page as window.TB_CONFIG."""
    user = request.user
    return {
        "projectsApi": reverse("qda:api_projects"),
        "csrfToken": get_token(request),  # also sets the CSRF cookie the API calls need
        "user": (
            {"id": user.pk, "name": user.get_username(), "email": user.email}
            if user.is_authenticated
            else None
        ),
        "allowGuests": settings.QDA_ALLOW_GUESTS,
        "urls": {
            "dashboard": reverse("qda:dashboard"),
            "projects": reverse("qda:projects"),
            "workspace": reverse("qda:workspace"),
            "analysis": reverse("qda:analysis"),
            "clouds": reverse("qda:clouds"),
            "export": reverse("qda:export"),
            "account": reverse("qda:account"),
            "guide": reverse("qda:guide"),
            "about": reverse("qda:about"),
            "welcome": reverse("qda:welcome"),
            "signup": reverse("accounts:signup"),
            "logout": reverse("accounts:logout"),
            "passwordChange": reverse("accounts:password_change"),
            "site": reverse("core:home"),
        },
    }


def _render(request, name, title, subtitle, **extra):
    context = {"page": name, "page_title": title, "page_subtitle": subtitle, "qda_config": _config(request)}
    context.update(extra)
    return render(request, f"qda/{name}.html", context)


def _app_view(name):
    title, subtitle = APP_PAGES[name]

    def view(request):
        if not can_use_app(request):
            url = reverse("qda:welcome")
            here = request.get_full_path()
            if here != reverse("qda:dashboard"):
                url += "?" + urlencode({"next": here})
            return redirect(url)
        extra = {}
        if name == "account" and request.user.is_authenticated:
            projects = Project.objects.filter(owner=request.user)
            extra = {
                "projects_in_account": projects.filter(deleted=False).count(),
                "projects_in_trash": projects.filter(deleted=True).count(),
            }
        return _render(request, name, title, subtitle, **extra)

    view.__name__ = name
    return view


def _public_view(name):
    title, subtitle = PUBLIC_PAGES[name]

    def view(request):
        return _render(request, name, title, subtitle)

    view.__name__ = name
    return view


dashboard = _app_view("dashboard")
projects = _app_view("projects")
workspace = _app_view("workspace")
analysis = _app_view("analysis")
clouds = _app_view("clouds")
export = _app_view("export")
account = _app_view("account")
guide = _public_view("guide")
about = _public_view("about")


def welcome(request):
    """The tool's opening page: sign in, create an account, or (if allowed)
    continue without one."""
    next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
    if request.user.is_authenticated:
        return redirect(next_url)

    form = StyledAuthenticationForm(request)
    if request.method == "POST":
        if request.POST.get("action") == "guest" and settings.QDA_ALLOW_GUESTS:
            response = redirect(next_url)
            # A session cookie: the next visit opens on the sign-in page again.
            response.set_cookie(GUEST_COOKIE, "1", samesite="Lax", secure=request.is_secure(), httponly=True)
            return response
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            response = redirect(next_url)
            response.delete_cookie(GUEST_COOKIE, samesite="Lax")
            return response

    raw_next = request.POST.get("next") or request.GET.get("next") or ""
    signup = reverse("accounts:signup") + "?" + urlencode({"next": next_url})
    return render(
        request,
        "qda/welcome.html",
        {
            "page_title": "Sign in",
            "form": form,
            "next": next_url if raw_next else "",
            "signup_url": signup,
            "qda_config": _config(request),
            "email_ready": settings.EMAIL_CONFIGURED,
        },
    )
