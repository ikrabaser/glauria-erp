# Gloauria ERP

# Glauria ERP Sistem Mimarisi

## 1. Projenin Amacı

Glauria ERP; kozmetik üretimi yapan bir işletmenin satın alma, stok,
lot izlenebilirliği, formülasyon, üretim, kalite kontrol, satış,
faturalandırma ve müşteri ilişkileri süreçlerini tek sistem üzerinden
yönetmesini sağlayan kurumsal kaynak planlama yazılımıdır.

Sistem yalnızca kayıt tutan bağımsız CRUD ekranlarından oluşmayacaktır.
Bütün modüller ortak iş süreçleri üzerinden birbirine bağlı çalışacaktır.

---

## 2. Mimari Yaklaşım

Glauria ERP, modüler monolit mimarisiyle geliştirilecektir.

Tek bir Django projesi içinde çalışan sistem, iş alanlarına göre ayrı
Django uygulamalarına bölünecektir.

Bu yaklaşımın tercih edilme nedenleri:

- Merkezi veri tutarlılığı sağlaması
- Modüllerin birbirleriyle güvenli biçimde iletişim kurabilmesi
- Mikroservislere göre daha kolay geliştirilmesi ve dağıtılması
- Küçük geliştirme ekibi için yönetilebilir olması
- İleride ihtiyaç duyulursa belirli modüllerin ayrıştırılabilmesi

---

## 3. Katmanlı Yapı

Sistem dört ana katmandan oluşacaktır.

### 3.1 Sunum Katmanı

Kullanıcının doğrudan etkileşim kurduğu katmandır.

Kullanılacak teknolojiler:

- HTML5
- CSS3
- Bootstrap 5
- JavaScript
- Django Template Engine
- Chart.js

Görevleri:

- Dashboard ekranlarını göstermek
- Formları ve tabloları sunmak
- Kullanıcı etkileşimlerini yönetmek
- Responsive arayüz sağlamak
- Grafik ve raporları görselleştirmek

### 3.2 Uygulama Katmanı

İş süreçlerinin koordine edildiği katmandır.

Örnek görevler:

- Satın alma önerisi oluşturmak
- Üretim ihtiyaçlarını hesaplamak
- Stok rezervasyonu yapmak
- FEFO kurallarına göre lot seçmek
- Fatura onay sürecini yürütmek
- Yetki ve onay kontrollerini gerçekleştirmek

Karmaşık iş mantığı doğrudan view dosyalarında tutulmayacaktır.
İş kuralları service katmanında uygulanacaktır.

### 3.3 Domain Katmanı

ERP sisteminin temel iş modellerini içerir.

Örnek domain varlıkları:

- Company
- User
- Supplier
- Customer
- Product
- Material
- Warehouse
- Lot
- StockMovement
- PurchaseOrder
- ProductionOrder
- QualityInspection
- SalesOrder
- Invoice

### 3.4 Altyapı Katmanı

Sistemin teknik servislerini içerir.

- PostgreSQL
- Redis
- Celery
- Gunicorn
- NGINX
- Docker
- Sentry
- Prometheus
- Grafana
- OpenAI API
- pgvector

---

## 4. Ana İş Modülleri

Glauria ERP aşağıdaki ana modüllerden oluşacaktır.

1. Satın Alma ve Tedarikçi Yönetimi
2. Depo, Stok ve Lot Yönetimi
3. Ürün, Formülasyon ve BOM Yönetimi
4. Üretim Planlama ve Üretim Emirleri
5. Kalite Kontrol Yönetimi
6. Raf Ömrü ve Son Kullanma Tarihi Yönetimi
7. Satış, Sipariş, Sevkiyat ve Faturalandırma
8. CRM ve Müşteri Şikâyetleri
9. Raporlama ve Dashboard
10. Aura AI Asistan
11. Kullanıcı, Rol ve Yetki Yönetimi
12. Audit Log ve Bildirim Yönetimi

---

## 5. Django Uygulama Yapısı

Planlanan uygulama yapısı:

```text
apps/
├── core/
├── accounts/
├── organizations/
├── audit/
├── dashboard/
├── catalog/
├── inventory/
├── procurement/
├── production/
├── quality/
├── sales/
├── crm/
├── finance/
├── documents/
├── notifications/
├── reporting/
└── ai_assistant/