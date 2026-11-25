from django.conf import settings


def account_features(request):
    """Lets templates hide "Forgot password?" until outgoing email is set up."""
    return {"email_ready": settings.EMAIL_CONFIGURED}
