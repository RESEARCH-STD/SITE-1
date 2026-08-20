from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path under static/, e.g. images/categories/education.svg",
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


ALLOWED_DATASET_EXTENSIONS = ["csv", "xlsx", "xls", "json", "dta", "sav", "zip", "pdf"]
MAX_DATASET_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class Dataset(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="datasets"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="datasets"
    )
    description = models.TextField()
    region = models.CharField(max_length=255, blank=True)
    year = models.CharField(max_length=50, blank=True)
    file = models.FileField(upload_to="datasets/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:260]
            slug = base_slug
            n = 1
            while Dataset.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base_slug}-{n}"
            self.slug = slug
        if self.file and not self.file._committed:
            # Only a freshly-uploaded, not-yet-stored file is cheap/safe to
            # inspect here (.size/.name read the local upload directly). A
            # file that's already committed to storage (e.g. editing a
            # dataset's metadata without changing the file, or a remote
            # storage backend like Cloudinary) would require a network
            # round-trip instead, so leave the previously-stored values as-is.
            self.original_filename = self.file.name
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("datasets:detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title
