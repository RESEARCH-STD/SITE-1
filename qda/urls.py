from django.urls import path
from django.views.generic import RedirectView

from . import api, views

app_name = "qda"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("welcome/", views.welcome, name="welcome"),
    path("projects/", views.projects, name="projects"),
    path("workspace/", views.workspace, name="workspace"),
    path("analysis/", views.analysis, name="analysis"),
    path("clouds/", views.clouds, name="clouds"),
    path("export/", views.export, name="export"),
    path("account/", views.account, name="account"),
    path("guide/", views.guide, name="guide"),
    path("about/", views.about, name="about"),
    path("api/projects/", api.project_list, name="api_projects"),
    path("api/projects/<str:client_id>/", api.project_detail, name="api_project"),
]

# Addresses from the earlier static version of the tool (e.g. a bookmarked
# workspace.html) lead to the same page here.
_OLD_PAGES = {
    "index": "dashboard", "projects": "projects", "workspace": "workspace", "analysis": "analysis",
    "wordfrequency": "clouds", "export": "export", "account": "account", "guide": "guide",
    "about": "about", "welcome": "welcome",
}
urlpatterns += [
    path(f"{old}.html", RedirectView.as_view(pattern_name=f"qda:{new}", query_string=True, permanent=False))
    for old, new in _OLD_PAGES.items()
]
