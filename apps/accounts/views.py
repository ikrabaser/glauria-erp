from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import ProfileForm


@login_required
def login_redirect(request):
    if request.user.user_type == request.user.UserType.PORTAL:
        return redirect("portal:home")

    return redirect("dashboard:home")


@login_required
def profile_settings(request):
    membership = (
        request.user.organization_memberships
        .select_related("company", "branch", "department")
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )

    profile_form = ProfileForm(instance=request.user)
    password_form = PasswordChangeForm(user=request.user)

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "profile":
            profile_form = ProfileForm(
                request.POST,
                instance=request.user,
            )

            if profile_form.is_valid():
                profile_form.save()

                return redirect(
                    f"{reverse('accounts:profile')}?updated=profile"
                )

        elif form_type == "password":
            password_form = PasswordChangeForm(
                user=request.user,
                data=request.POST,
            )

            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)

                return redirect(
                    f"{reverse('accounts:profile')}?updated=password"
                )

    return render(
        request,
        "accounts/profile_settings.html",
        {
            "profile_form": profile_form,
            "password_form": password_form,
            "membership": membership,
        },
    )