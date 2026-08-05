from datetime import date

from apps.accounts.models import OrganizationMembership
from apps.hr.models import EmploymentAssignment


ENTERPRISE_DEPARTMENTS = [
    {
        "code": "TECH",
        "name": "Bilgi Teknolojileri",
    },
    {
        "code": "MKT",
        "name": "Pazarlama",
    },
    {
        "code": "CS",
        "name": "Müşteri Başarısı",
    },
    {
        "code": "LEGAL",
        "name": "Hukuk ve Uyum",
    },
]


ENTERPRISE_POSITIONS = [
    # Bilgi Teknolojileri
    {
        "code": "TECH-MGR",
        "department_code": "TECH",
        "title": "Bilgi Teknolojileri Müdürü",
    },
    {
        "code": "TECH-BE-SR",
        "department_code": "TECH",
        "title": "Kıdemli Backend Developer",
    },
    {
        "code": "TECH-BE",
        "department_code": "TECH",
        "title": "Backend Developer",
    },
    {
        "code": "TECH-FE",
        "department_code": "TECH",
        "title": "Frontend Developer",
    },
    {
        "code": "TECH-DEVOPS",
        "department_code": "TECH",
        "title": "DevOps Engineer",
    },
    {
        "code": "TECH-QA",
        "department_code": "TECH",
        "title": "QA Engineer",
    },

    # İnsan Kaynakları
    {
        "code": "HR-REC",
        "department_code": "HR",
        "title": "İşe Alım Uzmanı",
    },
    {
        "code": "HR-PAY",
        "department_code": "HR",
        "title": "Bordro ve Özlük Uzmanı",
    },

    # Finans
    {
        "code": "FIN-SR",
        "department_code": "FIN",
        "title": "Kıdemli Finans Uzmanı",
    },
    {
        "code": "FIN-ACC",
        "department_code": "FIN",
        "title": "Muhasebe Uzmanı",
    },
    {
        "code": "FIN-BUD",
        "department_code": "FIN",
        "title": "Bütçe ve Raporlama Uzmanı",
    },

    # Satın Alma
    {
        "code": "PUR-SR",
        "department_code": "PUR",
        "title": "Kıdemli Satın Alma Uzmanı",
    },
    {
        "code": "PUR-SPC",
        "department_code": "PUR",
        "title": "Satın Alma Uzmanı",
    },

    # Satış
    {
        "code": "SAL-AE",
        "department_code": "SAL",
        "title": "Müşteri Yöneticisi",
    },
    {
        "code": "SAL-SDR",
        "department_code": "SAL",
        "title": "Satış Geliştirme Uzmanı",
    },
    {
        "code": "SAL-OPS",
        "department_code": "SAL",
        "title": "Satış Operasyon Uzmanı",
    },

    # Operasyon
    {
        "code": "OPS-SR",
        "department_code": "OPS",
        "title": "Kıdemli Operasyon Uzmanı",
    },
    {
        "code": "OPS-SPC",
        "department_code": "OPS",
        "title": "Operasyon Uzmanı",
    },
    {
        "code": "OPS-WH",
        "department_code": "OPS",
        "title": "Depo ve Lojistik Uzmanı",
    },

    # Pazarlama
    {
        "code": "MKT-MGR",
        "department_code": "MKT",
        "title": "Pazarlama Müdürü",
    },
    {
        "code": "MKT-DIG",
        "department_code": "MKT",
        "title": "Dijital Pazarlama Uzmanı",
    },
    {
        "code": "MKT-CNT",
        "department_code": "MKT",
        "title": "İçerik ve Marka Uzmanı",
    },

    # Müşteri Başarısı
    {
        "code": "CS-MGR",
        "department_code": "CS",
        "title": "Müşteri Başarısı Müdürü",
    },
    {
        "code": "CS-SPC",
        "department_code": "CS",
        "title": "Müşteri Başarısı Uzmanı",
    },
    {
        "code": "CS-SUP",
        "department_code": "CS",
        "title": "Teknik Destek Uzmanı",
    },

    # Hukuk ve Uyum
    {
        "code": "LEGAL-MGR",
        "department_code": "LEGAL",
        "title": "Hukuk ve Uyum Müdürü",
    },
    {
        "code": "LEGAL-SPC",
        "department_code": "LEGAL",
        "title": "Hukuk ve Uyum Uzmanı",
    },
]


ENTERPRISE_EMPLOYEES = [
    # Yeni departman yöneticileri önce oluşturulur.
    {
        "username": "enterprise.tech.manager",
        "employee_number": "GLA-0008",
        "first_name": "Arda",
        "last_name": "Koç",
        "department_code": "TECH",
        "position_code": "TECH-MGR",
        "job_title": "Bilgi Teknolojileri Müdürü",
        "manager_username": "demo.ceo",
        "role": OrganizationMembership.Role.MANAGER,
        "is_department_manager": True,
        "hire_date": date(2023, 2, 6),
    },
    {
        "username": "enterprise.marketing.manager",
        "employee_number": "GLA-0009",
        "first_name": "Derya",
        "last_name": "Kurt",
        "department_code": "MKT",
        "position_code": "MKT-MGR",
        "job_title": "Pazarlama Müdürü",
        "manager_username": "demo.ceo",
        "role": OrganizationMembership.Role.MANAGER,
        "is_department_manager": True,
        "hire_date": date(2023, 4, 3),
    },
    {
        "username": "enterprise.cs.manager",
        "employee_number": "GLA-0010",
        "first_name": "Onur",
        "last_name": "Acar",
        "department_code": "CS",
        "position_code": "CS-MGR",
        "job_title": "Müşteri Başarısı Müdürü",
        "manager_username": "demo.ceo",
        "role": OrganizationMembership.Role.MANAGER,
        "is_department_manager": True,
        "hire_date": date(2023, 6, 5),
    },
    {
        "username": "enterprise.legal.manager",
        "employee_number": "GLA-0011",
        "first_name": "Zeynep",
        "last_name": "Eren",
        "department_code": "LEGAL",
        "position_code": "LEGAL-MGR",
        "job_title": "Hukuk ve Uyum Müdürü",
        "manager_username": "demo.ceo",
        "role": OrganizationMembership.Role.MANAGER,
        "is_department_manager": True,
        "hire_date": date(2023, 8, 7),
    },

    # Bilgi Teknolojileri
    {
        "username": "enterprise.tech.backend1",
        "employee_number": "GLA-0012",
        "first_name": "Berk",
        "last_name": "Özdemir",
        "department_code": "TECH",
        "position_code": "TECH-BE-SR",
        "job_title": "Kıdemli Backend Developer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2023, 10, 2),
    },
    {
        "username": "enterprise.tech.backend2",
        "employee_number": "GLA-0013",
        "first_name": "Melis",
        "last_name": "Yıldız",
        "department_code": "TECH",
        "position_code": "TECH-BE",
        "job_title": "Backend Developer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2024, 1, 15),
    },
    {
        "username": "enterprise.tech.backend3",
        "employee_number": "GLA-0014",
        "first_name": "Emir",
        "last_name": "Tunç",
        "department_code": "TECH",
        "position_code": "TECH-BE",
        "job_title": "Backend Developer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2024, 5, 6),
    },
    {
        "username": "enterprise.tech.frontend1",
        "employee_number": "GLA-0015",
        "first_name": "İrem",
        "last_name": "Çetin",
        "department_code": "TECH",
        "position_code": "TECH-FE",
        "job_title": "Frontend Developer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2024, 2, 19),
    },
    {
        "username": "enterprise.tech.frontend2",
        "employee_number": "GLA-0016",
        "first_name": "Oğuz",
        "last_name": "Aksoy",
        "department_code": "TECH",
        "position_code": "TECH-FE",
        "job_title": "Frontend Developer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2025, 1, 13),
    },
    {
        "username": "enterprise.tech.devops",
        "employee_number": "GLA-0017",
        "first_name": "Sarp",
        "last_name": "Kılıç",
        "department_code": "TECH",
        "position_code": "TECH-DEVOPS",
        "job_title": "DevOps Engineer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2024, 3, 11),
    },
    {
        "username": "enterprise.tech.qa",
        "employee_number": "GLA-0018",
        "first_name": "Ceren",
        "last_name": "Uslu",
        "department_code": "TECH",
        "position_code": "TECH-QA",
        "job_title": "QA Engineer",
        "manager_username": "enterprise.tech.manager",
        "hire_date": date(2025, 2, 3),
    },

    # İnsan Kaynakları
    {
        "username": "enterprise.hr.recruiter",
        "employee_number": "GLA-0019",
        "first_name": "Naz",
        "last_name": "Şen",
        "department_code": "HR",
        "position_code": "HR-REC",
        "job_title": "İşe Alım Uzmanı",
        "manager_username": "demo.hr.manager",
        "hire_date": date(2024, 4, 1),
        "permissions": [
            OrganizationMembership.Permission.ACCESS_HR,
        ],
    },
    {
        "username": "enterprise.hr.payroll",
        "employee_number": "GLA-0020",
        "first_name": "Tolga",
        "last_name": "Keskin",
        "department_code": "HR",
        "position_code": "HR-PAY",
        "job_title": "Bordro ve Özlük Uzmanı",
        "manager_username": "demo.hr.manager",
        "hire_date": date(2024, 9, 2),
        "permissions": [
            OrganizationMembership.Permission.ACCESS_HR,
        ],
    },

    # Finans
    {
        "username": "enterprise.finance.senior",
        "employee_number": "GLA-0021",
        "first_name": "Gökçe",
        "last_name": "Bozkurt",
        "department_code": "FIN",
        "position_code": "FIN-SR",
        "job_title": "Kıdemli Finans Uzmanı",
        "manager_username": "demo.finance.manager",
        "hire_date": date(2023, 11, 6),
    },
    {
        "username": "enterprise.finance.accountant1",
        "employee_number": "GLA-0022",
        "first_name": "Umut",
        "last_name": "Yalçın",
        "department_code": "FIN",
        "position_code": "FIN-ACC",
        "job_title": "Muhasebe Uzmanı",
        "manager_username": "demo.finance.manager",
        "hire_date": date(2024, 6, 3),
    },
    {
        "username": "enterprise.finance.accountant2",
        "employee_number": "GLA-0023",
        "first_name": "Eylül",
        "last_name": "Ateş",
        "department_code": "FIN",
        "position_code": "FIN-ACC",
        "job_title": "Muhasebe Uzmanı",
        "manager_username": "demo.finance.manager",
        "hire_date": date(2025, 2, 17),
    },
    {
        "username": "enterprise.finance.budget",
        "employee_number": "GLA-0024",
        "first_name": "Kaan",
        "last_name": "Polat",
        "department_code": "FIN",
        "position_code": "FIN-BUD",
        "job_title": "Bütçe ve Raporlama Uzmanı",
        "manager_username": "demo.finance.manager",
        "hire_date": date(2024, 8, 5),
    },

    # Satın Alma
    {
        "username": "enterprise.purchasing.senior",
        "employee_number": "GLA-0025",
        "first_name": "Pelin",
        "last_name": "Sönmez",
        "department_code": "PUR",
        "position_code": "PUR-SR",
        "job_title": "Kıdemli Satın Alma Uzmanı",
        "manager_username": "demo.purchasing.manager",
        "hire_date": date(2023, 12, 4),
    },
    {
        "username": "enterprise.purchasing.specialist1",
        "employee_number": "GLA-0026",
        "first_name": "Baran",
        "last_name": "Özer",
        "department_code": "PUR",
        "position_code": "PUR-SPC",
        "job_title": "Satın Alma Uzmanı",
        "manager_username": "demo.purchasing.manager",
        "hire_date": date(2024, 7, 1),
    },
    {
        "username": "enterprise.purchasing.specialist2",
        "employee_number": "GLA-0027",
        "first_name": "Aslı",
        "last_name": "Doğan",
        "department_code": "PUR",
        "position_code": "PUR-SPC",
        "job_title": "Satın Alma Uzmanı",
        "manager_username": "demo.purchasing.manager",
        "hire_date": date(2025, 3, 3),
    },

    # Satış
    {
        "username": "enterprise.sales.ae1",
        "employee_number": "GLA-0028",
        "first_name": "Kerem",
        "last_name": "Işık",
        "department_code": "SAL",
        "position_code": "SAL-AE",
        "job_title": "Müşteri Yöneticisi",
        "manager_username": "demo.sales.manager",
        "hire_date": date(2023, 10, 9),
    },
    {
        "username": "enterprise.sales.ae2",
        "employee_number": "GLA-0029",
        "first_name": "Sude",
        "last_name": "Kara",
        "department_code": "SAL",
        "position_code": "SAL-AE",
        "job_title": "Müşteri Yöneticisi",
        "manager_username": "demo.sales.manager",
        "hire_date": date(2024, 1, 8),
    },
    {
        "username": "enterprise.sales.ae3",
        "employee_number": "GLA-0030",
        "first_name": "Mete",
        "last_name": "Güler",
        "department_code": "SAL",
        "position_code": "SAL-AE",
        "job_title": "Müşteri Yöneticisi",
        "manager_username": "demo.sales.manager",
        "hire_date": date(2024, 5, 13),
    },
    {
        "username": "enterprise.sales.sdr1",
        "employee_number": "GLA-0031",
        "first_name": "Yağmur",
        "last_name": "Ergin",
        "department_code": "SAL",
        "position_code": "SAL-SDR",
        "job_title": "Satış Geliştirme Uzmanı",
        "manager_username": "demo.sales.manager",
        "hire_date": date(2024, 9, 9),
    },
    {
        "username": "enterprise.sales.sdr2",
        "employee_number": "GLA-0032",
        "first_name": "Alp",
        "last_name": "Karaca",
        "department_code": "SAL",
        "position_code": "SAL-SDR",
        "job_title": "Satış Geliştirme Uzmanı",
        "manager_username": "demo.sales.manager",
        "hire_date": date(2025, 1, 6),
    },
    {
        "username": "enterprise.sales.operations",
        "employee_number": "GLA-0033",
        "first_name": "Ada",
        "last_name": "Korkmaz",
        "department_code": "SAL",
        "position_code": "SAL-OPS",
        "job_title": "Satış Operasyon Uzmanı",
        "manager_username": "demo.sales.manager",
        "hire_date": date(2024, 3, 18),
    },

    # Operasyon
    {
        "username": "enterprise.operations.senior",
        "employee_number": "GLA-0034",
        "first_name": "Eren",
        "last_name": "Bulut",
        "department_code": "OPS",
        "position_code": "OPS-SR",
        "job_title": "Kıdemli Operasyon Uzmanı",
        "manager_username": "demo.operations.manager",
        "hire_date": date(2023, 11, 13),
    },
    {
        "username": "enterprise.operations.specialist1",
        "employee_number": "GLA-0035",
        "first_name": "Defne",
        "last_name": "Tekin",
        "department_code": "OPS",
        "position_code": "OPS-SPC",
        "job_title": "Operasyon Uzmanı",
        "manager_username": "demo.operations.manager",
        "hire_date": date(2024, 2, 5),
    },
    {
        "username": "enterprise.operations.specialist2",
        "employee_number": "GLA-0036",
        "first_name": "Bora",
        "last_name": "Kaplan",
        "department_code": "OPS",
        "position_code": "OPS-SPC",
        "job_title": "Operasyon Uzmanı",
        "manager_username": "demo.operations.manager",
        "hire_date": date(2024, 8, 12),
    },
    {
        "username": "enterprise.operations.warehouse1",
        "employee_number": "GLA-0037",
        "first_name": "Nehir",
        "last_name": "Tan",
        "department_code": "OPS",
        "position_code": "OPS-WH",
        "job_title": "Depo ve Lojistik Uzmanı",
        "manager_username": "demo.operations.manager",
        "hire_date": date(2024, 10, 7),
    },
    {
        "username": "enterprise.operations.warehouse2",
        "employee_number": "GLA-0038",
        "first_name": "Batuhan",
        "last_name": "Çakır",
        "department_code": "OPS",
        "position_code": "OPS-WH",
        "job_title": "Depo ve Lojistik Uzmanı",
        "manager_username": "demo.operations.manager",
        "hire_date": date(2025, 2, 10),
    },

    # Pazarlama
    {
        "username": "enterprise.marketing.digital1",
        "employee_number": "GLA-0039",
        "first_name": "Lara",
        "last_name": "Köse",
        "department_code": "MKT",
        "position_code": "MKT-DIG",
        "job_title": "Dijital Pazarlama Uzmanı",
        "manager_username": "enterprise.marketing.manager",
        "hire_date": date(2024, 1, 22),
    },
    {
        "username": "enterprise.marketing.digital2",
        "employee_number": "GLA-0040",
        "first_name": "Rüzgar",
        "last_name": "Kaya",
        "department_code": "MKT",
        "position_code": "MKT-DIG",
        "job_title": "Dijital Pazarlama Uzmanı",
        "manager_username": "enterprise.marketing.manager",
        "hire_date": date(2025, 1, 20),
    },
    {
        "username": "enterprise.marketing.content1",
        "employee_number": "GLA-0041",
        "first_name": "Mina",
        "last_name": "Önal",
        "department_code": "MKT",
        "position_code": "MKT-CNT",
        "job_title": "İçerik ve Marka Uzmanı",
        "manager_username": "enterprise.marketing.manager",
        "hire_date": date(2024, 6, 17),
    },
    {
        "username": "enterprise.marketing.content2",
        "employee_number": "GLA-0042",
        "first_name": "Doruk",
        "last_name": "Çınar",
        "department_code": "MKT",
        "position_code": "MKT-CNT",
        "job_title": "İçerik ve Marka Uzmanı",
        "manager_username": "enterprise.marketing.manager",
        "hire_date": date(2025, 3, 10),
    },

    # Müşteri Başarısı
    {
        "username": "enterprise.cs.specialist1",
        "employee_number": "GLA-0043",
        "first_name": "Nil",
        "last_name": "Akın",
        "department_code": "CS",
        "position_code": "CS-SPC",
        "job_title": "Müşteri Başarısı Uzmanı",
        "manager_username": "enterprise.cs.manager",
        "hire_date": date(2024, 2, 12),
    },
    {
        "username": "enterprise.cs.specialist2",
        "employee_number": "GLA-0044",
        "first_name": "Fırat",
        "last_name": "Sezer",
        "department_code": "CS",
        "position_code": "CS-SPC",
        "job_title": "Müşteri Başarısı Uzmanı",
        "manager_username": "enterprise.cs.manager",
        "hire_date": date(2024, 7, 15),
    },
    {
        "username": "enterprise.cs.support1",
        "employee_number": "GLA-0045",
        "first_name": "İlayda",
        "last_name": "Aydın",
        "department_code": "CS",
        "position_code": "CS-SUP",
        "job_title": "Teknik Destek Uzmanı",
        "manager_username": "enterprise.cs.manager",
        "hire_date": date(2024, 11, 4),
    },
    {
        "username": "enterprise.cs.support2",
        "employee_number": "GLA-0046",
        "first_name": "Kuzey",
        "last_name": "Er",
        "department_code": "CS",
        "position_code": "CS-SUP",
        "job_title": "Teknik Destek Uzmanı",
        "manager_username": "enterprise.cs.manager",
        "hire_date": date(2025, 2, 24),
    },

    # Hukuk ve Uyum
    {
        "username": "enterprise.legal.specialist1",
        "employee_number": "GLA-0047",
        "first_name": "Serra",
        "last_name": "Yüce",
        "department_code": "LEGAL",
        "position_code": "LEGAL-SPC",
        "job_title": "Hukuk ve Uyum Uzmanı",
        "manager_username": "enterprise.legal.manager",
        "hire_date": date(2024, 3, 4),
    },
    {
        "username": "enterprise.legal.specialist2",
        "employee_number": "GLA-0048",
        "first_name": "Tuna",
        "last_name": "Gündüz",
        "department_code": "LEGAL",
        "position_code": "LEGAL-SPC",
        "job_title": "Hukuk ve Uyum Uzmanı",
        "manager_username": "enterprise.legal.manager",
        "hire_date": date(2025, 1, 27),
    },
]


def employee_permissions(employee_data):
    return employee_data.get("permissions", [])


def employee_role(employee_data):
    return employee_data.get(
        "role",
        OrganizationMembership.Role.MEMBER,
    )


def employee_employment_type(employee_data):
    return employee_data.get(
        "employment_type",
        EmploymentAssignment.EmploymentType.FULL_TIME,
    )
