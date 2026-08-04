from datetime import date, datetime, time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OrganizationMembership, User
from apps.hr.models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    AbsenceType,
    AttendanceRecord,
    AttendanceRecordEvent,
    Employee,
    EmployeeScheduleAssignment,
    EmploymentAssignment,
    Position,
    WorkSchedule,
    WorkScheduleDay,
    EmployeeGoal,
    PerformanceReview,
    PerformanceReviewCycle,
    PerformanceReviewEvent,
)
from apps.hr.services import (
    approve_attendance_record,
    clock_in_attendance,
    clock_out_attendance,
    generate_attendance_record,
    submit_attendance_record,
)
from apps.finance.models import (
    FinanceBudget,
    FinanceBudgetAccount,
    FinanceBudgetLine,
    FinancialAccount,
    FinancialAccountTransaction,
)
from apps.organizations.models import (
    Branch,
    Company,
    CompanySubscription,
    Department,
)
from apps.purchasing.models import (
    PurchaseRequest,
    PurchaseRequestLine,
    Supplier,
)


DEMO_COMPANY_NAME = "Glauria Demo A.Ş."
DEMO_BRANCH_CODE = "DMO-HQ"

DEMO_DEPARTMENTS = [
    ("EXEC", "Yönetim"),
    ("FIN", "Finans ve Muhasebe"),
    ("PUR", "Satın Alma"),
    ("HR", "İnsan Kaynakları"),
    ("SAL", "Satış Yönetimi"),
    ("OPS", "Operasyon"),
]

DEMO_BUDGET_ACCOUNTS = [
    (
        "GEL-SATIS",
        "Ürün ve Hizmet Satışları",
        FinanceBudgetAccount.AccountType.REVENUE,
        "Ürün ve hizmet satışlarından beklenen nakit girişleri.",
    ),
    (
        "GEL-DANISMANLIK",
        "Danışmanlık Gelirleri",
        FinanceBudgetAccount.AccountType.REVENUE,
        "Danışmanlık ve proje hizmetlerinden beklenen gelirler.",
    ),
    (
        "GID-PAZARLAMA",
        "Pazarlama Giderleri",
        FinanceBudgetAccount.AccountType.EXPENSE,
        "Dijital reklam, kampanya ve marka iletişimi harcamaları.",
    ),
    (
        "GID-PERSONEL",
        "Personel Giderleri",
        FinanceBudgetAccount.AccountType.EXPENSE,
        "Ücret, yan hak ve insan kaynakları maliyetleri.",
    ),
    (
        "GID-OPERASYON",
        "Operasyon Giderleri",
        FinanceBudgetAccount.AccountType.EXPENSE,
        "Ofis, yazılım, lojistik ve günlük operasyon harcamaları.",
    ),
]

DEMO_BUDGET_LINES = [
    (
        date(2026, 8, 1),
        "GEL-SATIS",
        "Ağustos ürün ve hizmet satış hedefi",
        Decimal("125000.00"),
        Decimal("0.00"),
        "Demo satış hedefi",
    ),
    (
        date(2026, 8, 1),
        "GEL-DANISMANLIK",
        "Ağustos danışmanlık gelir hedefi",
        Decimal("35000.00"),
        Decimal("0.00"),
        "Demo danışmanlık hedefi",
    ),
    (
        date(2026, 8, 1),
        "GID-PAZARLAMA",
        "Ağustos pazarlama bütçesi",
        Decimal("0.00"),
        Decimal("25000.00"),
        "Dijital reklam ve kampanya",
    ),
    (
        date(2026, 8, 1),
        "GID-PERSONEL",
        "Ağustos personel bütçesi",
        Decimal("0.00"),
        Decimal("65000.00"),
        "Ücret ve yan haklar",
    ),
    (
        date(2026, 8, 1),
        "GID-OPERASYON",
        "Ağustos operasyon bütçesi",
        Decimal("0.00"),
        Decimal("30000.00"),
        "Ofis ve yazılım giderleri",
    ),
    (
        date(2026, 9, 1),
        "GEL-SATIS",
        "Eylül ürün ve hizmet satış hedefi",
        Decimal("140000.00"),
        Decimal("0.00"),
        "Demo satış hedefi",
    ),
    (
        date(2026, 9, 1),
        "GEL-DANISMANLIK",
        "Eylül danışmanlık gelir hedefi",
        Decimal("40000.00"),
        Decimal("0.00"),
        "Demo danışmanlık hedefi",
    ),
    (
        date(2026, 9, 1),
        "GID-PAZARLAMA",
        "Eylül pazarlama bütçesi",
        Decimal("0.00"),
        Decimal("30000.00"),
        "Dijital reklam ve kampanya",
    ),
    (
        date(2026, 9, 1),
        "GID-PERSONEL",
        "Eylül personel bütçesi",
        Decimal("0.00"),
        Decimal("65000.00"),
        "Ücret ve yan haklar",
    ),
    (
        date(2026, 9, 1),
        "GID-OPERASYON",
        "Eylül operasyon bütçesi",
        Decimal("0.00"),
        Decimal("35000.00"),
        "Ofis ve yazılım giderleri",
    ),
    (
        date(2026, 10, 1),
        "GEL-SATIS",
        "Ekim ürün ve hizmet satış hedefi",
        Decimal("155000.00"),
        Decimal("0.00"),
        "Demo satış hedefi",
    ),
    (
        date(2026, 10, 1),
        "GEL-DANISMANLIK",
        "Ekim danışmanlık gelir hedefi",
        Decimal("45000.00"),
        Decimal("0.00"),
        "Demo danışmanlık hedefi",
    ),
    (
        date(2026, 10, 1),
        "GID-PAZARLAMA",
        "Ekim pazarlama bütçesi",
        Decimal("0.00"),
        Decimal("35000.00"),
        "Dijital reklam ve kampanya",
    ),
    (
        date(2026, 10, 1),
        "GID-PERSONEL",
        "Ekim personel bütçesi",
        Decimal("0.00"),
        Decimal("65000.00"),
        "Ücret ve yan haklar",
    ),
    (
        date(2026, 10, 1),
        "GID-OPERASYON",
        "Ekim operasyon bütçesi",
        Decimal("0.00"),
        Decimal("35000.00"),
        "Ofis ve yazılım giderleri",
    ),
]

DEMO_FINANCIAL_TRANSACTIONS = [
    (
        "SEED-DEMO-2026-08-001",
        "GEL-SATIS",
        "in",
        "manual_in",
        date(2026, 8, 5),
        Decimal("82000.00"),
        "Demo ürün ve hizmet satış tahsilatı",
    ),
    (
        "SEED-DEMO-2026-08-002",
        "GEL-DANISMANLIK",
        "in",
        "manual_in",
        date(2026, 8, 12),
        Decimal("22000.00"),
        "Demo danışmanlık tahsilatı",
    ),
    (
        "SEED-DEMO-2026-08-003",
        "GID-PAZARLAMA",
        "out",
        "manual_out",
        date(2026, 8, 16),
        Decimal("12000.00"),
        "Demo dijital reklam ödemesi",
    ),
    (
        "SEED-DEMO-2026-08-004",
        "GID-PERSONEL",
        "out",
        "manual_out",
        date(2026, 8, 25),
        Decimal("48000.00"),
        "Demo personel gideri",
    ),
    (
        "SEED-DEMO-2026-08-005",
        "GID-OPERASYON",
        "out",
        "manual_out",
        date(2026, 8, 28),
        Decimal("10500.00"),
        "Demo operasyon gideri",
    ),
]

DEMO_HR_USERS = [
    {
        "username": "demo.ceo",
        "first_name": "Deniz",
        "last_name": "Arslan",
        "email": "deniz.arslan@demo.glauria.local",
        "employee_number": "GLA-0001",
        "department_code": "EXEC",
        "position_code": "EXEC-GM",
        "position_title": "Genel Müdür",
        "job_title": "Genel Müdür",
        "role": OrganizationMembership.Role.ADMIN,
        "permissions": [],
        "manager_username": None,
        "is_department_manager": True,
        "hire_date": date(2023, 1, 2),
    },
    {
        "username": "demo.hr.manager",
        "first_name": "Selin",
        "last_name": "Aydın",
        "email": "selin.aydin@demo.glauria.local",
        "employee_number": "GLA-0002",
        "department_code": "HR",
        "position_code": "HR-MGR",
        "position_title": "İnsan Kaynakları Müdürü",
        "job_title": "İnsan Kaynakları Müdürü",
        "role": OrganizationMembership.Role.MANAGER,
        "permissions": [
            OrganizationMembership.Permission.ACCESS_HR,
            OrganizationMembership.Permission.MANAGE_MEMBERS,
        ],
        "manager_username": "demo.ceo",
        "is_department_manager": True,
        "hire_date": date(2023, 3, 6),
    },
    {
        "username": "demo.hr.specialist",
        "first_name": "Ece",
        "last_name": "Demir",
        "email": "ece.demir@demo.glauria.local",
        "employee_number": "GLA-0003",
        "department_code": "HR",
        "position_code": "HR-SPC",
        "position_title": "İnsan Kaynakları Uzmanı",
        "job_title": "İnsan Kaynakları Uzmanı",
        "role": OrganizationMembership.Role.MEMBER,
        "permissions": [
            OrganizationMembership.Permission.ACCESS_HR,
        ],
        "manager_username": "demo.hr.manager",
        "is_department_manager": False,
        "hire_date": date(2024, 2, 12),
    },
    {
        "username": "demo.finance.manager",
        "first_name": "Burak",
        "last_name": "Kaya",
        "email": "burak.kaya@demo.glauria.local",
        "employee_number": "GLA-0004",
        "department_code": "FIN",
        "position_code": "FIN-MGR",
        "position_title": "Finans Müdürü",
        "job_title": "Finans Müdürü",
        "role": OrganizationMembership.Role.MANAGER,
        "permissions": [
            OrganizationMembership.Permission.ACCESS_FINANCE,
        ],
        "manager_username": "demo.ceo",
        "is_department_manager": True,
        "hire_date": date(2023, 5, 8),
    },
    {
        "username": "demo.purchasing.manager",
        "first_name": "Mert",
        "last_name": "Yılmaz",
        "email": "mert.yilmaz@demo.glauria.local",
        "employee_number": "GLA-0005",
        "department_code": "PUR",
        "position_code": "PUR-MGR",
        "position_title": "Satın Alma Müdürü",
        "job_title": "Satın Alma Müdürü",
        "role": OrganizationMembership.Role.MANAGER,
        "permissions": [
            OrganizationMembership.Permission.ACCESS_PURCHASING,
        ],
        "manager_username": "demo.ceo",
        "is_department_manager": True,
        "hire_date": date(2023, 7, 10),
    },
    {
        "username": "demo.sales.manager",
        "first_name": "Elif",
        "last_name": "Şahin",
        "email": "elif.sahin@demo.glauria.local",
        "employee_number": "GLA-0006",
        "department_code": "SAL",
        "position_code": "SAL-MGR",
        "position_title": "Satış Müdürü",
        "job_title": "Satış Müdürü",
        "role": OrganizationMembership.Role.MANAGER,
        "permissions": [
            OrganizationMembership.Permission.ACCESS_SALES,
        ],
        "manager_username": "demo.ceo",
        "is_department_manager": True,
        "hire_date": date(2023, 9, 4),
    },
    {
        "username": "demo.operations.manager",
        "first_name": "Can",
        "last_name": "Öztürk",
        "email": "can.ozturk@demo.glauria.local",
        "employee_number": "GLA-0007",
        "department_code": "OPS",
        "position_code": "OPS-MGR",
        "position_title": "Operasyon Müdürü",
        "job_title": "Operasyon Müdürü",
        "role": OrganizationMembership.Role.MANAGER,
        "permissions": [
            OrganizationMembership.Permission.ACCESS_INVENTORY,
            OrganizationMembership.Permission.ACCESS_MANUFACTURING,
        ],
        "manager_username": "demo.ceo",
        "is_department_manager": True,
        "hire_date": date(2023, 11, 6),
    },
]
DEMO_ABSENCE_TYPES = [
    {
        "code": "ANNUAL",
        "name": "Yıllık İzin",
        "description": (
            "Personelin yıllık ücretli izin hakkı."
        ),
        "is_paid": True,
        "requires_approval": True,
        "deducts_balance": True,
        "default_entitlement_days": Decimal("14.00"),
    },
    {
        "code": "SICK",
        "name": "Hastalık İzni",
        "description": (
            "Sağlık durumuna bağlı ücretli izin kaydı."
        ),
        "is_paid": True,
        "requires_approval": True,
        "deducts_balance": False,
        "default_entitlement_days": Decimal("10.00"),
    },
    {
        "code": "EXCUSE",
        "name": "Mazeret İzni",
        "description": (
            "Kısa süreli kişisel mazeret izinleri."
        ),
        "is_paid": True,
        "requires_approval": True,
        "deducts_balance": True,
        "default_entitlement_days": Decimal("5.00"),
    },
]


DEMO_ABSENCE_REQUESTS = [
    {
        "employee_username": "demo.hr.specialist",
        "absence_type_code": "ANNUAL",
        "start_date": date(2026, 8, 10),
        "end_date": date(2026, 8, 12),
        "reason": (
            "Aile ziyareti için yıllık izin talebi."
        ),
        "status": AbsenceRequest.Status.SUBMITTED,
        "decision_note": "",
    },
    {
        "employee_username": "demo.finance.manager",
        "absence_type_code": "ANNUAL",
        "start_date": date(2026, 7, 20),
        "end_date": date(2026, 7, 22),
        "reason": (
            "Planlanan yaz dönemi yıllık izni."
        ),
        "status": AbsenceRequest.Status.APPROVED,
        "decision_note": (
            "Departman iş planı doğrultusunda onaylandı."
        ),
    },
    {
        "employee_username": "demo.purchasing.manager",
        "absence_type_code": "EXCUSE",
        "start_date": date(2026, 8, 18),
        "end_date": date(2026, 8, 18),
        "reason": (
            "Kişisel resmi işlemler için mazeret izni."
        ),
        "status": AbsenceRequest.Status.DRAFT,
        "decision_note": "",
    },
]
DEMO_WORK_SCHEDULE_CODE = "STD-40"

DEMO_WORK_SCHEDULE_DAYS = [
    {
        "weekday": WorkScheduleDay.Weekday.MONDAY,
        "is_working_day": True,
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "break_minutes": 60,
    },
    {
        "weekday": WorkScheduleDay.Weekday.TUESDAY,
        "is_working_day": True,
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "break_minutes": 60,
    },
    {
        "weekday": WorkScheduleDay.Weekday.WEDNESDAY,
        "is_working_day": True,
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "break_minutes": 60,
    },
    {
        "weekday": WorkScheduleDay.Weekday.THURSDAY,
        "is_working_day": True,
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "break_minutes": 60,
    },
    {
        "weekday": WorkScheduleDay.Weekday.FRIDAY,
        "is_working_day": True,
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "break_minutes": 60,
    },
    {
        "weekday": WorkScheduleDay.Weekday.SATURDAY,
        "is_working_day": False,
        "start_time": None,
        "end_time": None,
        "break_minutes": 0,
    },
    {
        "weekday": WorkScheduleDay.Weekday.SUNDAY,
        "is_working_day": False,
        "start_time": None,
        "end_time": None,
        "break_minutes": 0,
    },
]


DEMO_ATTENDANCE_RECORDS = [
    {
        "employee_username": "demo.ceo",
        "work_date": date(2026, 8, 3),
        "clock_in_time": time(9, 0),
        "clock_out_time": time(18, 0),
        "status": AttendanceRecord.Status.PRESENT,
        "approval_status": AttendanceRecord.ApprovalStatus.APPROVED,
        "note": "Standart zamanında çalışma kaydı.",
    },
    {
        "employee_username": "demo.hr.manager",
        "work_date": date(2026, 8, 3),
        "clock_in_time": time(9, 12),
        "clock_out_time": time(18, 0),
        "status": AttendanceRecord.Status.LATE,
        "approval_status": AttendanceRecord.ApprovalStatus.SUBMITTED,
        "note": "On iki dakika geç giriş yapılan demo kayıt.",
    },
    {
        "employee_username": "demo.hr.specialist",
        "work_date": date(2026, 8, 3),
        "clock_in_time": time(8, 58),
        "clock_out_time": time(18, 0),
        "status": AttendanceRecord.Status.PRESENT,
        "approval_status": AttendanceRecord.ApprovalStatus.DRAFT,
        "note": "Tamamlanmış taslak devam kaydı.",
    },
    {
        "employee_username": "demo.finance.manager",
        "work_date": date(2026, 7, 20),
        "clock_in_time": None,
        "clock_out_time": None,
        "status": AttendanceRecord.Status.ON_LEAVE,
        "approval_status": AttendanceRecord.ApprovalStatus.APPROVED,
        "note": "Onaylı yıllık izin ile otomatik oluşan kayıt.",
    },
    {
        "employee_username": "demo.purchasing.manager",
        "work_date": date(2026, 8, 3),
        "clock_in_time": time(9, 0),
        "clock_out_time": time(18, 0),
        "status": AttendanceRecord.Status.REMOTE,
        "approval_status": AttendanceRecord.ApprovalStatus.SUBMITTED,
        "note": "Uzaktan çalışma demo kaydı.",
    },
    {
        "employee_username": "demo.sales.manager",
        "work_date": date(2026, 8, 3),
        "clock_in_time": time(9, 0),
        "clock_out_time": time(20, 0),
        "status": AttendanceRecord.Status.PRESENT,
        "approval_status": AttendanceRecord.ApprovalStatus.APPROVED,
        "note": "Fazla mesai içeren demo kayıt.",
    },
    {
        "employee_username": "demo.operations.manager",
        "work_date": date(2026, 8, 2),
        "clock_in_time": None,
        "clock_out_time": None,
        "status": AttendanceRecord.Status.NON_WORKING_DAY,
        "approval_status": AttendanceRecord.ApprovalStatus.DRAFT,
        "note": "Pazar günü çalışma dışı kayıt.",
    },
]

DEMO_PERFORMANCE_CYCLE = {
    "code": "PERF-2026",
    "name": "2026 Yıllık Performans Dönemi",
    "description": (
        "Glauria Demo A.Ş. çalışanları için yıllık hedef ve "
        "performans değerlendirme dönemi."
    ),
    "start_date": date(2026, 1, 1),
    "end_date": date(2026, 12, 31),
    "self_review_deadline": date(2026, 11, 30),
    "manager_review_deadline": date(2026, 12, 15),
}


DEMO_EMPLOYEE_GOALS = [
    {
        "employee_username": "demo.ceo",
        "title": "Kurumsal büyüme planını gerçekleştirmek",
        "description": (
            "Şirketin yıllık büyüme ve kârlılık hedeflerini "
            "stratejik olarak yönetmek."
        ),
        "weight": Decimal("40.00"),
        "target_value": Decimal("20.00"),
        "current_value": Decimal("14.00"),
        "unit": "yüzde",
        "progress_percentage": Decimal("70.00"),
        "status": EmployeeGoal.Status.IN_PROGRESS,
    },
    {
        "employee_username": "demo.hr.manager",
        "title": "Çalışan bağlılığını artırmak",
        "description": (
            "Çalışan bağlılığı ve memnuniyet skorunu artırmak."
        ),
        "weight": Decimal("30.00"),
        "target_value": Decimal("90.00"),
        "current_value": Decimal("86.00"),
        "unit": "puan",
        "progress_percentage": Decimal("80.00"),
        "status": EmployeeGoal.Status.IN_PROGRESS,
    },
    {
        "employee_username": "demo.hr.specialist",
        "title": "İK operasyon süresini azaltmak",
        "description": (
            "Personel ve izin operasyonlarının tamamlanma süresini "
            "iyileştirmek."
        ),
        "weight": Decimal("25.00"),
        "target_value": Decimal("30.00"),
        "current_value": Decimal("21.00"),
        "unit": "yüzde",
        "progress_percentage": Decimal("70.00"),
        "status": EmployeeGoal.Status.IN_PROGRESS,
    },
    {
        "employee_username": "demo.finance.manager",
        "title": "Finansal raporlama doğruluğunu artırmak",
        "description": (
            "Aylık finansal raporların doğruluk ve zamanında "
            "tamamlanma oranını yükseltmek."
        ),
        "weight": Decimal("35.00"),
        "target_value": Decimal("99.00"),
        "current_value": Decimal("97.50"),
        "unit": "yüzde",
        "progress_percentage": Decimal("85.00"),
        "status": EmployeeGoal.Status.IN_PROGRESS,
    },
    {
        "employee_username": "demo.purchasing.manager",
        "title": "Tedarik maliyetlerini optimize etmek",
        "description": (
            "Stratejik tedarikçi anlaşmalarıyla satın alma "
            "maliyetlerini azaltmak."
        ),
        "weight": Decimal("35.00"),
        "target_value": Decimal("12.00"),
        "current_value": Decimal("4.00"),
        "unit": "yüzde",
        "progress_percentage": Decimal("35.00"),
        "status": EmployeeGoal.Status.IN_PROGRESS,
    },
    {
        "employee_username": "demo.sales.manager",
        "title": "Yeni müşteri kazanımını artırmak",
        "description": (
            "Yıl boyunca elli yeni kurumsal müşteri kazanmak."
        ),
        "weight": Decimal("40.00"),
        "target_value": Decimal("50.00"),
        "current_value": Decimal("52.00"),
        "unit": "müşteri",
        "progress_percentage": Decimal("100.00"),
        "status": EmployeeGoal.Status.COMPLETED,
        "completion_note": (
            "Yıllık yeni müşteri hedefi planlanandan önce tamamlandı."
        ),
    },
    {
        "employee_username": "demo.operations.manager",
        "title": "Operasyon verimliliğini artırmak",
        "description": (
            "Operasyon süreçlerinde çevrim süresini ve hata oranını "
            "iyileştirmek."
        ),
        "weight": Decimal("30.00"),
        "target_value": Decimal("15.00"),
        "current_value": Decimal("11.00"),
        "unit": "yüzde",
        "progress_percentage": Decimal("75.00"),
        "status": EmployeeGoal.Status.IN_PROGRESS,
    },
]


DEMO_PERFORMANCE_REVIEWS = [
    {
        "employee_username": "demo.hr.manager",
        "manager_username": "demo.ceo",
        "status": PerformanceReview.Status.COMPLETED,
        "employee_rating": Decimal("4.20"),
        "manager_rating": Decimal("4.50"),
        "overall_rating": Decimal("4.40"),
        "employee_comment": (
            "İK süreçlerinin dijitalleşmesi ve çalışan deneyimi "
            "hedeflerinde ilerleme sağlandı."
        ),
        "manager_comment": (
            "Yıl boyunca insan kaynakları süreçlerinde güçlü liderlik "
            "gösterildi."
        ),
        "development_plan": (
            "Organizasyonel gelişim ve yetenek yönetimi programlarına "
            "katılım."
        ),
    },
    {
        "employee_username": "demo.hr.specialist",
        "manager_username": "demo.hr.manager",
        "status": PerformanceReview.Status.MANAGER_REVIEW,
        "employee_rating": Decimal("4.10"),
        "manager_rating": None,
        "overall_rating": None,
        "employee_comment": (
            "Personel operasyonları ve izin süreçlerinde belirlenen "
            "hedeflerin çoğu tamamlandı."
        ),
        "manager_comment": "",
        "development_plan": "",
    },
    {
        "employee_username": "demo.finance.manager",
        "manager_username": "demo.ceo",
        "status": PerformanceReview.Status.SELF_REVIEW,
        "employee_rating": None,
        "manager_rating": None,
        "overall_rating": None,
        "employee_comment": "",
        "manager_comment": "",
        "development_plan": "",
    },
    {
        "employee_username": "demo.purchasing.manager",
        "manager_username": "demo.ceo",
        "status": PerformanceReview.Status.DRAFT,
        "employee_rating": None,
        "manager_rating": None,
        "overall_rating": None,
        "employee_comment": "",
        "manager_comment": "",
        "development_plan": "",
    },
    {
        "employee_username": "demo.sales.manager",
        "manager_username": "demo.ceo",
        "status": PerformanceReview.Status.COMPLETED,
        "employee_rating": Decimal("4.60"),
        "manager_rating": Decimal("4.80"),
        "overall_rating": Decimal("4.70"),
        "employee_comment": (
            "Yeni müşteri kazanımı ve satış büyümesi hedefleri "
            "başarıyla tamamlandı."
        ),
        "manager_comment": (
            "Satış performansı ve ekip liderliği beklentilerin "
            "üzerindedir."
        ),
        "development_plan": (
            "Stratejik satış yönetimi ve uluslararası pazar geliştirme."
        ),
    },
    {
        "employee_username": "demo.operations.manager",
        "manager_username": "demo.ceo",
        "status": PerformanceReview.Status.CANCELLED,
        "employee_rating": None,
        "manager_rating": None,
        "overall_rating": None,
        "employee_comment": "",
        "manager_comment": "",
        "development_plan": "",
    },
]


class Command(BaseCommand):
    help = (
        "Glauria Demo A.Ş. için organizasyon, İK, finans ve satın alma "
        "örnek kayıtlarını güvenle oluşturur."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            required=True,
            help=(
                "Demo şirketinde owner yapılacak mevcut kullanıcı adı. "
                "Örnek: --owner ikra"
            ),
        )
        parser.add_argument(
            "--demo-password",
            default=None,
            help=(
                "Demo kullanıcılarına atanacak ortak geliştirme parolası. "
                "Verilmezse yeni hesaplar kullanılamaz parola ile oluşturulur."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        owner_username = options["owner"].strip()
        demo_password = options["demo_password"]

        try:
            owner = User.objects.get(username=owner_username)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"'{owner_username}' adlı kullanıcı bulunamadı."
            ) from exc

        company, company_created = Company.objects.get_or_create(
            name=DEMO_COMPANY_NAME,
            defaults={
                "legal_name": "Glauria Demo Anonim Şirketi",
                "tax_number": "1111111111",
                "tax_office": "Demo Vergi Dairesi",
                "email": "demo@glauria.local",
                "phone": "+90 312 000 00 00",
                "address": (
                    "Glauria Demo Merkezi, Ankara, Türkiye"
                ),
            },
        )

        subscription, subscription_created = (
            CompanySubscription.objects.get_or_create(
                company=company,
                defaults={
                    "plan": CompanySubscription.Plan.ENTERPRISE,
                    "status": CompanySubscription.Status.ACTIVE,
                    "member_limit": 50,
                },
            )
        )

        branch, branch_created = Branch.objects.get_or_create(
            company=company,
            code=DEMO_BRANCH_CODE,
            defaults={
                "name": "Demo Genel Merkez",
                "email": "merkez@glauria.local",
                "phone": "+90 312 000 00 01",
                "address": (
                    "Glauria Demo Merkezi, Ankara, Türkiye"
                ),
            },
        )

        departments = {}
        created_department_count = 0

        for department_code, department_name in DEMO_DEPARTMENTS:
            department, created = Department.objects.get_or_create(
                branch=branch,
                code=department_code,
                defaults={
                    "name": department_name,
                },
            )
            departments[department_code] = department

            if created:
                created_department_count += 1

        membership, membership_created = (
            OrganizationMembership.objects.get_or_create(
                user=owner,
                company=company,
                branch=branch,
                department=departments["EXEC"],
                defaults={
                    "job_title": "Demo Şirket Sahibi",
                    "role": OrganizationMembership.Role.OWNER,
                    "is_primary": False,
                    "is_active": True,
                },
            )
        )
        created_hr_user_count = 0
        created_hr_membership_count = 0
        created_position_count = 0
        created_employee_count = 0
        created_assignment_count = 0

        hr_users = {}
        hr_employees = {}
        hr_positions = {}

        for person_data in DEMO_HR_USERS:
            department = departments[
                person_data["department_code"]
            ]

            position, position_created = Position.objects.update_or_create(
                company=company,
                code=person_data["position_code"],
                defaults={
                    "department": department,
                    "title": person_data["position_title"],
                    "description": (
                        "Glauria Demo A.Ş. için oluşturulan "
                        "örnek İK pozisyonu."
                    ),
                    "is_active": True,
                },
            )

            hr_positions[person_data["position_code"]] = position

            if position_created:
                created_position_count += 1

            user, user_created = User.objects.update_or_create(
                username=person_data["username"],
                defaults={
                    "first_name": person_data["first_name"],
                    "last_name": person_data["last_name"],
                    "email": person_data["email"],
                    "user_type": User.UserType.INTERNAL,
                    "is_active": True,
                },
            )

            if demo_password:
                user.set_password(demo_password)
                user.save(update_fields=["password"])
            elif user_created:
                user.set_unusable_password()
                user.save(update_fields=["password"])

            hr_users[person_data["username"]] = user

            if user_created:
                created_hr_user_count += 1

            _, hr_membership_created = (
                OrganizationMembership.objects.update_or_create(
                    user=user,
                    company=company,
                    branch=branch,
                    department=department,
                    defaults={
                        "job_title": person_data["job_title"],
                        "role": person_data["role"],
                        "permissions": person_data["permissions"],
                        "is_primary": False,
                        "is_active": True,
                    },
                )
            )

            if hr_membership_created:
                created_hr_membership_count += 1

            employee, employee_created = Employee.objects.update_or_create(
                company=company,
                employee_number=person_data["employee_number"],
                defaults={
                    "user": user,
                    "first_name": person_data["first_name"],
                    "last_name": person_data["last_name"],
                    "work_email": person_data["email"],
                    "hire_date": person_data["hire_date"],
                    "employment_status": (
                        Employee.EmploymentStatus.ACTIVE
                    ),
                    "is_active": True,
                },
            )

            hr_employees[person_data["username"]] = employee

            if employee_created:
                created_employee_count += 1

        for person_data in DEMO_HR_USERS:
            employee = hr_employees[person_data["username"]]
            department = departments[
                person_data["department_code"]
            ]
            position = hr_positions[
                person_data["position_code"]
            ]

            manager_username = person_data["manager_username"]
            manager = (
                hr_employees[manager_username]
                if manager_username
                else None
            )

            _, assignment_created = (
                EmploymentAssignment.objects.update_or_create(
                    employee=employee,
                    is_primary=True,
                    end_date=None,
                    defaults={
                        "branch": branch,
                        "department": department,
                        "position": position,
                        "manager": manager,
                        "employment_type": (
                            EmploymentAssignment
                            .EmploymentType
                            .FULL_TIME
                        ),
                        "start_date": person_data["hire_date"],
                        "is_department_manager": (
                            person_data["is_department_manager"]
                        ),
                    },
                )
            )

            if assignment_created:
                created_assignment_count += 1
        absence_types = {}
        created_absence_type_count = 0
        created_absence_balance_count = 0
        created_absence_request_count = 0
        created_absence_event_count = 0

        for absence_type_data in DEMO_ABSENCE_TYPES:
            absence_type, absence_type_created = (
                AbsenceType.objects.update_or_create(
                    company=company,
                    code=absence_type_data["code"],
                    defaults={
                        "name": absence_type_data["name"],
                        "description": (
                            absence_type_data["description"]
                        ),
                        "is_paid": absence_type_data["is_paid"],
                        "requires_approval": (
                            absence_type_data[
                                "requires_approval"
                            ]
                        ),
                        "deducts_balance": (
                            absence_type_data[
                                "deducts_balance"
                            ]
                        ),
                        "default_entitlement_days": (
                            absence_type_data[
                                "default_entitlement_days"
                            ]
                        ),
                        "is_active": True,
                    },
                )
            )

            absence_types[
                absence_type_data["code"]
            ] = absence_type

            if absence_type_created:
                created_absence_type_count += 1

        for employee_username, employee in hr_employees.items():
            for absence_type_code, absence_type in (
                absence_types.items()
            ):
                used_days = Decimal("0.00")

                if (
                    employee_username
                    == "demo.finance.manager"
                    and absence_type_code == "ANNUAL"
                ):
                    used_days = Decimal("3.00")

                _, balance_created = (
                    AbsenceBalance.objects.update_or_create(
                        company=company,
                        employee=employee,
                        absence_type=absence_type,
                        year=2026,
                        defaults={
                            "entitled_days": (
                                absence_type
                                .default_entitlement_days
                            ),
                            "carried_days": Decimal("0.00"),
                            "adjustment_days": Decimal("0.00"),
                            "used_days": used_days,
                        },
                    )
                )

                if balance_created:
                    created_absence_balance_count += 1

        absence_requests = {}

        for request_data in DEMO_ABSENCE_REQUESTS:
            employee = hr_employees[
                request_data["employee_username"]
            ]
            absence_type = absence_types[
                request_data["absence_type_code"]
            ]
            status = request_data["status"]

            is_submitted = status in {
                AbsenceRequest.Status.SUBMITTED,
                AbsenceRequest.Status.APPROVED,
            }
            is_decided = (
                status == AbsenceRequest.Status.APPROVED
            )

            absence_request, request_created = (
                AbsenceRequest.objects.update_or_create(
                    company=company,
                    employee=employee,
                    absence_type=absence_type,
                    start_date=request_data["start_date"],
                    end_date=request_data["end_date"],
                    defaults={
                        "reason": request_data["reason"],
                        "status": status,
                        "submitted_at": (
                            timezone.now()
                            if is_submitted
                            else None
                        ),
                        "decided_at": (
                            timezone.now()
                            if is_decided
                            else None
                        ),
                        "decided_by": (
                            hr_users["demo.hr.manager"]
                            if is_decided
                            else None
                        ),
                        "decision_note": (
                            request_data["decision_note"]
                        ),
                    },
                )
            )

            absence_requests[
                (
                    request_data["employee_username"],
                    request_data["absence_type_code"],
                    request_data["start_date"],
                )
            ] = absence_request

            if request_created:
                created_absence_request_count += 1

            if is_submitted:
                _, submitted_event_created = (
                    AbsenceRequestEvent.objects.get_or_create(
                        request=absence_request,
                        previous_status=(
                            AbsenceRequest.Status.DRAFT
                        ),
                        new_status=(
                            AbsenceRequest.Status.SUBMITTED
                        ),
                        defaults={
                            "company": company,
                            "changed_by": employee.user,
                            "note": (
                                "Demo izin talebi onaya "
                                "gönderildi."
                            ),
                        },
                    )
                )

                if submitted_event_created:
                    created_absence_event_count += 1

            if is_decided:
                _, approved_event_created = (
                    AbsenceRequestEvent.objects.get_or_create(
                        request=absence_request,
                        previous_status=(
                            AbsenceRequest.Status.SUBMITTED
                        ),
                        new_status=(
                            AbsenceRequest.Status.APPROVED
                        ),
                        defaults={
                            "company": company,
                            "changed_by": (
                                hr_users["demo.hr.manager"]
                            ),
                            "note": (
                                request_data["decision_note"]
                            ),
                        },
                    )
                )

                if approved_event_created:
                    created_absence_event_count += 1
                work_schedule, work_schedule_created = (
            WorkSchedule.objects.update_or_create(
                company=company,
                code=DEMO_WORK_SCHEDULE_CODE,
                defaults={
                    "name": "Standart 40 Saat",
                    "weekly_hours": Decimal("40.00"),
                    "timezone_name": "Europe/Istanbul",
                    "description": (
                        "Pazartesi-Cuma 09:00-18:00 standart "
                        "demo çalışma takvimi."
                    ),
                    "is_active": True,
                },
            )
        )

        created_work_schedule_count = int(
            work_schedule_created
        )
        created_work_schedule_day_count = 0
        created_schedule_assignment_count = 0
        created_attendance_record_count = 0

        attendance_event_count_before = (
            AttendanceRecordEvent.objects.filter(
                company=company,
            ).count()
        )

        for schedule_day_data in DEMO_WORK_SCHEDULE_DAYS:
            _, schedule_day_created = (
                WorkScheduleDay.objects.update_or_create(
                    work_schedule=work_schedule,
                    weekday=schedule_day_data["weekday"],
                    defaults={
                        "is_working_day": (
                            schedule_day_data[
                                "is_working_day"
                            ]
                        ),
                        "start_time": (
                            schedule_day_data["start_time"]
                        ),
                        "end_time": (
                            schedule_day_data["end_time"]
                        ),
                        "break_minutes": (
                            schedule_day_data[
                                "break_minutes"
                            ]
                        ),
                        "crosses_midnight": False,
                    },
                )
            )

            if schedule_day_created:
                created_work_schedule_day_count += 1

        for employee in hr_employees.values():
            _, schedule_assignment_created = (
                EmployeeScheduleAssignment.objects.update_or_create(
                    company=company,
                    employee=employee,
                    is_primary=True,
                    end_date=None,
                    defaults={
                        "work_schedule": work_schedule,
                        "start_date": date(2026, 1, 1),
                        "assignment_note": (
                            "Demo standart çalışma takvimi ataması."
                        ),
                    },
                )
            )

            if schedule_assignment_created:
                created_schedule_assignment_count += 1

        attendance_approver = hr_users["demo.hr.manager"]

        for attendance_data in DEMO_ATTENDANCE_RECORDS:
            employee = hr_employees[
                attendance_data["employee_username"]
            ]

            attendance_record, attendance_record_created = (
                generate_attendance_record(
                    employee=employee,
                    work_date=attendance_data["work_date"],
                    changed_by=attendance_approver,
                )
            )

            if attendance_record_created:
                created_attendance_record_count += 1

            attendance_record.refresh_from_db()

            if (
                attendance_data["status"]
                == AttendanceRecord.Status.REMOTE
                and not attendance_record.clock_in_at
                and attendance_record.approval_status
                in {
                    AttendanceRecord.ApprovalStatus.DRAFT,
                    AttendanceRecord.ApprovalStatus.REJECTED,
                }
            ):
                attendance_record.status = (
                    AttendanceRecord.Status.REMOTE
                )
                attendance_record.save(
                    update_fields=[
                        "status",
                        "worked_minutes",
                        "updated_at",
                    ]
                )

            clock_in_time = attendance_data[
                "clock_in_time"
            ]

            if (
                clock_in_time
                and not attendance_record.clock_in_at
            ):
                clock_in_at = timezone.make_aware(
                    datetime.combine(
                        attendance_data["work_date"],
                        clock_in_time,
                    ),
                    timezone.get_current_timezone(),
                )

                attendance_record = clock_in_attendance(
                    attendance_record=attendance_record,
                    changed_by=employee.user,
                    clock_in_at=clock_in_at,
                )

            attendance_record.refresh_from_db()

            clock_out_time = attendance_data[
                "clock_out_time"
            ]

            if (
                clock_out_time
                and attendance_record.clock_in_at
                and not attendance_record.clock_out_at
            ):
                clock_out_at = timezone.make_aware(
                    datetime.combine(
                        attendance_data["work_date"],
                        clock_out_time,
                    ),
                    timezone.get_current_timezone(),
                )

                attendance_record = clock_out_attendance(
                    attendance_record=attendance_record,
                    changed_by=employee.user,
                    clock_out_at=clock_out_at,
                )

            attendance_record.refresh_from_db()

            if attendance_record.note != attendance_data["note"]:
                attendance_record.note = attendance_data["note"]
                attendance_record.save(
                    update_fields=[
                        "note",
                        "worked_minutes",
                        "updated_at",
                    ]
                )

            target_approval_status = attendance_data[
                "approval_status"
            ]

            if (
                target_approval_status
                in {
                    AttendanceRecord.ApprovalStatus.SUBMITTED,
                    AttendanceRecord.ApprovalStatus.APPROVED,
                }
                and attendance_record.approval_status
                in {
                    AttendanceRecord.ApprovalStatus.DRAFT,
                    AttendanceRecord.ApprovalStatus.REJECTED,
                }
            ):
                attendance_record = submit_attendance_record(
                    attendance_record=attendance_record,
                    changed_by=employee.user,
                    note="Demo devam kaydı onaya gönderildi.",
                )

            attendance_record.refresh_from_db()

            if (
                target_approval_status
                == AttendanceRecord.ApprovalStatus.APPROVED
                and attendance_record.approval_status
                == AttendanceRecord.ApprovalStatus.SUBMITTED
            ):
                approve_attendance_record(
                    attendance_record=attendance_record,
                    changed_by=attendance_approver,
                    note="Demo devam kaydı onaylandı.",
                )

        created_attendance_event_count = (
            AttendanceRecordEvent.objects.filter(
                company=company,
            ).count()
            - attendance_event_count_before
        )
        performance_cycle, performance_cycle_created = (
            PerformanceReviewCycle.objects.update_or_create(
                company=company,
                code=DEMO_PERFORMANCE_CYCLE["code"],
                defaults={
                    "name": DEMO_PERFORMANCE_CYCLE["name"],
                    "description": (
                        DEMO_PERFORMANCE_CYCLE["description"]
                    ),
                    "start_date": (
                        DEMO_PERFORMANCE_CYCLE["start_date"]
                    ),
                    "end_date": DEMO_PERFORMANCE_CYCLE["end_date"],
                    "self_review_deadline": (
                        DEMO_PERFORMANCE_CYCLE[
                            "self_review_deadline"
                        ]
                    ),
                    "manager_review_deadline": (
                        DEMO_PERFORMANCE_CYCLE[
                            "manager_review_deadline"
                        ]
                    ),
                    "status": (
                        PerformanceReviewCycle.Status.OPEN
                    ),
                    "is_active": True,
                },
            )
        )

        created_performance_cycle_count = int(
            performance_cycle_created
        )
        created_employee_goal_count = 0
        created_performance_review_count = 0
        created_performance_event_count = 0

        for goal_data in DEMO_EMPLOYEE_GOALS:
            employee = hr_employees[
                goal_data["employee_username"]
            ]

            _, goal_created = EmployeeGoal.objects.update_or_create(
                cycle=performance_cycle,
                employee=employee,
                title=goal_data["title"],
                defaults={
                    "company": company,
                    "description": goal_data["description"],
                    "weight": goal_data["weight"],
                    "target_value": goal_data["target_value"],
                    "current_value": goal_data["current_value"],
                    "unit": goal_data["unit"],
                    "start_date": performance_cycle.start_date,
                    "due_date": date(2026, 12, 15),
                    "progress_percentage": (
                        goal_data["progress_percentage"]
                    ),
                    "status": goal_data["status"],
                    "completion_note": goal_data.get(
                        "completion_note",
                        "",
                    ),
                },
            )

            if goal_created:
                created_employee_goal_count += 1

        for review_data in DEMO_PERFORMANCE_REVIEWS:
            employee = hr_employees[
                review_data["employee_username"]
            ]
            manager = hr_employees[
                review_data["manager_username"]
            ]
            employee_user = hr_users[
                review_data["employee_username"]
            ]
            manager_user = hr_users[
                review_data["manager_username"]
            ]

            target_status = review_data["status"]

            submitted_at = None
            completed_at = None
            completed_by = None

            if target_status in {
                PerformanceReview.Status.MANAGER_REVIEW,
                PerformanceReview.Status.COMPLETED,
            }:
                submitted_at = timezone.make_aware(
                    datetime(2026, 11, 25, 10, 0)
                )

            if target_status == PerformanceReview.Status.COMPLETED:
                completed_at = timezone.make_aware(
                    datetime(2026, 12, 10, 15, 30)
                )
                completed_by = manager_user

            performance_review, review_created = (
                PerformanceReview.objects.update_or_create(
                    company=company,
                    cycle=performance_cycle,
                    employee=employee,
                    defaults={
                        "manager": manager,
                        "status": target_status,
                        "employee_rating": (
                            review_data["employee_rating"]
                        ),
                        "manager_rating": (
                            review_data["manager_rating"]
                        ),
                        "overall_rating": (
                            review_data["overall_rating"]
                        ),
                        "employee_comment": (
                            review_data["employee_comment"]
                        ),
                        "manager_comment": (
                            review_data["manager_comment"]
                        ),
                        "development_plan": (
                            review_data["development_plan"]
                        ),
                        "submitted_at": submitted_at,
                        "completed_at": completed_at,
                        "completed_by": completed_by,
                    },
                )
            )

            if review_created:
                created_performance_review_count += 1

            event_definitions = [
                {
                    "event_type": (
                        PerformanceReviewEvent.EventType.CREATED
                    ),
                    "previous_status": "",
                    "new_status": PerformanceReview.Status.DRAFT,
                    "changed_by": manager_user,
                    "note": (
                        "Demo performans değerlendirmesi oluşturuldu."
                    ),
                },
            ]

            if target_status in {
                PerformanceReview.Status.SELF_REVIEW,
                PerformanceReview.Status.MANAGER_REVIEW,
                PerformanceReview.Status.COMPLETED,
            }:
                event_definitions.append(
                    {
                        "event_type": (
                            PerformanceReviewEvent
                            .EventType
                            .SELF_REVIEW_STARTED
                        ),
                        "previous_status": (
                            PerformanceReview.Status.DRAFT
                        ),
                        "new_status": (
                            PerformanceReview.Status.SELF_REVIEW
                        ),
                        "changed_by": employee_user,
                        "note": "Demo öz değerlendirme süreci başladı.",
                    }
                )

            if target_status in {
                PerformanceReview.Status.MANAGER_REVIEW,
                PerformanceReview.Status.COMPLETED,
            }:
                event_definitions.append(
                    {
                        "event_type": (
                            PerformanceReviewEvent
                            .EventType
                            .SELF_REVIEW_SUBMITTED
                        ),
                        "previous_status": (
                            PerformanceReview.Status.SELF_REVIEW
                        ),
                        "new_status": (
                            PerformanceReview.Status.MANAGER_REVIEW
                        ),
                        "changed_by": employee_user,
                        "note": (
                            "Demo öz değerlendirme yöneticiye "
                            "gönderildi."
                        ),
                    }
                )

            if target_status == PerformanceReview.Status.COMPLETED:
                event_definitions.append(
                    {
                        "event_type": (
                            PerformanceReviewEvent
                            .EventType
                            .COMPLETED
                        ),
                        "previous_status": (
                            PerformanceReview.Status.MANAGER_REVIEW
                        ),
                        "new_status": (
                            PerformanceReview.Status.COMPLETED
                        ),
                        "changed_by": manager_user,
                        "note": (
                            "Demo performans değerlendirmesi "
                            "tamamlandı."
                        ),
                    }
                )

            if target_status == PerformanceReview.Status.CANCELLED:
                event_definitions.append(
                    {
                        "event_type": (
                            PerformanceReviewEvent
                            .EventType
                            .CANCELLED
                        ),
                        "previous_status": (
                            PerformanceReview.Status.DRAFT
                        ),
                        "new_status": (
                            PerformanceReview.Status.CANCELLED
                        ),
                        "changed_by": manager_user,
                        "note": (
                            "Organizasyon değişikliği nedeniyle demo "
                            "değerlendirme iptal edildi."
                        ),
                    }
                )

            for event_data in event_definitions:
                _, event_created = (
                    PerformanceReviewEvent.objects.get_or_create(
                        review=performance_review,
                        event_type=event_data["event_type"],
                        previous_status=(
                            event_data["previous_status"]
                        ),
                        new_status=event_data["new_status"],
                        defaults={
                            "company": company,
                            "changed_by": event_data["changed_by"],
                            "note": event_data["note"],
                        },
                    )
                )

                if event_created:
                    created_performance_event_count += 1

        financial_account, financial_account_created = (
            FinancialAccount.objects.get_or_create(
                company=company,
                name="Demo Operasyon Bankası",
                currency="TRY",
                defaults={
                    "account_type": (
                        FinancialAccount.AccountType.BANK
                    ),
                    "bank_name": "Glauria Demo Bankası",
                    "is_active": True,
                },
            )
        )

        budget_accounts = {}
        created_budget_account_count = 0

        for code, name, account_type, description in (
            DEMO_BUDGET_ACCOUNTS
        ):
            budget_account, created = (
                FinanceBudgetAccount.objects.get_or_create(
                    company=company,
                    code=code,
                    defaults={
                        "name": name,
                        "account_type": account_type,
                        "description": description,
                        "is_active": True,
                    },
                )
            )
            budget_accounts[code] = budget_account

            if created:
                created_budget_account_count += 1

        demo_budget, demo_budget_created = (
            FinanceBudget.objects.get_or_create(
                company=company,
                name="2026 Demo Operasyon Bütçesi",
                fiscal_year=2026,
                defaults={
                    "currency": "TRY",
                    "status": FinanceBudget.Status.ACTIVE,
                    "description": (
                        "Glauria Demo A.Ş. için üç aylık operasyon "
                        "ve nakit planı."
                    ),
                    "created_by": owner,
                    "submitted_by": owner,
                    "submitted_at": timezone.now(),
                    "approved_by": owner,
                    "approved_at": timezone.now(),
                },
            )
        )

        created_budget_line_count = 0

        for (
            period_month,
            account_code,
            category,
            planned_inflow,
            planned_outflow,
            notes,
        ) in DEMO_BUDGET_LINES:
            _, created = FinanceBudgetLine.objects.get_or_create(
                budget=demo_budget,
                budget_account=budget_accounts[account_code],
                period_month=period_month,
                defaults={
                    "category": category,
                    "planned_inflow": planned_inflow,
                    "planned_outflow": planned_outflow,
                    "notes": notes,
                },
            )

            if created:
                created_budget_line_count += 1

        created_transaction_count = 0

        for (
            reference_number,
            account_code,
            direction,
            transaction_type,
            transaction_date,
            amount,
            description,
        ) in DEMO_FINANCIAL_TRANSACTIONS:
            _, created = (
                FinancialAccountTransaction.objects.get_or_create(
                    company=company,
                    reference_number=reference_number,
                    defaults={
                        "account": financial_account,
                        "budget_account": budget_accounts[account_code],
                        "direction": direction,
                        "transaction_type": transaction_type,
                        "transaction_date": transaction_date,
                        "amount": amount,
                        "description": description,
                        "created_by": owner,
                    },
                )
            )

            if created:
                created_transaction_count += 1

        demo_suppliers = [
            {
                "code": "TED-DIJITAL-01",
                "name": "Demo Dijital Medya Ltd.",
                "legal_name": (
                    "Demo Dijital Medya Reklam ve Danışmanlık Ltd. Şti."
                ),
                "tax_number": "2222222222",
                "tax_office": "Çankaya Vergi Dairesi",
                "contact_name": "Ece Yılmaz",
                "email": "tedarikci@demo.glauria.local",
                "phone": "+90 312 000 10 01",
                "address": "Çankaya, Ankara, Türkiye",
                "payment_term_days": 30,
            },
            {
                "code": "TED-OFIS-01",
                "name": "Demo Ofis Çözümleri A.Ş.",
                "legal_name": "Demo Ofis Çözümleri Anonim Şirketi",
                "tax_number": "3333333333",
                "tax_office": "Kızılay Vergi Dairesi",
                "contact_name": "Mert Kaya",
                "email": "ofis@demo.glauria.local",
                "phone": "+90 312 000 10 02",
                "address": "Yenimahalle, Ankara, Türkiye",
                "payment_term_days": 45,
            },
        ]

        created_supplier_count = 0

        for supplier_data in demo_suppliers:
            _, created = Supplier.objects.get_or_create(
                company=company,
                code=supplier_data["code"],
                defaults={
                    **supplier_data,
                    "is_active": True,
                },
            )

            if created:
                created_supplier_count += 1

        purchase_request, purchase_request_created = (
            PurchaseRequest.objects.get_or_create(
                company=company,
                title="Eylül Demo Dijital Reklam Talebi",
                defaults={
                    "currency": "TRY",
                    "needed_by_date": date(2026, 9, 15),
                    "description": (
                        "Demo şirketinin Eylül dijital reklam "
                        "kampanyası için oluşturulmuş taslak talep."
                    ),
                    "requested_by": owner,
                },
            )
        )

        _, purchase_request_line_created = (
            PurchaseRequestLine.objects.get_or_create(
                purchase_request=purchase_request,
                budget_account=budget_accounts["GID-PAZARLAMA"],
                description="Eylül demo dijital reklam paketi",
                defaults={
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("18000.00"),
                    "needed_by_date": date(2026, 9, 15),
                    "notes": (
                        "Taslak talep; onay akışını test etmek için."
                    ),
                },
            )
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Seed demo altyapısı hazır.")
        )
        self.stdout.write(
            f"Şirket: {company.name} "
            f"({'oluşturuldu' if company_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Abonelik: {subscription.get_plan_display()} "
            f"({'oluşturuldu' if subscription_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Şube: {branch.name} "
            f"({'oluşturuldu' if branch_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni departman sayısı: {created_department_count}"
        )
        self.stdout.write(
            "Demo sahibi: "
            f"{owner.username} "
            f"({'oluşturuldu' if membership_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni demo kullanıcı sayısı: {created_hr_user_count}"
        )
        self.stdout.write(
            "Yeni demo üyelik sayısı: "
            f"{created_hr_membership_count}"
        )
        self.stdout.write(
            f"Yeni pozisyon sayısı: {created_position_count}"
        )
        self.stdout.write(
            f"Yeni personel kartı sayısı: {created_employee_count}"
        )
        self.stdout.write(
            f"Yeni personel ataması sayısı: {created_assignment_count}"
        )
        self.stdout.write(
            "Yeni izin türü sayısı: "
            f"{created_absence_type_count}"
        )
        self.stdout.write(
            "Yeni izin bakiyesi sayısı: "
            f"{created_absence_balance_count}"
        )
        self.stdout.write(
            "Yeni izin talebi sayısı: "
            f"{created_absence_request_count}"
        )
        self.stdout.write(
            "Yeni izin işlem kaydı sayısı: "
            f"{created_absence_event_count}"
        )
        self.stdout.write(
            "Yeni çalışma takvimi sayısı: "
            f"{created_work_schedule_count}"
        )
        self.stdout.write(
            "Yeni çalışma takvimi günü sayısı: "
            f"{created_work_schedule_day_count}"
        )
        self.stdout.write(
            "Yeni personel takvim ataması sayısı: "
            f"{created_schedule_assignment_count}"
        )
        self.stdout.write(
            "Yeni devam kaydı sayısı: "
            f"{created_attendance_record_count}"
        )
        self.stdout.write(
            "Yeni devam işlem kaydı sayısı: "
            f"{created_attendance_event_count}"
        )
        self.stdout.write(
            "Yeni performans dönemi sayısı: "
            f"{created_performance_cycle_count}"
        )
        self.stdout.write(
            "Yeni personel hedefi sayısı: "
            f"{created_employee_goal_count}"
        )
        self.stdout.write(
            "Yeni performans değerlendirmesi sayısı: "
            f"{created_performance_review_count}"
        )
        self.stdout.write(
            "Yeni performans işlem kaydı sayısı: "
            f"{created_performance_event_count}"
        )
        self.stdout.write(
            "Kasa / banka hesabı: "
            f"{financial_account.name} "
            f"({'oluşturuldu' if financial_account_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni bütçe hesabı sayısı: {created_budget_account_count}"
        )
        self.stdout.write(
            "Demo bütçe: "
            f"{demo_budget.name} "
            f"({'oluşturuldu' if demo_budget_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni bütçe satırı sayısı: {created_budget_line_count}"
        )
        self.stdout.write(
            f"Yeni finans hareketi sayısı: {created_transaction_count}"
        )
        self.stdout.write(
            f"Yeni tedarikçi sayısı: {created_supplier_count}"
        )
        self.stdout.write(
            "Demo satın alma talebi: "
            f"{purchase_request.request_number} "
            f"({'oluşturuldu' if purchase_request_created else 'zaten vardı'})"
        )
        self.stdout.write(
            "Demo talep kalemi: "
            f"{'oluşturuldu' if purchase_request_line_created else 'zaten vardı'}"
        )
        self.stdout.write("")
        self.stdout.write(
            "Not: Mevcut Maison Glauria kayıtları değiştirilmedi."
        )