from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import HttpResponseForbidden

from .forms import ProfileForm
from .models import OrganizationMembership

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
@login_required
def workspace_members(request):
    current_membership = (
        request.user.organization_memberships
        .select_related("company")
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )

    if not current_membership:
        return redirect("dashboard:home")

    allowed_roles = {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }

    if current_membership.role not in allowed_roles:
        return HttpResponseForbidden(
            "Bu sayfayı görüntüleme yetkiniz bulunmuyor."
        )

    memberships = (
        OrganizationMembership.objects
        .select_related(
            "user",
            "company",
            "branch",
            "department",
        )
        .filter(company=current_membership.company)
        .order_by(
            "-is_active",
            "role",
            "user__first_name",
            "user__username",
        )
    )

    return render(
        request,
        "accounts/workspace_members.html",
        {
            "memberships": memberships,
            "current_membership": current_membership,
        },
    )