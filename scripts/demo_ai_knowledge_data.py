from django.contrib.auth import get_user_model

from apps.ai_core.models import AIKnowledgeDocument
from apps.ai_core.services import index_knowledge_document
from apps.organizations.models import Company


COMPANY_NAME = "Glauria Demo A.Ş."
OWNER_USERNAME = "ikra"

company = Company.objects.get(name=COMPANY_NAME)
owner = get_user_model().objects.get(username=OWNER_USERNAME)


KNOWLEDGE_DOCUMENTS = [
    {
        "document_type": AIKnowledgeDocument.DocumentType.HR_POLICY,
        "title": "Glauria İzin ve Devamsızlık Politikası",
        "source_reference": "policy://hr/leave-and-absence",
        "metadata": {
            "department": "human_resources",
            "language": "tr",
            "version": "1.0",
        },
        "content_text": """
Glauria İzin ve Devamsızlık Politikası

Çalışanlar yıllık izin, mazeret izni, hastalık izni ve ücretsiz izin
taleplerini İnsan Kaynakları modülündeki izin yönetimi ekranından
oluşturur.

İzin talebinde izin türü, başlangıç tarihi, bitiş tarihi ve açıklama
alanları doldurulmalıdır. Talep oluşturulduğunda sistem çalışanın izin
bakiyesini kontrol eder. Yetersiz izin bakiyesi bulunan talepler normal
onay sürecine alınmaz.

İlk onay, çalışanın aktif birincil atamasındaki doğrudan yöneticisi
tarafından yapılır. Şirket politikasına göre gerekli durumlarda İnsan
Kaynakları birimi ikinci kontrolü gerçekleştirir.

Onaylanan izinler çalışanın izin bakiyesinden düşülür ve ilgili tarihler
personel devam kayıtlarında izinli olarak değerlendirilir.

Reddedilen taleplerde yönetici veya İnsan Kaynakları birimi açıklama
girmelidir. Çalışan, reddedilen talebi güncelleyerek yeniden
gönderebilir.

Hastalık izninde destekleyici sağlık belgesi istenebilir. Mazeret ve
ücretsiz izinlerde açıklama alanının doldurulması zorunludur.

İzinli çalışanların bilgileri yalnızca yetkili yöneticiler ve İnsan
Kaynakları kullanıcıları tarafından görüntülenebilir.
""".strip(),
    },
    {
        "document_type": AIKnowledgeDocument.DocumentType.FINANCE_POLICY,
        "title": "Glauria Finans Tahsilat ve Vade Politikası",
        "source_reference": "policy://finance/collection-and-due-date",
        "metadata": {
            "department": "finance",
            "language": "tr",
            "version": "1.0",
        },
        "content_text": """
Glauria Finans Tahsilat ve Vade Politikası

Müşteri faturaları düzenlenirken fatura tarihi, vade tarihi, para
birimi, müşteri cari hesabı ve toplam tutar doğrulanmalıdır.

Vadesi yaklaşan faturalar finans ekranındaki tahsilat takibinde
gösterilir. Finans ekibi vade tarihinden önce müşteriyle iletişime
geçerek ödeme planını teyit eder.

Vadesi geçen faturalar gecikmiş alacak olarak değerlendirilir.
Gecikmiş faturalar için müşteri cari hesabı, açık fatura toplamı,
gerçekleşen tahsilatlar ve kalan bakiye birlikte incelenmelidir.

Kısmi tahsilat yapıldığında fatura durumu kısmi ödendi olarak
güncellenir. Kalan tutar ayrıca takip edilmeye devam eder.

Fatura toplamının tamamı tahsil edildiğinde durum ödendi olarak
işaretlenir. İptal edilen faturalar tahsilat hesaplamalarına dahil
edilmez.

Müşteriyle yeni bir ödeme planı oluşturulması gerekiyorsa taksit
tarihleri, taksit tutarları ve para birimi açıkça belirtilmelidir.
Finansal kararlar yalnızca sistemdeki güncel cari hesap ve işlem
verileri üzerinden verilmelidir.

Yetkisiz kullanıcılar başka şirketlerin cari hesaplarını, faturalarını
ve ödeme planlarını görüntüleyemez.
""".strip(),
    },
    {
        "document_type": AIKnowledgeDocument.DocumentType.ERP_HELP,
        "title": "Glauria Satın Alma ve Bütçe Onay Prosedürü",
        "source_reference": "help://purchasing/request-to-invoice",
        "metadata": {
            "module": "purchasing",
            "language": "tr",
            "version": "1.0",
        },
        "content_text": """
Glauria Satın Alma ve Bütçe Onay Prosedürü

Satın alma süreci bir satın alma talebiyle başlar. Talepte başlık, para
birimi, ihtiyaç tarihi, açıklama ve en az bir talep kalemi bulunmalıdır.

Her talep kalemi bir bütçe kontrol hesabına bağlanır. Kalemde açıklama,
miktar, birim fiyat ve ihtiyaç tarihi belirtilir. Sistem planlanan
tutarı miktar ile birim fiyat üzerinden hesaplar.

Talep taslak durumunda hazırlanır ve yetkili kullanıcı tarafından onaya
gönderilir. Bütçe kontrolü başarısız olan veya gerekli alanları eksik
olan talepler siparişe dönüştürülemez.

Onaylanan satın alma talebi uygun tedarikçi seçilerek satın alma
siparişine dönüştürülür. Sipariş tedarikçiye gönderilir ve tedarikçi
onayı takip edilir.

Ürün veya hizmet teslim edildiğinde sipariş kalemleri için teslim alma
kaydı oluşturulur. Kısmi teslimatlarda yalnızca teslim edilen miktar
kaydedilir ve sipariş kısmi teslim alındı durumuna geçer.

Tedarikçi faturası yalnızca teslimatı başlamış satın alma siparişleri
için oluşturulabilir. Fatura kalemleri teslim alınan sipariş
kalemleriyle ilişkilendirilir.

Fatura onaylandıktan sonra finansal borç ve ödeme süreci başlar.
Talep, sipariş, teslim alma ve fatura kayıtları denetlenebilir bir
işlem zinciri olarak korunur.
""".strip(),
    },
    {
        "document_type": AIKnowledgeDocument.DocumentType.PRODUCT_DOCUMENT,
        "title": "Glauria Kritik Stok ve Yeniden Sipariş Politikası",
        "source_reference": "policy://inventory/reorder-and-critical-stock",
        "metadata": {
            "module": "inventory",
            "language": "tr",
            "version": "1.0",
        },
        "content_text": """
Glauria Kritik Stok ve Yeniden Sipariş Politikası

Her aktif ürün için yeniden sipariş seviyesi tanımlanabilir. Bir ürünün
kullanılabilir stok miktarı, eldeki toplam miktardan rezerve edilmiş
miktarın çıkarılmasıyla hesaplanır.

Kullanılabilir stok miktarı yeniden sipariş seviyesine eşit veya bu
seviyenin altına düştüğünde ürün kritik stok olarak değerlendirilir.

Karantina, bloke veya kullanım dışı durumdaki stok lotları kullanılabilir
stok hesaplamasına dahil edilmez.

Kritik stok oluştuğunda stok yöneticisi ürünün güncel talep durumunu,
açık satış siparişlerini, üretim ihtiyaçlarını ve mevcut satın alma
siparişlerini birlikte değerlendirmelidir.

Yeni satın alma talebi oluşturulmadan önce aynı ürün için açık bir
satın alma talebi veya bekleyen satın alma siparişi olup olmadığı
kontrol edilmelidir.

Hammadde ve ambalaj ürünlerinde aktif ürün reçetelerindeki ihtiyaçlar da
yeniden sipariş kararına dahil edilmelidir.

Stok hareketleri lot ve depo bazında izlenir. Şirketler arası stok
verileri birleştirilemez. Kullanıcı yalnızca erişim yetkisi bulunan
şirket ve depo kayıtlarını görüntüleyebilir.
""".strip(),
    },
    {
        "document_type": AIKnowledgeDocument.DocumentType.ERP_HELP,
        "title": "Glauria ERP Kurumsal Kullanım Rehberi",
        "source_reference": "help://erp/general-usage",
        "metadata": {
            "module": "core",
            "language": "tr",
            "version": "1.0",
        },
        "content_text": """
Glauria ERP Kurumsal Kullanım Rehberi

Glauria ERP; CRM, satış, satın alma, stok, üretim, finans, insan
kaynakları ve yapay zekâ modüllerini tek çalışma alanında birleştirir.

Kullanıcıların görebildiği veriler aktif şirket üyeliği, rol, şube,
departman ve modül yetkileriyle sınırlandırılır. Bir kullanıcının başka
bir şirkete ait kayıtları görmesine izin verilmez.

CRM modülü müşteri kayıtlarını ve satış fırsatlarını yönetir. Satış
modülü teklif, satış siparişi ve müşteri faturası süreçlerini takip
eder.

Satın alma modülü talep, bütçe kontrolü, tedarikçi, sipariş, teslim alma
ve tedarikçi faturası süreçlerini kapsar.

Stok modülü ürün, depo, stok lotu ve stok hareketlerini yönetir. Üretim
modülü satış siparişlerinden oluşan üretim emirlerini ve ürün
reçetelerini takip eder.

Finans modülü cari hesap, banka ve kasa hesapları, nakit akışı, ödeme
planları, bütçe ve finansal hareketleri yönetir.

İnsan Kaynakları modülü personel, pozisyon, atama, izin, devam,
performans ve işe alım süreçlerini içerir.

Glauria AI yalnızca kullanıcının erişebildiği modüllerdeki salt okunur
araçları kullanır. Canlı ERP kayıtları ile bilgi tabanı içeriği
çeliştiğinde güncel ERP verisi esas alınır.
""".strip(),
    },
]


documents = []

for item in KNOWLEDGE_DOCUMENTS:
    document, _ = AIKnowledgeDocument.objects.update_or_create(
        company=company,
        source_reference=item["source_reference"],
        defaults={
            "created_by": owner,
            "document_type": item["document_type"],
            "source_type": AIKnowledgeDocument.SourceType.MANUAL,
            "title": item["title"],
            "content_text": item["content_text"],
            "metadata": item["metadata"],
        },
    )
    documents.append(document)


print()
print("=" * 72)
print("KNOWLEDGE BASE DOKÜMANLARI HAZIRLANDI")
print("=" * 72)

successful_count = 0
failed_count = 0

for document in documents:
    print()
    print(f"İndeksleniyor: {document.title}")

    try:
        result = index_knowledge_document(
            document=document,
            requested_by=owner,
        )

        successful_count += 1

        print(
            "  Durum:",
            (
                "mevcut indeks kullanıldı"
                if result.reused_existing_index
                else "yeni indeks oluşturuldu"
            ),
        )
        print("  Chunk sayısı:", result.chunk_count)
        print("  Embedding modeli:", result.embedding_model)

    except Exception as error:
        failed_count += 1
        print("  HATA:", str(error))


print()
print("=" * 72)
print("KNOWLEDGE BASE İNDEKSLEME ÖZETİ")
print("=" * 72)
print("Doküman:", len(documents))
print("Başarılı:", successful_count)
print("Başarısız:", failed_count)
print(
    "İndekslenmiş doküman:",
    AIKnowledgeDocument.objects.filter(
        company=company,
        status=AIKnowledgeDocument.Status.INDEXED,
    ).count(),
)
print(
    "Toplam chunk:",
    sum(
        document.chunks.count()
        for document in documents
    ),
)
print("=" * 72)
