from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CustomerForm
from .models import Customer


def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


@login_required
def home(request):
    membership = get_active_membership(request.user)

    if membership:
        customers = (
            Customer.objects
            .select_related("company", "created_by")
            .filter(company=membership.company)
        )
    else:
        customers = Customer.objects.none()

    return render(
        request,
        "crm/home.html",
        {
            "customers": customers,
            "current_membership": membership,
        },
    )


@login_required
def customer_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("crm:home")

    if request.method == "POST":
        form = CustomerForm(request.POST)

        if form.is_valid():
            customer = form.save(commit=False)
            customer.company = membership.company
            customer.created_by = request.user
            customer.save()

            return redirect("crm:home")
    else:
        form = CustomerForm(
            initial={"status": Customer.Status.LEAD}
        )

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "current_membership": membership,
        },
    )