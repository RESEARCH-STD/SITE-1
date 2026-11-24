from django.contrib.auth import login
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView

from .forms import SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("datasets:catalog")

    def _next(self):
        """Where to go after signing up, if a safe address was passed (e.g. by the QDA tool)."""
        url = self.request.POST.get("next") or self.request.GET.get("next") or ""
        if url and url_has_allowed_host_and_scheme(
            url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            return url
        return ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self._next()
        return context

    def get_success_url(self):
        return self._next() or super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object, backend="accounts.backends.EmailOrUsernameBackend")
        return response
