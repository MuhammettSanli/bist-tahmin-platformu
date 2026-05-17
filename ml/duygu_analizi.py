"""
duygu_analizi.py — BERT ile haberleri/tweetleri skorla, gunluk_duygu tablosunu doldur
Çalıştır: python duygu_analizi.py

Adımlar:
  1. duygu_skoru IS NULL olan haberler → BERT → güncelle
  2. duygu_skoru IS NULL olan tweetler → BERT → güncelle
  3. Her (hisse_kodu, tarih) için AGIRLIKLI ortalama skor → gunluk_duygu tablosuna yaz
     (Haberler × 2 agirlik, Tweetler × 1 agirlik)

Iyilestirmeler:
  - GPU destegi (varsa otomatik kullanir)
  - Dinamik batch boyutu (GPU bellegine gore)
  - Metin kalite filtresi (cok kisa / anlamsiz tweetleri atlar)
  - Agirlikli gunluk duygu ortalamasi (haberler daha güvenilir kaynak)
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sqlite3
import re
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from database import DB_YOLU

MODEL_ADI = "savasy/bert-base-turkish-sentiment-cased"

# GPU varsa buyuk batch; yoksa kucuk tut (bellek icin)
TOPLU_BOYUT_GPU = 64
TOPLU_BOYUT_CPU = 16

# Metin kalite filtresi
MIN_KELIME_SAYISI = 3    # En az 3 kelime olmali
MAX_TEKRAR_ORAN  = 0.6   # Tekrarlayan karakterlerin orani bu degerin altinda olmali

# Kaynak agirliklari (gunluk_duygu hesaplamasi icin)
AGIRLIK = {
    "haberler": 2.0,
    "tweetler": 1.0,
}


# ─── Metin Kalite Kontrolü ───────────────────────────────────────────────────

def metni_temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)         # URL
    metin = re.sub(r"@\w+", "", metin)            # Mention
    metin = re.sub(r"#(\w+)", r"\1", metin)       # # kaldir, kelimeyi birak
    metin = re.sub(r"[^\w\s.,!?;:'-]", " ", metin)  # Ozel karakterler
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


def metin_kaliteli_mi(metin: str) -> bool:
    """Cok kisa, bot komutu veya tekrarlayan icerikli metinleri filtreler."""
    if not metin:
        return False
    # Bot komutları: /akd, /analiz vb.
    if metin.lstrip().startswith("/"):
        return False
    kelimeler = metin.split()
    if len(kelimeler) < MIN_KELIME_SAYISI:
        return False
    # Tekrar orani kontrolu: tek bir karakter cok fazla tekrar ediyorsa atla
    for char in set(metin.lower()):
        if char.isalpha() and metin.lower().count(char) / len(metin) > MAX_TEKRAR_ORAN:
            return False
    return True


# ─── BERT ────────────────────────────────────────────────────────────────────

def model_yukle():
    print(f"BERT yukleniyor: {MODEL_ADI} ...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    toplu_boyut = TOPLU_BOYUT_GPU if device == "cuda" else TOPLU_BOYUT_CPU
    print(f"  Cihaz: {device} | Batch boyutu: {toplu_boyut}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ADI)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ADI)
    model.to(device)
    model.eval()
    print("  Model hazir.\n")
    return tokenizer, model, device, toplu_boyut


def batch_duygu_skoru(metinler: list[str], tokenizer, model, device: str) -> list[float]:
    """
    Bir liste metni tek seferde BERT'ten gecirir.
    Sonuc: her metin icin [-1, +1] araliginda float skor.
    """
    if not metinler:
        return []
    inputs = tokenizer(
        metinler,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=128,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=1)
    # pozitif - negatif
    skorlar = (probs[:, 1] - probs[:, 0]).cpu().tolist()
    return [round(s, 6) for s in skorlar]


# ─── Toplu Skorlama ───────────────────────────────────────────────────────────

def tabloyu_skorla(tablo: str, id_sutun: str, metin_sutun: str,
                   tokenizer, model, device: str, toplu_boyut: int) -> int:
    """
    Belirtilen tablodaki duygu_skoru NULL kayitlarini BERT ile gunceller.
    Kalitesiz metinlere 0.0 skoru verir (atlamak yerine isaret eder).
    Doner: guncellenen kayit sayisi.
    """
    conn = sqlite3.connect(DB_YOLU)
    c    = conn.cursor()
    c.execute(f"SELECT {id_sutun}, {metin_sutun} FROM {tablo} WHERE duygu_skoru IS NULL")
    satirlar = c.fetchall()

    if not satirlar:
        print(f"  [{tablo}] Skorlanacak kayit yok.")
        conn.close()
        return 0

    print(f"  [{tablo}] {len(satirlar)} kayit skorlanacak...")
    guncellenen = 0

    for i in range(0, len(satirlar), toplu_boyut):
        batch_satirlar = satirlar[i: i + toplu_boyut]
        ids     = [r[0] for r in batch_satirlar]
        metinler_ham = [r[1] or "" for r in batch_satirlar]

        # Temizle ve filtrele
        temiz_metinler = [metni_temizle(m) for m in metinler_ham]

        # Kaliteli metinlerin indekslerini bul
        kaliteli_idx = [j for j, m in enumerate(temiz_metinler) if metin_kaliteli_mi(m)]
        kaliteli_metinler = [temiz_metinler[j] for j in kaliteli_idx]

        # BERT'ten gecir (sadece kaliteli olanlar)
        if kaliteli_metinler:
            skorlar_kaliteli = batch_duygu_skoru(
                kaliteli_metinler, tokenizer, model, device
            )
        else:
            skorlar_kaliteli = []

        # Skorlari eslestir (kalitesiz olanlara 0.0)
        skor_haritasi = {}
        for idx_sirasi, j in enumerate(kaliteli_idx):
            skor_haritasi[j] = skorlar_kaliteli[idx_sirasi]

        for j, kayit_id in enumerate(ids):
            skor = skor_haritasi.get(j, 0.0)
            c.execute(
                f"UPDATE {tablo} SET duygu_skoru = ? WHERE {id_sutun} = ?",
                (skor, kayit_id),
            )
            guncellenen += 1

        conn.commit()
        bitti = min(i + toplu_boyut, len(satirlar))
        print(f"    {bitti}/{len(satirlar)} islendi "
              f"({len(kaliteli_idx)} kaliteli / {toplu_boyut} batch)...", end="\r")

    print(f"\n  [{tablo}] {guncellenen} kayit guncellendi.")
    conn.close()
    return guncellenen


# ─── Ağırlıklı Günlük Duygu ──────────────────────────────────────────────────

def gunluk_duygu_guncelle() -> int:
    """
    Her (hisse_kodu, tarih) icin haberler + tweetler tablosundan
    AGIRLIKLI ortalama duygu skoru hesaplar → gunluk_duygu tablosuna yazar.

    Haberler: agirlik=2 (daha guvenilir, editorial icerik)
    Tweetler: agirlik=1 (kalabalik ama gurultulu)
    """
    conn = sqlite3.connect(DB_YOLU)
    c    = conn.cursor()

    c.execute("""
        SELECT
            hisse_kodu,
            DATE(tarih) AS gun,
            SUM(duygu_skoru * agirlik) / SUM(agirlik) AS agirlikli_ort,
            COUNT(*)                                    AS sayi
        FROM (
            SELECT hisse_kodu, tarih, duygu_skoru, 2.0 AS agirlik
            FROM haberler
            WHERE duygu_skoru IS NOT NULL

            UNION ALL

            -- Bot tweet filtreleri:
            --   LENGTH < 20 : /akd asels, GARAN-akd verisi gibi kisa komutlar
            --   LIKE '/%'   : slash komutlari (LENGTH>=20 olsa bile)
            --   AKD/Gecersiz: bot echo mesajlari (goruntu istekleri, hata mesajlari)
            SELECT hisse_kodu, tarih, duygu_skoru, 1.0 AS agirlik
            FROM tweetler
            WHERE duygu_skoru IS NOT NULL
              AND LENGTH(metin) >= 20
              AND metin NOT LIKE '/%'
              AND metin NOT LIKE '%AKD Görüntüsü%'
              AND metin NOT LIKE '%Geçersiz hisse kodu%'
        )
        GROUP BY hisse_kodu, gun
        HAVING sayi >= 1
    """)
    satirlar = c.fetchall()

    n = 0
    for hisse_kodu, gun, ort_skor, sayi in satirlar:
        c.execute(
            """INSERT OR REPLACE INTO gunluk_duygu
               (hisse_kodu, tarih, ortalama_skor, kayit_sayisi)
               VALUES (?, ?, ?, ?)""",
            (hisse_kodu, gun, round(ort_skor, 6), sayi),
        )
        n += 1

    conn.commit()
    conn.close()
    print(f"  gunluk_duygu: {n} gun guncellendi.")
    return n


# ─── Ozet İstatistik ─────────────────────────────────────────────────────────

def ozet_yazdir():
    """Skorlama sonrasi veritabani istatistiklerini yazdirir."""
    conn = sqlite3.connect(DB_YOLU)
    c    = conn.cursor()

    print("\n  --- Veritabani Ozeti ---")
    for tablo in ("haberler", "tweetler"):
        c.execute(f"SELECT COUNT(*), COUNT(duygu_skoru) FROM {tablo}")
        toplam, skorlu = c.fetchone()
        print(f"  {tablo:12s}: {toplam:5d} kayit, {skorlu:5d} skorlu")

    c.execute("""
        SELECT hisse_kodu, COUNT(*) AS gun_sayisi,
               ROUND(AVG(ortalama_skor), 4) AS ort_skor
        FROM gunluk_duygu
        GROUP BY hisse_kodu
        ORDER BY ort_skor DESC
    """)
    rows = c.fetchall()
    if rows:
        print("\n  Hisse bazinda gunluk_duygu:")
        print(f"  {'Hisse':8s}  {'Gun':>5s}  {'Ort Skor':>10s}")
        print(f"  {'-'*8}  {'-'*5}  {'-'*10}")
        for hisse, gun, skor in rows:
            bar = "+" if skor > 0 else "-"
            print(f"  {hisse:8s}  {gun:5d}  {skor:+10.4f}  {bar * min(int(abs(skor)*20), 20)}")

    conn.close()


# ─── Ana Akış ────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("Duygu Analizi (GPU Destekli Batch + Agirlikli Ortalama)")
    print("=" * 55)

    tokenizer, model, device, toplu_boyut = model_yukle()

    print("1. Haberler skorlaniyor...")
    tabloyu_skorla("haberler", "id", "metin", tokenizer, model, device, toplu_boyut)

    print("\n2. Tweetler skorlaniyor...")
    tabloyu_skorla("tweetler", "id", "metin", tokenizer, model, device, toplu_boyut)

    print("\n3. Agirlikli gunluk duygu ortalamalari hesaplaniyor...")
    gunluk_duygu_guncelle()

    ozet_yazdir()
    print("\nDuygu analizi tamamlandi.")


if __name__ == "__main__":
    main()
