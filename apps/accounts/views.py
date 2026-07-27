from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST


from .forms import ProfileForm, WorkspaceMemberCreateForm
from apps.organizations.models import CompanySubscription
from .models import OrganizationMembership, User

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
    member_form = WorkspaceMemberCreateForm(
        company=current_membership.company,
    )

    return render(
        request,
        "accounts/workspace_members.html",
        {
            "memberships": memberships,
            "current_membership": current_membership,
            "member_form": member_form,
        },
    )

@login_required
@require_POST
def workspace_member_create(request):
    current_membership = (
        request.user.organization_memberships
        .select_related("company")
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )

    if not current_membership:
        return redirect("dashboard:home")

    if current_membership.role not in {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }:
        return HttpResponseForbidden(
            "Bu işlem için yetkiniz bulunmuyor."
        )

    subscription = (
        CompanySubscription.objects
        .filter(company=current_membership.company)
        .first()
    )

    active_member_count = (
        current_membership.company.memberships
        .filter(is_active=True)
        .count()
    )

    if (
        subscription
        and active_member_count >= subscription.member_limit
    ):
        return HttpResponseBadRequest(
            "Çalışma alanı üye limitine ulaşıldı."
        )

    form = WorkspaceMemberCreateForm(
        request.POST,
        company=current_membership.company,
    )

    if not form.is_valid():
        return redirect("accounts:workspace_members")

    selected_role = form.cleaned_data["role"]

    if (
        current_membership.role == OrganizationMembership.Role.ADMIN
        and selected_role in {
            OrganizationMembership.Role.OWNER,
            OrganizationMembership.Role.ADMIN,
        }
    ):
        return HttpResponseForbidden(
            "Yöneticiler Sahip veya Yönetici rolüyle üye ekleyemez."
        )

    user = form.save(commit=False)
    user.user_type = User.UserType.INTERNAL
    user.save()

    OrganizationMembership.objects.create(
        user=user,
        company=current_membership.company,
        branch=form.cleaned_data["branch"],
        department=form.cleaned_data["department"],
        role=selected_role,
        job_title=form.cleaned_data["job_title"],
        is_primary=True,
        is_active=True,
    )

    return redirect("accounts:workspace_members")
@login_required
@require_POST
def workspace_member_access_update(request, membership_id):
    current_membership = (
        request.user.organization_memberships
        .select_related("company")
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )

    if not current_membership:
        return redirect("dashboard:home")

    if current_membership.role not in {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }:
        return HttpResponseForbidden(
            "Bu işlem için yetkiniz bulunmuyor."
        )

    target_membership = get_object_or_404(
        OrganizationMembership,
        id=membership_id,
        company=current_membership.company,
    )

    if target_membership.id == current_membership.id:
        return HttpResponseBadRequest(
            "Kendi rolünüzü veya üyelik durumunuzu bu ekrandan değiştiremezsiniz."
        )

    if (
        current_membership.role == OrganizationMembership.Role.ADMIN
        and target_membership.role in {
            OrganizationMembership.Role.OWNER,
            OrganizationMembership.Role.ADMIN,
        }
    ):
        return HttpResponseForbidden(
            "Yöneticiler Sahip veya diğer Yönetici rollerini değiştiremez."
        )

    selected_role = request.POST.get("role")
    is_active = request.POST.get("is_active") == "on"

    allowed_roles = {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
        OrganizationMembership.Role.MANAGER,
        OrganizationMembership.Role.MEMBER,
        OrganizationMembership.Role.VIEWER,
    }

    if selected_role not in allowed_roles:
        return HttpResponseBadRequest("Geçersiz rol seçimi.")

    if (
        current_membership.role == OrganizationMembership.Role.ADMIN
        and selected_role in {
            OrganizationMembership.Role.OWNER,
            OrganizationMembership.Role.ADMIN,
        }
    ):
        return HttpResponseForbidden(
            "Yöneticiler Sahip veya Yönetici rolü atayamaz."
        )

    target_membership.role = selected_role
    target_membership.is_active = is_active
    target_membership.save(
        update_fields=["role", "is_active", "updated_at"]
    )

    return redirect("accounts:workspace_members")