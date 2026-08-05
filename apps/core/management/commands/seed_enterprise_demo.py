from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OrganizationMembership, User
from apps.core.demo_data.enterprise_hr import (
    ENTERPRISE_DEPARTMENTS,
    ENTERPRISE_EMPLOYEES,
    ENTERPRISE_POSITIONS,
    employee_employment_type,
    employee_permissions,
    employee_role,
)
from apps.core.demo_data.enterprise_recruitment import (
    ENTERPRISE_APPLICATION_TARGETS,
    ENTERPRISE_JOB_REQUISITIONS,
    STAGE_DISTRIBUTION,
    build_enterprise_candidates,
    requisition_deadline,
    requisition_target_date,
)
from apps.hr.models import (
    Employee,
    EmploymentAssignment,
    Position,
    Candidate,
    JobApplication,
    JobRequisition,
    RecruitmentEvent,
)
from apps.organizations.models import (
    Branch,
    Company,
    Department,
)

DEMO_COMPANY_NAME = "Glauria Demo A.Ş."
DEMO_BRANCH_CODE = "DMO-HQ"


class Command(BaseCommand):
    help = (
        "Glauria Demo A.Ş. verilerini kurumsal sunum veri setine "
        "genişletir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            default="ikra",
            help="Demo şirket sahibinin kullanıcı adı.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        owner_username = options["owner"].strip()

        try:
            owner = User.objects.get(username=owner_username)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"'{owner_username}' adlı kullanıcı bulunamadı."
            ) from exc

        # Hafif demo verisinin her zaman hazır olmasını garanti eder.
        call_command(
            "seed_demo",
            owner=owner_username,
            stdout=self.stdout,
        )

        company = Company.objects.get(
            name=DEMO_COMPANY_NAME,
        )

        branch = Branch.objects.get(
            company=company,
            code=DEMO_BRANCH_CODE,
        )

        subscription = company.subscription

        if subscription.member_limit < 50:
            subscription.member_limit = 50
            subscription.save(
                update_fields=[
                    "member_limit",
                    "updated_at",
                ]
            )

        departments = {
            department.code: department
            for department in Department.objects.filter(
                branch=branch,
            )
        }

        created_department_count = 0

        for department_data in ENTERPRISE_DEPARTMENTS:
            department, created = (
                Department.objects.update_or_create(
                    branch=branch,
                    code=department_data["code"],
                    defaults={
                        "name": department_data["name"],
                        "is_active": True,
                    },
                )
            )

            departments[department.code] = department

            if created:
                created_department_count += 1

        positions = {
            position.code: position
            for position in Position.objects.filter(
                company=company,
            )
        }

        created_position_count = 0

        for position_data in ENTERPRISE_POSITIONS:
            department = departments[
                position_data["department_code"]
            ]

            position, created = Position.objects.update_or_create(
                company=company,
                code=position_data["code"],
                defaults={
                    "department": department,
                    "title": position_data["title"],
                    "description": (
                        "Glauria Enterprise Demo organizasyon "
                        "pozisyonu."
                    ),
                    "is_active": True,
                },
            )

            positions[position.code] = position

            if created:
                created_position_count += 1

        users = {
            user.username: user
            for user in User.objects.filter(
                username__in=[
                    "demo.ceo",
                    "demo.hr.manager",
                    "demo.hr.specialist",
                    "demo.finance.manager",
                    "demo.purchasing.manager",
                    "demo.sales.manager",
                    "demo.operations.manager",
                ]
            )
        }

        employees = {
            employee.user.username: employee
            for employee in Employee.objects.filter(
                company=company,
                user__isnull=False,
            ).select_related("user")
        }

        created_user_count = 0
        created_membership_count = 0
        created_employee_count = 0
        created_assignment_count = 0

        # İlk tur: Kullanıcı, üyelik ve personel kartları.
        for employee_data in ENTERPRISE_EMPLOYEES:
            username = employee_data["username"]
            department = departments[
                employee_data["department_code"]
            ]

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": (
                        f"{username}@demo.glauria.local"
                    ),
                    "first_name": employee_data["first_name"],
                    "last_name": employee_data["last_name"],
                    "user_type": User.UserType.INTERNAL,
                },
            )

            user.email = f"{username}@demo.glauria.local"
            user.first_name = employee_data["first_name"]
            user.last_name = employee_data["last_name"]
            user.user_type = User.UserType.INTERNAL
            user.set_unusable_password()
            user.save()

            users[username] = user

            if user_created:
                created_user_count += 1

            membership, membership_created = (
                OrganizationMembership.objects.update_or_create(
                    user=user,
                    company=company,
                    defaults={
                        "branch": branch,
                        "department": department,
                        "job_title": employee_data["job_title"],
                        "role": employee_role(employee_data),
                        "permissions": employee_permissions(
                            employee_data
                        ),
                        "is_primary": True,
                        "is_active": True,
                    },
                )
            )

            if membership_created:
                created_membership_count += 1

            employee, employee_created = (
                Employee.objects.update_or_create(
                    company=company,
                    employee_number=(
                        employee_data["employee_number"]
                    ),
                    defaults={
                        "user": user,
                        "first_name": (
                            employee_data["first_name"]
                        ),
                        "last_name": employee_data["last_name"],
                        "work_email": user.email,
                        "hire_date": employee_data["hire_date"],
                        "employment_status": (
                            Employee.EmploymentStatus.ACTIVE
                        ),
                        "notes": (
                            "Glauria Enterprise Demo personeli."
                        ),
                        "is_active": True,
                    },
                )
            )

            employees[username] = employee

            if employee_created:
                created_employee_count += 1

        # İkinci tur: Yönetici ilişkileri kurulmuş atamalar.
        for employee_data in ENTERPRISE_EMPLOYEES:
            employee = employees[employee_data["username"]]
            department = departments[
                employee_data["department_code"]
            ]
            position = positions[
                employee_data["position_code"]
            ]
            manager = employees[
                employee_data["manager_username"]
            ]

            assignment, assignment_created = (
                EmploymentAssignment.objects.update_or_create(
                    employee=employee,
                    is_primary=True,
                    end_date__isnull=True,
                    defaults={
                        "branch": branch,
                        "department": department,
                        "position": position,
                        "manager": manager,
                        "employment_type": (
                            employee_employment_type(
                                employee_data
                            )
                        ),
                        "start_date": employee_data["hire_date"],
                        "is_department_manager": (
                            employee_data.get(
                                "is_department_manager",
                                False,
                            )
                        ),
                    },
                )
            )

            if assignment_created:
                created_assignment_count += 1


        # =====================================================
        # Enterprise Recruitment
        # =====================================================

        created_enterprise_candidate_count = 0
        created_enterprise_requisition_count = 0
        created_enterprise_application_count = 0
        created_enterprise_event_count = 0

        consent_at = timezone.make_aware(
            datetime(2026, 8, 5, 9, 0)
        )

        for candidate_data in build_enterprise_candidates():
            _, created = Candidate.objects.update_or_create(
                company=company,
                email=candidate_data["email"],
                defaults={
                    **candidate_data,
                    "consent_given": True,
                    "consent_at": consent_at,
                    "created_by": owner,
                },
            )

            if created:
                created_enterprise_candidate_count += 1

        for index, requisition_data in enumerate(
            ENTERPRISE_JOB_REQUISITIONS,
        ):
            department = departments[
                requisition_data["department"]
            ]
            position = positions[
                requisition_data["position"]
            ]
            hiring_manager = employees[
                requisition_data["manager"]
            ]
            recruiter = employees[
                requisition_data["recruiter"]
            ]

            _, created = JobRequisition.objects.update_or_create(
                company=company,
                requisition_number=requisition_data["number"],
                defaults={
                    "department": department,
                    "position": position,
                    "title": requisition_data["title"],
                    "description": (
                        f"{requisition_data['title']} pozisyonu için "
                        "kurumsal işe alım talebi."
                    ),
                    "requirements": (
                        "Pozisyonla ilgili mesleki deneyim, güçlü "
                        "iletişim ve ekip çalışması yetkinliği."
                    ),
                    "employment_type": (
                        requisition_data["employment_type"]
                    ),
                    "opening_reason": requisition_data["reason"],
                    "headcount": requisition_data["headcount"],
                    "filled_headcount": 0,
                    "hiring_manager": hiring_manager,
                    "recruiter": recruiter,
                    "status": JobRequisition.Status.OPEN,
                    "application_deadline": (
                        requisition_deadline(index)
                    ),
                    "target_start_date": (
                        requisition_target_date(index)
                    ),
                    "opened_at": timezone.make_aware(
                        datetime(2026, 8, 5, 10, 0)
                    ),
                    "closed_at": None,
                    "created_by": owner,
                },
            )

            if created:
                created_enterprise_requisition_count += 1

        all_candidates = list(
            Candidate.objects.filter(
                company=company,
            ).order_by("email")
        )

        all_requisitions = list(
            JobRequisition.objects.filter(
                company=company,
            ).order_by("requisition_number")
        )

        # =====================================================
        # İlan yoğunluğuna göre ağırlıklı başvuru dağılımı
        # =====================================================

        enterprise_source_note = (
            "Enterprise Demo ATS başvurusu."
        )

        removed_enterprise_application_count = 0

        enterprise_requisition_numbers = set(
            ENTERPRISE_APPLICATION_TARGETS
        )

        # Önceki eşit dağıtım algoritmasının hafif demo ilanlarına
        # eklediği enterprise başvuruları kaldır. Hafif seed_demo
        # başvuruları farklı source_note kullandığı için korunur.
        legacy_enterprise_applications = (
            JobApplication.objects.filter(
                company=company,
                source_note=enterprise_source_note,
            )
            .exclude(
                requisition__requisition_number__in=(
                    enterprise_requisition_numbers
                )
            )
        )

        legacy_application_count = (
            legacy_enterprise_applications.count()
        )

        if legacy_application_count:
            legacy_enterprise_applications.delete()
            removed_enterprise_application_count += (
                legacy_application_count
            )

        requisitions_by_number = {
            requisition.requisition_number: requisition
            for requisition in all_requisitions
        }

        # Daha önce eşit dağıtılmış olan enterprise başvuruların
        # ilan hedefini aşan bölümünü güvenli biçimde kaldır.
        for requisition_number, target_count in (
            ENTERPRISE_APPLICATION_TARGETS.items()
        ):
            requisition = requisitions_by_number[
                requisition_number
            ]

            enterprise_applications = list(
                JobApplication.objects.filter(
                    company=company,
                    requisition=requisition,
                    source_note=enterprise_source_note,
                ).order_by(
                    "applied_at",
                    "id",
                )
            )

            surplus_count = max(
                len(enterprise_applications) - target_count,
                0,
            )

            if surplus_count:
                surplus_ids = [
                    application.id
                    for application in enterprise_applications[
                        -surplus_count:
                    ]
                ]

                deleted_count, _ = (
                    JobApplication.objects.filter(
                        id__in=surplus_ids,
                    ).delete()
                )

                removed_enterprise_application_count += (
                    surplus_count
                )

        existing_pairs = set(
            JobApplication.objects.filter(
                company=company,
            ).values_list(
                "candidate_id",
                "requisition_id",
            )
        )

        application_sequence = (
            JobApplication.objects.filter(
                company=company,
            ).count()
        )

        stage_path = [
            JobApplication.Stage.APPLIED,
            JobApplication.Stage.SCREENING,
            JobApplication.Stage.PHONE_SCREEN,
            JobApplication.Stage.INTERVIEW,
            JobApplication.Stage.ASSESSMENT,
            JobApplication.Stage.OFFER,
        ]

        event_types = {
            JobApplication.Stage.SCREENING: (
                RecruitmentEvent
                .EventType
                .MOVED_TO_SCREENING
            ),
            JobApplication.Stage.PHONE_SCREEN: (
                RecruitmentEvent
                .EventType
                .MOVED_TO_PHONE_SCREEN
            ),
            JobApplication.Stage.INTERVIEW: (
                RecruitmentEvent
                .EventType
                .MOVED_TO_INTERVIEW
            ),
            JobApplication.Stage.ASSESSMENT: (
                RecruitmentEvent
                .EventType
                .MOVED_TO_ASSESSMENT
            ),
            JobApplication.Stage.OFFER: (
                RecruitmentEvent
                .EventType
                .MOVED_TO_OFFER
            ),
        }

        for requisition_index, (
            requisition_number,
            target_count,
        ) in enumerate(
            ENTERPRISE_APPLICATION_TARGETS.items()
        ):
            requisition = requisitions_by_number[
                requisition_number
            ]

            current_count = (
                JobApplication.objects.filter(
                    company=company,
                    requisition=requisition,
                ).count()
            )

            required_count = max(
                target_count - current_count,
                0,
            )

            candidate_offset = (
                requisition_index * 17
            ) % len(all_candidates)

            candidate_attempt = 0
            created_for_requisition = 0

            while created_for_requisition < required_count:
                if candidate_attempt >= len(all_candidates):
                    raise CommandError(
                        f"{requisition_number} için yeterli "
                        "benzersiz aday bulunamadı."
                    )

                candidate = all_candidates[
                    (
                        candidate_offset
                        + candidate_attempt
                    )
                    % len(all_candidates)
                ]

                candidate_attempt += 1

                pair = (
                    candidate.id,
                    requisition.id,
                )

                if pair in existing_pairs:
                    continue

                stage = STAGE_DISTRIBUTION[
                    (
                        application_sequence
                        + requisition_index * 3
                    )
                    % len(STAGE_DISTRIBUTION)
                ]

                status = JobApplication.Status.ACTIVE
                rejection_reason = ""
                withdrawn_reason = ""

                if stage == JobApplication.Stage.REJECTED:
                    status = JobApplication.Status.REJECTED
                    rejection_reason = (
                        "Pozisyonun öncelikli gereksinimleriyle "
                        "yeterli eşleşme sağlanamadı."
                    )
                elif stage == JobApplication.Stage.WITHDRAWN:
                    status = JobApplication.Status.WITHDRAWN
                    withdrawn_reason = (
                        "Aday kariyer planı nedeniyle başvuruyu "
                        "geri çekti."
                    )

                score = None

                if stage != JobApplication.Stage.APPLIED:
                    score = Decimal(
                        str(
                            55
                            + (
                                application_sequence * 11
                                + candidate_attempt * 3
                                + requisition_index * 5
                            )
                            % 44
                        )
                    )

                applied_at = timezone.make_aware(
                    datetime(2026, 7, 1, 9, 0)
                ) + timedelta(
                    days=application_sequence % 35,
                    hours=application_sequence % 8,
                )

                application = JobApplication.objects.create(
                    company=company,
                    candidate=candidate,
                    requisition=requisition,
                    stage=stage,
                    status=status,
                    applied_at=applied_at,
                    screening_score=score,
                    source_note=enterprise_source_note,
                    rejection_reason=rejection_reason,
                    withdrawn_reason=withdrawn_reason,
                    assigned_recruiter=requisition.recruiter,
                )

                existing_pairs.add(pair)
                created_for_requisition += 1
                created_enterprise_application_count += 1

                terminal_stage = stage in {
                    JobApplication.Stage.REJECTED,
                    JobApplication.Stage.WITHDRAWN,
                }

                if terminal_stage:
                    target_index = (
                        application_sequence
                        + requisition_index
                    ) % 3
                else:
                    target_index = (
                        stage_path.index(stage)
                        if stage in stage_path
                        else 0
                    )

                event_steps = [
                    {
                        "type": (
                            RecruitmentEvent
                            .EventType
                            .APPLICATION_CREATED
                        ),
                        "previous": "",
                        "new": JobApplication.Stage.APPLIED,
                        "previous_status": "",
                        "new_status": (
                            JobApplication.Status.ACTIVE
                        ),
                    }
                ]

                for path_index in range(
                    1,
                    target_index + 1,
                ):
                    event_steps.append(
                        {
                            "type": event_types[
                                stage_path[path_index]
                            ],
                            "previous": stage_path[
                                path_index - 1
                            ],
                            "new": stage_path[path_index],
                            "previous_status": (
                                JobApplication.Status.ACTIVE
                            ),
                            "new_status": (
                                JobApplication.Status.ACTIVE
                            ),
                        }
                    )

                if terminal_stage:
                    previous_stage = stage_path[
                        target_index
                    ]

                    event_steps.append(
                        {
                            "type": (
                                RecruitmentEvent
                                .EventType
                                .REJECTED
                                if stage
                                == JobApplication.Stage.REJECTED
                                else RecruitmentEvent
                                .EventType
                                .WITHDRAWN
                            ),
                            "previous": previous_stage,
                            "new": stage,
                            "previous_status": (
                                JobApplication.Status.ACTIVE
                            ),
                            "new_status": status,
                        }
                    )

                for event_index, event_data in enumerate(
                    event_steps
                ):
                    RecruitmentEvent.objects.create(
                        application=application,
                        company=company,
                        event_type=event_data["type"],
                        previous_stage=event_data["previous"],
                        new_stage=event_data["new"],
                        previous_status=(
                            event_data["previous_status"]
                        ),
                        new_status=event_data["new_status"],
                        changed_by=owner,
                        note=(
                            "Enterprise Demo ATS işlem geçmişi."
                        ),
                        occurred_at=(
                            applied_at
                            + timedelta(days=event_index)
                        ),
                    )

                    created_enterprise_event_count += 1

                application_sequence += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Enterprise demo organizasyonu hazırlandı."
            )
        )
        self.stdout.write(
            f"Yeni departman sayısı: {created_department_count}"
        )
        self.stdout.write(
            f"Yeni pozisyon sayısı: {created_position_count}"
        )
        self.stdout.write(
            f"Yeni enterprise kullanıcı sayısı: {created_user_count}"
        )
        self.stdout.write(
            "Yeni enterprise üyelik sayısı: "
            f"{created_membership_count}"
        )
        self.stdout.write(
            "Yeni enterprise personel sayısı: "
            f"{created_employee_count}"
        )
        self.stdout.write(
            "Yeni enterprise atama sayısı: "
            f"{created_assignment_count}"
        )
        self.stdout.write(
            "Yeni enterprise aday sayısı: "
            f"{created_enterprise_candidate_count}"
        )
        self.stdout.write(
            "Yeni enterprise işe alım talebi sayısı: "
            f"{created_enterprise_requisition_count}"
        )
        self.stdout.write(
            "Yeni enterprise başvuru sayısı: "
            f"{created_enterprise_application_count}"
        )
        self.stdout.write(
            "Yeniden dağıtımda kaldırılan başvuru sayısı: "
            f"{removed_enterprise_application_count}"
        )
        self.stdout.write(
            "Yeni enterprise işe alım event sayısı: "
            f"{created_enterprise_event_count}"
        )
        self.stdout.write("")
        self.stdout.write(
            f"Toplam departman: "
            f"{Department.objects.filter(branch=branch).count()}"
        )
        self.stdout.write(
            f"Toplam pozisyon: "
            f"{Position.objects.filter(company=company).count()}"
        )
        self.stdout.write(
            f"Toplam personel: "
            f"{Employee.objects.filter(company=company).count()}"
        )

        self.stdout.write(
            f"Toplam aday: "
            f"{Candidate.objects.filter(company=company).count()}"
        )
        self.stdout.write(
            f"Toplam işe alım talebi: "
            f"{JobRequisition.objects.filter(company=company).count()}"
        )
        self.stdout.write(
            f"Toplam başvuru: "
            f"{JobApplication.objects.filter(company=company).count()}"
        )
