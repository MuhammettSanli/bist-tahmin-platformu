# BIST Borsa Tahmin Platformu

> Finansal veriler ve BERT duygu analizi birleştirilerek XGBoost / LightGBM ile hisse senedi fiyat yönü tahmini yapan hibrit yapay zeka platformu.

---

## Proje Özeti

Bu platform, Borsa İstanbul (BIST100) hisselerinin **bir sonraki günkü fiyat yönünü** (Yükseliş / Düşüş) tahmin eder. Tahmin iki ayrı veri akışını birleştirir:

- **Finansal veri** — geçmiş fiyat, hacim ve teknik göstergeler (RSI, SMA, MACD, Bollinger vb.)
- **Duygu verisi** — KAP bildirimleri, finans haberleri ve Telegram kanallarından BERT ile üretilen günlük duygu skoru

Hibrit yaklaşımın değeri, **Model Karşılaştırma Paneli** üzerinden görsel olarak ölçülür: sadece finansal model ile duygu dahil modelin walk-forward doğruluk farkı doğrudan gösterilir.

---

## Mimari

```
┌─────────────────────────────────────────────────────────────────┐
│                        Dış Veri Kaynakları                      │
│  Yahoo Finance   KAP (pykap)   Google News   Telegram Kanalları │
└────────┬─────────────┬──────────────┬───────────────┬───────────┘
         │             │              │               │
         ▼             ▼              ▼               ▼
  veri_cekici.py  kap_toplayici  haber_toplayici  telegram_toplayici
  (OHLCV+Makro)   (Bildirimler)  (RSS + Scraping) (Telethon)
         │             │              │               │
         └─────────────┴──────────────┴───────────────┘
                                 │
                                 ▼
                            borsa.db (SQLite)
                  ┌────────────────────────────────┐
                  │  gunluk_fiyatlar               │
                  │  makro_veriler                 │
                  │  haberler                      │
                  │  tweetler                      │
                  │  gunluk_duygu  ◄───────────────┼── duygu_analizi.py
                  └────────────────────────────────┘   (BERT toplu skorlama)
                                 │
                                 ▼
                          features.py
                    (Ortak özellik mühendisliği)
                                 │
                                 ▼
                         model_egitimi.py
               ┌──────────────────────────────────┐
               │  Model A: Sadece Finansal         │ → WF accuracy, F1
               │  Model B: Finansal + Duygu (Hibrit)│ → WF accuracy, F1
               │  Seçim: WF'de ≥%1 iyileşme varsa │
               │         hibrit, yoksa finansal    │
               └──────────────────────────────────┘
                                 │
                          models/*.pkl
                          models/*_metriks.json
                                 │
                                 ▼
                             app.py (Flask)
                                 │
                          ┌──────┴──────┐
                          │  API (JSON) │
                          └──────┬──────┘
                                 │
                         templates/index.html
                         (Plotly.js — candlestick)
```

---

## Teknoloji Yığını

| Katman | Teknoloji | Amaç |
|---|---|---|
| Veri Toplama | `yfinance` | BIST OHLCV + makro verisi (5 yıl) |
| Veri Toplama | `BeautifulSoup`, `cloudscraper` | Haber siteleri, forum scraping |
| Veri Toplama | `Telethon` | Telegram kanal mesajları |
| Veri Toplama | `pykap` | KAP resmi bildirimleri |
| NLP | `transformers` — `savasy/bert-base-turkish-sentiment-cased` | Türkçe duygu analizi |
| Veritabanı | `SQLite` | Yerel, hafif, geliştirme dostu |
| ML Modeli | `XGBoost`, `LightGBM` | İkili sınıflandırma (Yükseliş/Düşüş) |
| Validasyon | Walk-Forward (3 katlı temporal) | Veri sızıntısı olmayan test |
| Özellik Mühendisliği | `pandas_ta` | RSI, SMA, MACD, Bollinger, ATR vb. |
| Backend | `Flask`, `APScheduler` | REST API, günlük pipeline |
| Frontend | `Plotly.js` | Candlestick grafik, duygu skoru |

---

## Kapsam

### Takip Edilen Hisseler (BIST100 — Yüksek Hacimli 10 Hisse)

| Kod | Şirket |
|---|---|
| GARAN | Garanti BBVA |
| THYAO | Türk Hava Yolları |
| KCHOL | Koç Holding |
| EREGL | Ereğli Demir Çelik |
| TUPRS | Tüpraş |
| BIMAS | BİM Mağazaları |
| ASELS | Aselsan |
| SAHOL | Sabancı Holding |
| SISE | Şişe Cam |
| PETKM | Petkim |

### Tahmin Hedefi

- **Sınıflandırma:** Yükseliş (`1`) / Düşüş (`0`)
- **Eşik:** ±%0.5 veya ±%1.0 (hisse bazlı optimize edilir)
- **Finansal veri:** 2021'den bugüne (Yahoo Finance)
- **Duygu verisi:** 2022'den bugüne (haber + Telegram)

---

## Model Mimarisi

### Özellik Grupları

**Finansal özellikler (her hisse):**
RSI(14), SMA(20), SMA(50), MACD, Bollinger Bantları, ATR, Stokastik %K, ROC, Hacim Oranı, Yüksek-Düşük Farkı

**Makro özellikler:**
BIST100 getirisi, USD/TRY getirisi, Brent petrol, Altın, EUR/TRY

**Hisse bazlı ek makro (sektöre özgü):**
- EREGL: HRC çelik + demir cevheri getirisi
- PETKM: Doğalgaz + petrokimya sektör proxy
- KCHOL: İştirak hisse getirileri (TUPRS, FROTO, TOASO, YKBNK)
- GARAN/SAHOL: TCMB faiz oranı ve MPC karar değişimi

**Duygu özellikleri (hibrit modelde ek olarak):**
Tweet duygu skoru, haber duygu skoru, 7 günlük momentum, kaynak sayısı, kaynak konsensus, standart sapma

**Lag özellikleri:** 1, 2, 3, 5, 10 günlük gecikmeler

### Model Seçim Kriteri

Her hisse için finansal ve hibrit model ayrı eğitilir. Hibrit model walk-forward doğruluğu finansal modeli ≥%1 geçiyorsa hibrit seçilir; aksi hâlde finansal model üretimde kullanılır.

---

## Validasyon Metodolojisi

```
Walk-Forward (Temporal Cross-Validation):

Kat 1: Eğitim 2021-2023 → Test 2023H2
Kat 2: Eğitim 2021-2024 → Test 2024H2
Kat 3: Eğitim 2021-2025 → Test 2025H2+

WF Doğruluk = 3 katın ortalaması

HoldOut: Ekim 2025 → Nisan 2026 (bağımsız test seti)
```

---

## Duygu Analizi Pipeline

```
Ham metin (haber / tweet)
        │
        ▼
metni_temizle()  ←── URL, mention, özel karakter temizleme
        │
        ▼
metin_kaliteli_mi()  ←── Min 3 kelime, slash komut filtresi
        │
        ▼
BERT (savasy/bert-base-turkish-sentiment-cased)
        │
        ▼
Skor: [-1.0, +1.0]
        │
        ▼
gunluk_duygu  ←── Haberler ×2 + Tweetler ×1 ağırlıklı ortalama
```

**Gürültü filtreleri (features.py):**
- INVESTING_FORUM: Echo effect filtresi (önceki gün fiyatını yansıtır)
- EKSISOZLUK: Genel hisseler için filtrelenir (EREGL istisnası)
- KAP Faaliyet Raporu: Şablon yasal dil filtresi (ASELS istisnası)
- GNEWS Teknik Analiz: Mynet Finans şablon yazıları filtresi
- Bot tweet filtresi: Kısa mesajlar, slash komutları, bot echo'ları

---

## Veritabanı Şeması

```
gunluk_fiyatlar  → hisse_kodu, tarih, acilis, kapanis, yuksek, dusuk, hacim
makro_veriler    → tarih, bist100, usdtry, petrol, altin, celik_hrc,
                   demir_cevheri, dogalgaz, petrokimya, tuprs_hisse,
                   froto, toaso, ykbnk, eurtry, tcmb_faiz
haberler         → hisse_kodu, tarih, baslik, metin, kaynak, duygu_skoru
tweetler         → tweet_id (UNIQUE), hisse_kodu, tarih, metin, duygu_skoru
gunluk_duygu     → hisse_kodu, tarih, ortalama_skor, kayit_sayisi
```

---

## API Endpoint'leri

| Endpoint | Açıklama |
|---|---|
| `GET /` | Web arayüzü |
| `GET /api/hisseler` | 10 hisse listesi |
| `GET /api/fiyat/<hisse>` | Son 90 günlük OHLCV |
| `GET /api/duygu/<hisse>` | Son 90 günlük duygu skoru |
| `GET /api/tahmin/<hisse>` | XGBoost/LightGBM tahmini (yön + güven %) |
| `GET /api/karsilastirma/<hisse>` | Finansal model vs Hibrit model metrikleri |
| `GET /api/tum_hisseler_ozet` | Tüm hisseler WF + HoldOut doğruluk tablosu |
| `GET /api/backtest/<hisse>` | Strateji backtest sonuçları |

---

## Kurulum ve Çalıştırma

### 1. Bağımlılıkları Kur

```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenlerini Ayarla

```bash
cp .env.example .env
# .env dosyasını düzenle
```

### 3. Veritabanını Başlat

```bash
python database.py
```

### 4. Pipeline'ı Çalıştır

```bash
python pipeline.py
```

### 5. Web Uygulamasını Başlat

```bash
python app.py
# → http://localhost:5000
```

---

## Proje Yapısı

```
├── app.py                    # Flask API
├── database.py               # SQLite şeması
├── features.py               # Ortak özellik mühendisliği
├── pipeline.py               # Günlük veri + model pipeline
├── model_utils.py            # Kalibreli model wrapper
├── ml/
│   ├── model_egitimi.py      # XGBoost/LightGBM eğitim + walk-forward
│   ├── duygu_analizi.py      # BERT toplu skorlama
│   └── backtest.py           # Strateji backtest motoru
├── collectors/
│   ├── veri_cekici.py        # yfinance OHLCV + makro
│   ├── haber_toplayici.py    # Google News RSS + haber siteleri
│   ├── telegram_toplayici.py # Telethon kanal mesajları
│   ├── kap_toplayici.py      # KAP bildirimleri (pykap)
│   ├── eksisozluk_toplayici.py
│   ├── investing_toplayici.py
│   ├── mynet_toplayici.py
│   ├── hissenet_toplayici.py
│   ├── bigpara_toplayici.py
│   └── isyatirim_toplayici.py
├── models/                   # Eğitilen modeller (.pkl, _metriks.json)
├── data/                     # SQLite veritabanı (borsa.db)
├── static/                   # CSS + JS
├── templates/                # HTML şablonları
├── tests/                    # Birim testleri
└── .github/workflows/        # GitHub Actions günlük pipeline
```

---

## Akademik Referanslar

1. Fischer & Krauss (2018) — *Deep learning with LSTM for financial market predictions*
2. Devlin et al. (2018) — *BERT: Pre-training of Deep Bidirectional Transformers*
3. Bollen et al. (2011) — *Twitter mood predicts the stock market*
4. Araci (2019) — *FinBERT: Financial sentiment analysis with pre-trained language models*
5. Chen & Guestrin (2016) — *XGBoost: A Scalable Tree Boosting System*
6. Ke et al. (2017) — *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*

---

*Süleyman Demirel Üniversitesi — Bilgisayar Mühendisliği — Bitirme Tezi*

> **Not:** Bu platform yatırım tavsiyesi değildir. Araştırma ve eğitim amaçlıdır.
