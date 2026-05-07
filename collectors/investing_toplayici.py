"""
investing_toplayici.py — tr.investing.com hisse yorumlarini toplar
Calistir: python investing_toplayici.py

Next.js SSR ile sayfada gelen yorumlar cekilir.
Her hisse icin commentary + ana sayfa yorumlari alinir.
Tam pagination icin Playwright/Selenium gerekir (suan basit mod).
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sqlite3
import time
import random
import re
import json
from datetime import datetime
import cloudscraper
from database import DB_YOLU, HISSELER

# ─── Ayarlar ─────────────────────────────────────────────────────────────────

CALISTIRILACAK_HISSELER = list(HISSELER.keys())

HISSE_SLUGLAR = {
    "THYAO": "turk-hava-yollari",
    "GARAN": "garanti-bankasi",
    "KCHOL": "koc-holding",
    "EREGL": "eregli-demir-celik",
    "TUPRS": "tupras",
    "BIMAS": "bim-magazalar",
    "ASELS": "aselsan",
    "SAHOL": "sabanci-holding",
    "SISE":  "sise-cam",
    "PETKM": "petkim",
}

GECIKME_MIN = 3.0
GECIKME_MAX = 7.0
KAYNAK      = "INVESTING_FORUM"
BASE_URL    = "https://tr.investing.com"


# ─── Scraper ─────────────────────────────────────────────────────────────────

def scraper_olustur():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )


# ─── Yorum Cekme: SSR mod ────────────────────────────────────────────────────

def yorumlari_cek(scraper, slug: str) -> list[dict]:
    """
    __NEXT_DATA__ JSON blogundan forum yorumlarini cikarir.
    Commentary sayfasi ana sayfadan daha fazla yorum icerir (25 vs 10).
    """
    sonuclar = []
    for suffix in ["-commentary", ""]:
        url = f"{BASE_URL}/equities/{slug}{suffix}"
        try:
            r = scraper.get(url, timeout=40)
            if r.status_code != 200:
                continue
            m = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                r.text, re.DOTALL
            )
            if not m:
                continue
            data    = json.loads(m.group(1))
            forum   = data["props"]["pageProps"]["state"].get("forumStore", {})
            yorum_listesi = forum.get("comments", {}).get("_collection", [])

            for y in yorum_listesi:
                metin    = (y.get("text") or "").strip()
                tarih_h  = y.get("date", "")
                yorum_id = str(y.get("id", ""))
                if not metin or len(metin) < 10:
                    continue
                tarih = _tarih_ayristir(tarih_h)
                sonuclar.append({
                    "metin":     metin,
                    "tarih":     tarih,
                    "kaynak_id": yorum_id,
                })

        except Exception as e:
            print(f"  [{slug}{suffix}] Hata: {e}")

        time.sleep(random.uniform(GECIKME_MIN, GECIKME_MAX))

    # Duplikat temizle (kaynak_id bazli)
    goruldu = set()
    benzersiz = []
    for y in sonuclar:
        if y["kaynak_id"] not in goruldu:
            goruldu.add(y["kaynak_id"])
            benzersiz.append(y)
    return benzersiz


def _tarih_ayristir(ham: str) -> str:
    """
    Investing.com relative tarihlerini ('2 saat once', '3 gun once') bugunle isler.
    Mutlak tarih varsa parse eder.
    """
    if not ham:
        return str(datetime.today().date())
    ham_lower = ham.lower().strip()

    # Relative: "N saat/gun/hafta once"
    m = re.search(r"(\d+)\s*(saat|gun|g\.|hafta|ay|yil)", ham_lower)
    if m:
        n = int(m.group(1))
        birim = m.group(2)
        from datetime import timedelta
        delta_gun = {"saat": 0, "gun": n, "g.": n, "hafta": n*7, "ay": n*30, "yil": n*365}
        gun = delta_gun.get(birim, 0)
        return str((datetime.today() - timedelta(days=gun)).date())

    # Mutlak tarih
    for fmt in ("%d/%m/%Y %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ham[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(datetime.today().date())


# ─── Veritabani ──────────────────────────────────────────────────────────────

def yorumu_kaydet(conn, hisse_kodu, tarih, metin, kaynak_id) -> bool:
    c = conn.cursor()
    if kaynak_id:
        if c.execute("SELECT 1 FROM haberler WHERE kaynak=? AND baslik=?",
                     (KAYNAK, kaynak_id)).fetchone():
            return False
    else:
        if c.execute(
            "SELECT 1 FROM haberler WHERE hisse_kodu=? AND tarih=? AND metin=? AND kaynak=?",
            (hisse_kodu, tarih, metin, KAYNAK)
        ).fetchone():
            return False
    try:
        c.execute(
            "INSERT INTO haberler (hisse_kodu,tarih,baslik,metin,kaynak,duygu_skoru) "
            "VALUES (?,?,?,?,?,NULL)",
            (hisse_kodu, tarih, kaynak_id or metin[:60], metin, KAYNAK)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  [DB] {e}")
        return False


# ─── Hisse Isleme ────────────────────────────────────────────────────────────

def hisse_isle(scraper, hisse_kodu: str) -> int:
    slug = HISSE_SLUGLAR.get(hisse_kodu)
    if not slug:
        print(f"[{hisse_kodu}] slug tanimlanmamis.")
        return 0

    print(f"\n[{hisse_kodu}] {BASE_URL}/equities/{slug}")
    yorumlar = yorumlari_cek(scraper, slug)
    print(f"  {len(yorumlar)} benzersiz yorum bulundu.")

    if not yorumlar:
        return 0

    conn    = sqlite3.connect(DB_YOLU)
    eklenen = sum(
        yorumu_kaydet(conn, hisse_kodu, y["tarih"], y["metin"], y["kaynak_id"])
        for y in yorumlar
    )
    conn.close()
    print(f"  {eklenen} yeni yorum kaydedildi.")
    return eklenen


# ─── Ana Akis ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Investing.com/tr Yorum Toplayici (SSR modu)")
    print(f"Hisseler: {CALISTIRILACAK_HISSELER}")
    print("Not: Her hisse icin ~25-35 guncel yorum cekilir.")
    print("=" * 60)

    scraper = scraper_olustur()
    toplam  = 0

    for hisse in CALISTIRILACAK_HISSELER:
        toplam += hisse_isle(scraper, hisse)
        time.sleep(random.uniform(3, 6))

    print(f"\nToplam {toplam} yeni yorum eklendi.")
    print("BERT skorlama: python duygu_analizi.py")


if __name__ == "__main__":
    main()
