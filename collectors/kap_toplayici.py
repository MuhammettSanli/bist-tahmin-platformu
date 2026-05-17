"""
kap_toplayici.py — KAP (Kamuyu Aydinlatma Platformu) bildirim toplama
Calistir: python collectors/kap_toplayici.py

pykap kutuphanesi ile her hisse icin resmi KAP bildirimlerini cekar.
Faaliyet Raporlari (FAR) ozet metinleri BERT duygu analizine gonder.

pykap kurulum: pip install pykap
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import sqlite3
import time
import random
import re
from datetime import datetime
from database import DB_YOLU, HISSELER

try:
    import pykap
except ImportError:
    print("HATA: pykap kurulu degil. Kurmak icin: pip install pykap")
    _sys.exit(1)

# ─── Ayarlar ─────────────────────────────────────────────────────────────────

KAYNAK           = "KAP"
BILDIRIM_TIPLERI = ["FAR", "UNV"]   # FAR=Faaliyet Raporu, UNV=Unvanli
GECIKME_MIN      = 1.5
GECIKME_MAX      = 3.5


# ─── Tarih Ayrıştırma ───��────────────────────────────────────────────────────

def _tarih_ayristir(ham: str) -> str:
    """KAP tarih formati: '29.04.2026 18:21:07'"""
    if not ham:
        return str(datetime.today().date())
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", ham)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return str(datetime.today().date())


# ─── Bildirim Çekme ───────────────────────────────────────────────────────────

def bildirimleri_cek(hisse_kodu: str) -> list[dict]:
    try:
        company = pykap.BISTCompany(hisse_kodu)
    except Exception as e:
        print(f"  [{hisse_kodu}] Sirket bulunamadi: {e}")
        return []

    sonuclar = []
    for tip in BILDIRIM_TIPLERI:
        try:
            bildirimler = company.get_disclosures(disclosure_type=tip)
            for b in bildirimler:
                ozet = (b.get("summary") or "").strip()
                baslik = (b.get("title") or tip).strip()
                tarih = _tarih_ayristir(b.get("publishDate", ""))
                disclosure_id = b.get("disclosureId", "")

                metin = f"{baslik}. {ozet}".strip(". ")
                if len(metin) < 15:
                    continue

                sonuclar.append({
                    "baslik":    baslik[:120],
                    "metin":     metin[:1000],
                    "tarih":     tarih,
                    "kaynak_id": disclosure_id or metin[:80],
                })
            print(f"    {tip}: {len(bildirimler)} bildirim")
        except Exception as e:
            print(f"    {tip} hata: {e}")
        time.sleep(random.uniform(0.5, 1.5))

    # Duplikat temizle
    goruldu, benzersiz = set(), []
    for b in sonuclar:
        if b["kaynak_id"] not in goruldu:
            goruldu.add(b["kaynak_id"])
            benzersiz.append(b)
    return benzersiz


# ─── Veritabanı ──────────────────────────────────────────────────────────────

def kaydet(conn, hisse_kodu, tarih, baslik, metin, kaynak_id) -> bool:
    c = conn.cursor()
    if c.execute("SELECT 1 FROM haberler WHERE kaynak=? AND baslik=?",
                 (KAYNAK, kaynak_id[:120])).fetchone():
        return False
    try:
        c.execute(
            "INSERT INTO haberler (hisse_kodu,tarih,baslik,metin,kaynak,duygu_skoru) "
            "VALUES (?,?,?,?,?,NULL)",
            (hisse_kodu, tarih, baslik[:120], metin, KAYNAK)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  [DB] {e}")
        return False


# ─── Hisse İşleme ────────────────────────────────────────────────────────────

def hisse_isle(hisse_kodu: str) -> int:
    print(f"\n[{hisse_kodu}] KAP bildirimleri cekiliyor...")
    bildirimler = bildirimleri_cek(hisse_kodu)
    print(f"  {len(bildirimler)} benzersiz bildirim.")
    if not bildirimler:
        return 0
    conn = sqlite3.connect(DB_YOLU)
    eklenen = sum(
        kaydet(conn, hisse_kodu, b["tarih"], b["baslik"], b["metin"], b["kaynak_id"])
        for b in bildirimler
    )
    conn.close()
    print(f"  {eklenen} yeni kayit eklendi.")
    return eklenen


# ─── Ana Akış ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("KAP Bildirim Toplayici (pykap)")
    print(f"Hisseler: {list(HISSELER.keys())}")
    print(f"Bildirim tipleri: {BILDIRIM_TIPLERI}")
    print("=" * 60)

    toplam = 0
    for hisse in HISSELER:
        toplam += hisse_isle(hisse)
        time.sleep(random.uniform(GECIKME_MIN, GECIKME_MAX))

    print(f"\nToplam {toplam} yeni kayit eklendi.")
    print("BERT skorlama: python ml/duygu_analizi.py")


if __name__ == "__main__":
    main()
