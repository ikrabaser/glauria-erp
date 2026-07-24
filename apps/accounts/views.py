from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def login_redirect(request):
    if request.user.user_type == request.user.UserType.PORTAL:
        return redirect("portal:home")

    return redirect("dashboard:home")