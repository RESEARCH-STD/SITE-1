from django.db import models
from django.utils.text import slugify


class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class DataCustodian(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SiteStat(models.Model):
    label = models.CharField(max_length=100, help_text="e.g. \"Projects\", \"Partners\"")
    value = models.CharField(max_length=50, help_text="e.g. \"20+\", \"3,000+\"")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.value} {self.label}"


class Project(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    date_range = models.CharField(max_length=100, blank=True, help_text="e.g. \"2025 – Ongoing\"")
    summary = models.TextField()
    image = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path under static/, e.g. images/projects/example.jpg",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "-id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:270]
            slug = base_slug
            n = 1
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base_slug}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Partner(models.Model):
    name = models.CharField(max_length=255)
    logo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path under static/, e.g. images/partners/example.svg",
    )
    url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Insight(models.Model):
    CATEGORY_NEWS = "news"
    CATEGORY_PUBLICATION = "publication"
    CATEGORY_EVENT = "event"
    CATEGORY_CAREER = "career"
    CATEGORY_STARTUP = "startup"
    CATEGORY_CONFERENCE = "conference"
    CATEGORY_CHOICES = [
        (CATEGORY_NEWS, "Latest News"),
        (CATEGORY_PUBLICATION, "Publications"),
        (CATEGORY_EVENT, "Events"),
        (CATEGORY_CAREER, "Career Opportunities"),
        (CATEGORY_STARTUP, "Startup Competitions"),
        (CATEGORY_CONFERENCE, "International Conferences"),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    image = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path under static/, e.g. images/insights/example.jpg",
    )
    published_at = models.DateField()
    link = models.URLField(blank=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"
