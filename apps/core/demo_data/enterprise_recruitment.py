from datetime import date, timedelta
from decimal import Decimal

from apps.hr.models import Candidate, JobRequisition


FIRST_NAMES = [
    "Alara", "Ali", "Bade", "Batu", "Beril", "Cem", "Damla",
    "Deniz", "Dilan", "Ece", "Efe", "Elif", "Emre", "Esra",
    "Gizem", "Hakan", "Hazal", "İpek", "Kıvanç", "Merve",
    "Murat", "Nisa", "Okan", "Öykü", "Pınar", "Rana",
]

LAST_NAMES = [
    "Akbaş", "Akıncı", "Alkan", "Arı", "Aslan", "Avcı",
    "Başar", "Bayram", "Bilgin", "Candan", "Çalışkan", "Çelik",
    "Duman", "Erdoğan", "Eroğlu", "Güneş", "Karaman", "Koçak",
    "Mutlu", "Öz", "Sağlam", "Şener", "Taş", "Tekin",
    "Toprak", "Yavuz",
]

CANDIDATE_TITLES = [
    "Backend Developer",
    "Frontend Developer",
    "Full Stack Developer",
    "DevOps Engineer",
    "QA Engineer",
    "Finans Uzmanı",
    "Muhasebe Uzmanı",
    "Satış Uzmanı",
    "Satış Operasyon Uzmanı",
    "Satın Alma Uzmanı",
    "İnsan Kaynakları Uzmanı",
    "İşe Alım Uzmanı",
    "Dijital Pazarlama Uzmanı",
    "Müşteri Başarısı Uzmanı",
    "Teknik Destek Uzmanı",
    "Operasyon Uzmanı",
]

CANDIDATE_COMPANIES = [
    "Aster Teknoloji",
    "Bosphorus Digital",
    "CoreNova Yazılım",
    "Delta İş Çözümleri",
    "Eksen Danışmanlık",
    "Fora Teknoloji",
    "Kuzey Sistem",
    "Luna Bilişim",
    "Mavi Bulut",
    "NovaWorks",
    "Orion Teknoloji",
    "Pera Yazılım",
    "Rota Finans",
]

CANDIDATE_SOURCES = [
    Candidate.Source.CAREER_SITE,
    Candidate.Source.LINKEDIN,
    Candidate.Source.REFERRAL,
    Candidate.Source.AGENCY,
    Candidate.Source.UNIVERSITY,
    Candidate.Source.MANUAL,
]


def build_enterprise_candidates():
    candidates = []

    for index in range(192):
        first_name_index = index % len(FIRST_NAMES)
        last_name_index = (
            index // len(FIRST_NAMES)
        ) % len(LAST_NAMES)

        first_name = FIRST_NAMES[first_name_index]
        last_name = LAST_NAMES[last_name_index]

        sequence = index + 9

        candidates.append(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": (
                    f"enterprise.candidate{sequence:03d}"
                    "@candidate.glauria.local"
                ),
                "phone": (
                    f"+90 555 2{sequence:02d} "
                    f"{(sequence * 13) % 100:02d} "
                    f"{(sequence * 29) % 100:02d}"
                ),
                "linkedin_url": (
                    "https://www.linkedin.com/in/"
                    f"glauria-demo-candidate-{sequence:03d}"
                ),
                "portfolio_url": (
                    "https://github.com/"
                    f"glauria-demo-candidate-{sequence:03d}"
                    if index % 3 == 0
                    else ""
                ),
                "source": CANDIDATE_SOURCES[
                    index % len(CANDIDATE_SOURCES)
                ],
                "current_title": CANDIDATE_TITLES[
                    index % len(CANDIDATE_TITLES)
                ],
                "current_company": CANDIDATE_COMPANIES[
                    index % len(CANDIDATE_COMPANIES)
                ],
                "years_of_experience": Decimal(
                    str(round((index % 15) * 0.5 + 0.5, 1))
                ),
                "notes": (
                    "Glauria Enterprise Demo aday havuzu için "
                    "oluşturulmuş tamamen kurgusal aday kaydıdır."
                ),
            }
        )

    return candidates


ENTERPRISE_JOB_REQUISITIONS = [
    {
        "number": "REQ-2026-005",
        "title": "Kıdemli Backend Developer",
        "department": "TECH",
        "position": "TECH-BE-SR",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-006",
        "title": "Backend Developer",
        "department": "TECH",
        "position": "TECH-BE",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 3,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-007",
        "title": "Frontend Developer",
        "department": "TECH",
        "position": "TECH-FE",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-008",
        "title": "DevOps Engineer",
        "department": "TECH",
        "position": "TECH-DEVOPS",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-009",
        "title": "QA Engineer",
        "department": "TECH",
        "position": "TECH-QA",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-010",
        "title": "İşe Alım Uzmanı",
        "department": "HR",
        "position": "HR-REC",
        "manager": "demo.hr.manager",
        "recruiter": "demo.hr.specialist",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-011",
        "title": "Bordro ve Özlük Uzmanı",
        "department": "HR",
        "position": "HR-PAY",
        "manager": "demo.hr.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.REPLACEMENT,
    },
    {
        "number": "REQ-2026-012",
        "title": "Muhasebe Uzmanı",
        "department": "FIN",
        "position": "FIN-ACC",
        "manager": "demo.finance.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-013",
        "title": "Bütçe ve Raporlama Uzmanı",
        "department": "FIN",
        "position": "FIN-BUD",
        "manager": "demo.finance.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-014",
        "title": "Satın Alma Uzmanı",
        "department": "PUR",
        "position": "PUR-SPC",
        "manager": "demo.purchasing.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-015",
        "title": "Müşteri Yöneticisi",
        "department": "SAL",
        "position": "SAL-AE",
        "manager": "demo.sales.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 3,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-016",
        "title": "Satış Geliştirme Uzmanı",
        "department": "SAL",
        "position": "SAL-SDR",
        "manager": "demo.sales.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-017",
        "title": "Operasyon Uzmanı",
        "department": "OPS",
        "position": "OPS-SPC",
        "manager": "demo.operations.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-018",
        "title": "Dijital Pazarlama Uzmanı",
        "department": "MKT",
        "position": "MKT-DIG",
        "manager": "enterprise.marketing.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-019",
        "title": "Müşteri Başarısı Uzmanı",
        "department": "CS",
        "position": "CS-SPC",
        "manager": "enterprise.cs.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 3,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-020",
        "title": "Hukuk ve Uyum Uzmanı",
        "department": "LEGAL",
        "position": "LEGAL-SPC",
        "manager": "enterprise.legal.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-021",
        "title": "Full Stack Developer",
        "department": "TECH",
        "position": "TECH-BE",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-022",
        "title": "Junior Backend Developer",
        "department": "TECH",
        "position": "TECH-BE",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-023",
        "title": "Teknik Destek Uzmanı",
        "department": "CS",
        "position": "CS-SUP",
        "manager": "enterprise.cs.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-024",
        "title": "Kıdemli Finans Uzmanı",
        "department": "FIN",
        "position": "FIN-SR",
        "manager": "demo.finance.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.REPLACEMENT,
    },
    {
        "number": "REQ-2026-025",
        "title": "Kıdemli Satın Alma Uzmanı",
        "department": "PUR",
        "position": "PUR-SR",
        "manager": "demo.purchasing.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-026",
        "title": "Satış Operasyon Uzmanı",
        "department": "SAL",
        "position": "SAL-OPS",
        "manager": "demo.sales.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.NEW_POSITION,
    },
    {
        "number": "REQ-2026-027",
        "title": "Kıdemli Operasyon Uzmanı",
        "department": "OPS",
        "position": "OPS-SR",
        "manager": "demo.operations.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 1,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.REPLACEMENT,
    },
    {
        "number": "REQ-2026-028",
        "title": "İçerik ve Marka Uzmanı",
        "department": "MKT",
        "position": "MKT-CNT",
        "manager": "enterprise.marketing.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-029",
        "title": "Kıdemli Müşteri Başarısı Uzmanı",
        "department": "CS",
        "position": "CS-SPC",
        "manager": "enterprise.cs.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 2,
        "employment_type": JobRequisition.EmploymentType.FULL_TIME,
        "reason": JobRequisition.OpeningReason.GROWTH,
    },
    {
        "number": "REQ-2026-030",
        "title": "Uzun Dönem Yazılım Stajyeri",
        "department": "TECH",
        "position": "TECH-BE",
        "manager": "enterprise.tech.manager",
        "recruiter": "enterprise.hr.recruiter",
        "headcount": 3,
        "employment_type": JobRequisition.EmploymentType.INTERN,
        "reason": JobRequisition.OpeningReason.TEMPORARY_NEED,
    },

]


# İlan bazındaki toplam başvuru hedefleri.
# REQ-2026-001..004 hafif demo tarafından oluşturulur ve toplam 10
# başvuru taşır. Aşağıdaki enterprise hedefleri toplam 990 başvurudur.
ENTERPRISE_APPLICATION_TARGETS = {
    "REQ-2026-005": 77,  # Kıdemli Backend Developer
    "REQ-2026-006": 70,  # Backend Developer
    "REQ-2026-007": 61,  # Frontend Developer
    "REQ-2026-008": 47,  # DevOps Engineer
    "REQ-2026-009": 55,  # QA Engineer
    "REQ-2026-010": 27,  # İşe Alım Uzmanı
    "REQ-2026-011": 21,  # Bordro ve Özlük Uzmanı
    "REQ-2026-012": 31,  # Muhasebe Uzmanı
    "REQ-2026-013": 24,  # Bütçe ve Raporlama Uzmanı
    "REQ-2026-014": 28,  # Satın Alma Uzmanı
    "REQ-2026-015": 50,  # Müşteri Yöneticisi
    "REQ-2026-016": 43,  # Satış Geliştirme Uzmanı
    "REQ-2026-017": 34,  # Operasyon Uzmanı
    "REQ-2026-018": 38,  # Dijital Pazarlama Uzmanı
    "REQ-2026-019": 40,  # Müşteri Başarısı Uzmanı
    "REQ-2026-020": 16,  # Hukuk ve Uyum Uzmanı
    "REQ-2026-021": 64,  # Full Stack Developer
    "REQ-2026-022": 48,  # Junior Backend Developer
    "REQ-2026-023": 29,  # Teknik Destek Uzmanı
    "REQ-2026-024": 25,  # Kıdemli Finans Uzmanı
    "REQ-2026-025": 23,  # Kıdemli Satın Alma Uzmanı
    "REQ-2026-026": 36,  # Satış Operasyon Uzmanı
    "REQ-2026-027": 20,  # Kıdemli Operasyon Uzmanı
    "REQ-2026-028": 32,  # İçerik ve Marka Uzmanı
    "REQ-2026-029": 27,  # Kıdemli Müşteri Başarısı Uzmanı
    "REQ-2026-030": 24,  # Uzun Dönem Yazılım Stajyeri
}


STAGE_DISTRIBUTION = [
    "applied",
    "applied",
    "applied",
    "screening",
    "screening",
    "phone_screen",
    "interview",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "rejected",
    "withdrawn",
]


def requisition_deadline(index):
    return date(
        2026,
        9 + (index % 3),
        10 + (index % 15),
    )


def requisition_target_date(index):
    return requisition_deadline(index) + timedelta(days=30)
