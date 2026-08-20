import os

from django import forms

from .models import ALLOWED_DATASET_EXTENSIONS, MAX_DATASET_FILE_SIZE, Dataset


class DatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ["title", "category", "description", "region", "year", "file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-select" if name == "category" else "form-control"
            field.widget.attrs.setdefault("class", css)

    def clean_file(self):
        file = self.cleaned_data["file"]
        ext = os.path.splitext(file.name)[1].lstrip(".").lower()
        if ext not in ALLOWED_DATASET_EXTENSIONS:
            allowed = ", ".join(ALLOWED_DATASET_EXTENSIONS)
            raise forms.ValidationError(f"Unsupported file type. Allowed: {allowed}.")
        if file.size > MAX_DATASET_FILE_SIZE:
            raise forms.ValidationError("File is too large. Maximum size is 20MB.")
        return file
