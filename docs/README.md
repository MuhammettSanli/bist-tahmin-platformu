# BIST Borsa Tahmin Platformu

> Finansal veriler ve BERT duygu analizi birleştirilerek LSTM ile hisse senedi fiyat yönü tahmini yapan hibrit yapay zeka platformu.

---

## Proje Özeti

Bu platform, Borsa İstanbul (BIST100) hisselerinin **bir sonraki günkü fiyat yönünü** (Yükseliş / Düşüş) tahmin eder. Tahmin iki ayrı veri akışını birleştirir:

- **Finansal veri** — geçmiş fiyat, hacim ve teknik göstergeler (RSI, SMA, MACD)
- **Duygu verisi** — KAP bildirimleri, finans haberleri ve Twitter/X tweetlerinden BERT ile üretilen günlük duygu skoru

Hibrit yaklaşımın değeri, **Model Karşılaştırma Paneli** üzerinden görsel olarak ölçülür: sadece finansal model ile duygu dahil modelin doğruluk farkı doğrudan gösterilir.

---

## Mimari

```
┌─────────────────────────────────────────────────────────────┐
│                      Dış Veri Kaynakları                    │
│  Yahoo Finance    KAP (kap.org.tr)    Twitter/X             │
└────────┬──────────────────┬───────────────┬─────────────────┘
         │                  │               │
         ▼                  ▼               ▼
  veri_cekici.py    haber_toplayici.py  tweet_toplayici.py
  (OHLCV)          (BeautifulSoup)     (twscrape + BERT)
         │                  │               │
         └──────────────────┴───────────────┘
                            │
                            ▼
                       borsa.db (SQLite)
               ┌───────────────────────────┐
               │  hisseler                 │
               │  gunluk_fiyatlar          │
               │  haberler                 │
               │  tweetler                 │
               │  gunluk_duygu  ◄──────────┼── duygu_analizi.py
               └───────────────────────────┘   (BERT toplu skorlama)
                            │
                            ▼
                     model_egitimi.py
              ┌─────────────────────────────┐
              │  Model A: Sadece Finansal   │ → accuracy, F1
              │  Model B: Finansal + Duygu  │ → accuracy, F1
              └─────────────────────────────┘
                            │
                     models/*.keras
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
| Veri Toplama | `yfinance` | BIST OHLCV verisi (5 yıl) |
| Veri Toplama | `BeautifulSoup` + `requests` | KAP bildirimleri, finans haberleri |
| Veri Toplama | `twscrape` | Twitter/X tweet toplama |
| NLP | `transformers` — `savasy/bert-base-turkish-sentiment-cased` | Türkçe duygu analizi |
| Veritabanı | `SQLite` | Yerel, hafif, geliştirme dostu |
| ML Modeli | `TensorFlow / Keras` — LSTM | Zaman serisi sınıflandırma |
| Özellik Mühendisliği | `pandas_ta` | RSI, SMA_20, MACD |
| Backend | `Flask` | REST API |
| Frontend | `Plotly.js` | Candlestick grafik, zoom/pan |

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
- **Pencere:** Son 14 günlük veri → yarının yönü
- **Finansal veri:** 2020'den bugüne (Yahoo Finance)
- **Tweet verisi:** 2024-01-01'den bugüne

---

## Veritabanı Şeması

```
hisseler          → hisse_kodu (PK), sirket_adi
gunluk_fiyatlar   → hisse_kodu, tarih, acilis, kapanis, yuksek, dusuk, hacim
haberler          → hisse_kodu, tarih, baslik, metin, kaynak, duygu_skoru
tweetler          → tweet_id (UNIQUE), hisse_kodu, tarih, metin, duygu_skoru
gunluk_duygu      → hisse_kodu, tarih, ortalama_skor, kayit_sayisi
```

`gunluk_duygu` → haberler + tweetlerin günlük ortalaması → LSTM'e giren duygu özelliği

---

## API Endpoint'leri

| Endpoint | Açıklama |
|---|---|
| `GET /` | Web arayüzü |
| `GET /api/hisseler` | 10 hisse listesi |
| `GET /api/fiyat/<hisse>` | Son 90 günlük OHLCV |
| `GET /api/duygu/<hisse>` | Son 90 günlük duygu skoru |
| `GET /api/tahmin/<hisse>` | LSTM tahmini (yön + güven %) |
| `GET /api/karsilastirma/<hisse>` | Finansal model vs Hibrit model metrikleri |

---

## Kurulum ve Çalıştırma

### 1. Bağımlılıkları Kur

```bash
pip install -r requirements.txt
```

### 2. Veritabanını Başlat

```bash
python database.py
```

### 3. Finansal Veri İndir

```bash
python veri_cekici.py
# → borsa.db/gunluk_fiyatlar dolar (10 hisse × 5 yıl ≈ 12 500 satır)
```

### 4. Haber ve KAP Verisi Topla

```bash
python haber_toplayici.py
```

### 5. Twitter/X Verisi Topla

```bash
# İlk kurulum (bir kez)
echo "kullanici:sifre:email:email_sifresi" > accounts.txt
python -m twscrape add_accounts accounts.txt
python -m twscrape login_accounts

# Tweet topla
python tweet_toplayici.py
```

### 6. BERT ile Duygu Skoru Hesapla

```bash
python duygu_analizi.py
# → haberler ve tweetler skorlanır, gunluk_duygu tablosu güncellenir
```

### 7. LSTM Modellerini Eğit

```bash
python model_egitimi.py
# → her hisse için 2 model: finansal + hibrit
# → models/<HISSE>_metriks.json karşılaştırma verisi üretilir
```

### 8. Web Uygulamasını Başlat

```bash
python app.py
# → http://localhost:5000
```

---

## Proje Durumu

| Modül | Durum |
|---|---|
| `database.py` | Tamamlandı |
| `veri_cekici.py` | Tamamlandı |
| `haber_toplayici.py` | Tamamlandı |
| `tweet_toplayici.py` | Tamamlandı |
| `duygu_analizi.py` | Tamamlandı |
| `model_egitimi.py` | Tamamlandı |
| `app.py` | Tamamlandı |
| `templates/index.html` | Tamamlandı |
| Uçtan uca test | Bekliyor |

---

## Proje Yapısı

```
Agents/
├── database.py              # Adım 1 — DB şeması ve başlangıç verisi
├── veri_cekici.py           # Adım 2 — yfinance finansal veri
├── haber_toplayici.py       # Adım 3 — KAP + haber scraping
├── tweet_toplayici.py       # Adım 4 — twscrape + anında BERT skorlama
├── duygu_analizi.py         # Adım 5 — toplu BERT + gunluk_duygu güncelle
├── model_egitimi.py         # Adım 6 — LSTM (finansal vs hibrit)
├── app.py                   # Adım 7 — Flask REST API
├── templates/
│   └── index.html           # Adım 8 — Plotly.js web arayüzü
├── static/
│   ├── style.css
│   └── script.js
├── models/                  # Eğitilen modeller (.keras, .pkl, _metriks.json)
├── requirements.txt
├── .gitignore
└── borsa.db                 # Yerel SQLite (git'e dahil değil)
```

---

## Akademik Referanslar

1. Fischer & Krauss (2018) — *Deep learning with LSTM for financial market predictions*
2. Devlin et al. (2018) — *BERT: Pre-training of Deep Bidirectional Transformers*
3. Bollen et al. (2011) — *Twitter mood predicts the stock market*
4. Araci (2019) — *FinBERT: Financial sentiment analysis with pre-trained language models*
5. Jiang & Zeng (2023) — *Predicting Stock Prices with FinBERT-LSTM*

---

*Süleyman Demirel Üniversitesi — Bilgisayar Mühendisliği — Tasarım-I/II Dersi*
