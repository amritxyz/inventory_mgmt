from django.shortcuts import redirect
from django.urls import reverse

class DashboardLoginRequiredMiddleware:
    """
    Middleware that ensures any request to /dashboard/* requires authentication.
    If an unauthenticated user accesses /dashboard/*, redirect to login page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/dashboard') and not request.user.is_authenticated:
            login_url = reverse('login')
            return redirect(f"{login_url}?next={request.get_full_path()}")
        return self.get_response(request)
