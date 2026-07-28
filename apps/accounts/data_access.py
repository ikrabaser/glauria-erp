from .models import OrganizationMembership


def has_full_company_data_access(membership):
    return membership.role in {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }


def filter_company_records(
    queryset,
    membership,
    ownership_field,
):
    scoped_queryset = queryset.filter(
        company=membership.company,
    )

    if has_full_company_data_access(membership):
        return scoped_queryset

    return scoped_queryset.filter(
        **{
            ownership_field: membership.user,
        }
    )