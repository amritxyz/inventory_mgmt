from django.contrib.auth.models import User

def admin_context(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return {
            'pending_user_count': User.objects.filter(is_active=False).count()
        }
    return {'pending_user_count': 0}
