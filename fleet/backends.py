from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class RoleBasedBackend(ModelBackend):
    """
    Extends Django's standard ModelBackend.
    If the login form includes a 'role' field (from the role-selector tabs),
    authentication fails when the selected role doesn't match the user's actual role.
    This enforces tab-level role gating without exposing error details.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user and request:
            selected_role = request.POST.get('role')
            # Only reject if a role was explicitly selected AND it mismatches
            if selected_role and user.role != selected_role:
                return None
        return user
