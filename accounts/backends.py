from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Sign in with either the username or the account's email address.

    Usernames work exactly as before (and are tried first, since a username
    may itself contain "@"). Emails match case-insensitively; if older
    accounts share an email, the password decides which one it is.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        username = username.strip()
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None or "@" not in username:
            return user
        for candidate in UserModel._default_manager.filter(email__iexact=username).order_by("pk"):
            if candidate.check_password(password) and self.user_can_authenticate(candidate):
                return candidate
        return None
