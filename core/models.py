from django.db import models


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
