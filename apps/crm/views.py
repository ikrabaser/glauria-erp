from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
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

    query = request.GET.get("q", "").strip()
    selected_customer_type = request.GET.get("customer_type", "")
    selected_status = request.GET.get("status", "")

    if membership:
        customers = (
            Customer.objects
            .select_related("company", "created_by")
            .filter(company=membership.company)
        )

        if query:
            customers = customers.filter(
                Q(name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone__icontains=query)
                | Q(city__icontains=query)
            )

        if selected_customer_type in Customer.CustomerType.values:
            customers = customers.filter(
                customer_type=selected_customer_type
            )

        if selected_status in Customer.Status.values:
            customers = customers.filter(status=selected_status)
    else:
        customers = Customer.objects.none()

    return render(
        request,
        "crm/home.html",
        {
            "customers": customers,
            "current_membership": membership,
            "query": query,
            "selected_customer_type": selected_customer_type,
            "selected_status": selected_status,
            "customer_type_choices": Customer.CustomerType.choices,
            "status_choices": Customer.Status.choices,
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
@login_required
def customer_detail(request, customer_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("crm:home")

    customer = get_object_or_404(
        Customer.objects.select_related("company", "created_by"),
        id=customer_id,
        company=membership.company,
    )

    return render(
        request,
        "crm/customer_detail.html",
        {
            "customer": customer,
            "current_membership": membership,
        },
    )