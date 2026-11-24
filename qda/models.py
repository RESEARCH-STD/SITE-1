"""
TakwimuBridge QDA: the server copy of each researcher's qualitative projects.

The browser keeps the working copy of a project (static/qda/js/app.js) and
uploads the whole project document after each change (qda/api.py). That
document is stored here as rows, one per analysis, source (transcript),
theme and coded reference, so the admin can browse who coded what.
qda/sync.py converts a document to rows and back.

Each row keeps its item exactly as the browser sent it in `data` (minus the
id, and minus a source's transcript text, which has its own column), so a
project always comes back unchanged. The other columns are copied out of
`data` on every write, for the admin and for queries; nothing edits them
directly.
"""

from django.conf import settings
from django.db import models


class Project(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="qda_projects"
    )
    # The id the browser gave the project (e.g. "proj_m1x2y3_ab12cd"). Every
    # browser seeds the same demo project id, so ids are unique per owner only.
    client_id = models.CharField(max_length=100)
    data = models.JSONField(
        default=dict, blank=True, help_text="Project fields as stored by the app (title, researcher, memo, …)."
    )

    # Copied from `data` for the admin.
    title = models.CharField(max_length=300, blank=True)
    researcher = models.CharField(max_length=300, blank=True)
    organization = models.CharField(max_length=300, blank=True)
    topic = models.CharField(max_length=300, blank=True)

    # Sync bookkeeping (see qda/api.py). `revision` goes up by one on every
    # accepted change; an upload must say which revision it was based on.
    revision = models.PositiveIntegerField(default=0)
    deleted = models.BooleanField(default=False, help_text="In the trash: hidden from the app, kept here.")
    deleted_at = models.DateTimeField(null=True, blank=True)
    # Lets a browser safely resend an upload whose answer it never received.
    last_writer = models.CharField(max_length=64, blank=True)
    last_write_base = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "client_id"], name="qda_project_unique_per_owner"),
        ]

    def __str__(self):
        return self.title or self.client_id


class ProjectItem(models.Model):
    """One entry from a project's analyses / sources / themes / codings list."""

    client_id = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True
        ordering = ["position"]


class Analysis(ProjectItem):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="analyses")
    name = models.CharField(max_length=300, blank=True)
    question = models.TextField(blank=True)

    class Meta(ProjectItem.Meta):
        verbose_name_plural = "analyses"
        constraints = [
            models.UniqueConstraint(fields=["project", "client_id"], name="qda_analysis_unique_in_project"),
        ]

    def __str__(self):
        return self.name or self.client_id


class Source(ProjectItem):
    """A transcript or other text: a KII, FGD, interview or survey response."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=40, blank=True)
    name = models.CharField(max_length=300, blank=True)
    respondent_id = models.CharField(max_length=200, blank=True)
    text = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(default=0)

    class Meta(ProjectItem.Meta):
        constraints = [
            models.UniqueConstraint(fields=["project", "client_id"], name="qda_source_unique_in_project"),
        ]

    def __str__(self):
        return self.name or self.client_id


class Theme(ProjectItem):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="themes")
    name = models.CharField(max_length=300, blank=True)
    color = models.CharField(max_length=20, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    # Set on top-level themes only; sub-themes belong to their top theme's analysis.
    analysis = models.ForeignKey(
        Analysis, null=True, blank=True, on_delete=models.SET_NULL, related_name="themes"
    )

    class Meta(ProjectItem.Meta):
        constraints = [
            models.UniqueConstraint(fields=["project", "client_id"], name="qda_theme_unique_in_project"),
        ]

    def __str__(self):
        return self.name or self.client_id

    def path(self, max_depth=12):
        """Names from the top-level theme down to this one."""
        names, node, seen = [], self, set()
        while node is not None and node.pk not in seen and len(names) < max_depth:
            seen.add(node.pk)
            names.append(node.name or node.client_id)
            node = node.parent
        return " › ".join(reversed(names))

    def top_level(self, max_depth=12):
        node, seen = self, set()
        while node.parent_id and node.pk not in seen and len(seen) < max_depth:
            seen.add(node.pk)
            node = node.parent
        return node


class Coding(ProjectItem):
    """A coded reference: a passage of a source tagged with one or more themes."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="codings")
    source = models.ForeignKey(
        Source, null=True, blank=True, on_delete=models.CASCADE, related_name="codings"
    )
    speaker_id = models.CharField(max_length=100, blank=True)
    start = models.PositiveIntegerField(default=0)
    end = models.PositiveIntegerField(default=0)
    quote = models.TextField(blank=True)
    weight = models.PositiveSmallIntegerField(null=True, blank=True)
    themes = models.ManyToManyField(Theme, through="CodingTheme", related_name="codings", blank=True)

    class Meta(ProjectItem.Meta):
        verbose_name = "coded reference"
        constraints = [
            models.UniqueConstraint(fields=["project", "client_id"], name="qda_coding_unique_in_project"),
        ]

    def __str__(self):
        quote = " ".join((self.quote or "").split())
        return (quote[:77] + "…") if len(quote) > 80 else (quote or self.client_id)


class CodingTheme(models.Model):
    coding = models.ForeignKey(Coding, on_delete=models.CASCADE)
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["coding", "theme"], name="qda_coding_theme_unique"),
        ]
