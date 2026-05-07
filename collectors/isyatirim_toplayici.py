"""
isyatirim_toplayici.py — Is Yatirim arastirma raporu basliklar + ozetler
Calistir: python collectors/isyatirim_toplayici.py

arastirma.isyatirim.com.tr/?s={TICKER} sayfasindan
analist raporu baslik ve ozetlerini toplar.
Kurumsal analist gorusleri — perakende yorumdan farkli perspektif.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import sqlite3
import time
import random
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup
from database import DB_YOLU, HISSELER

# ─── Ayarlar ─────────────────────────────────────────────────────────────────

KAYNAK      = "ISYATIRIM_ARASTIRMA"
BASE_URL    = "https://arastirma.isyatirim.com.tr"
GECIKME_MIN = 2.0
GECIKME_MAX = 4.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://arastirma.isyatirim.com.tr/",
}


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _tarih_ayristir(ham: str) -> str:
    if not ham:
        return str(datetime.today().date())
    ham = ham.strip()
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", ham)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ham)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d+)\s*(Ocak|Subat|Mart|Nisan|Mayis|Haziran|Temmuz|Agustos|Eylul|Ekim|Kasim|Aralik)",
                  ham, re.I)
    if m:
        return str(datetime.today().date())
    return str(datetime.today().date())


def _temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


# ─── Rapor Çekme ─────────────────────────────────────────────────────────────

def raporlari_cek(scraper, hisse_kodu: str) -> list[dict]:
    url = f"{BASE_URL}/?s={hisse_kodu}"
    sonuclar = []

    try:
        r = scraper.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")

        # Makale/rapor bloklari
        raporlar = (
            soup.select("article.post")
            or soup.select("div.post")
            or soup.select("article")
            or soup.find_all(class_=re.compile(r"post|article|report|rapor", re.I))
        )

        goruldu = set()
        for rapor in raporlar:
            # Baslik
            baslik_el = rapor.find(["h1", "h2", "h3", "h4"])
            if not baslik_el:
                baslik_el = rapor.find("a")
            baslik = _temizle(baslik_el.get_text(strip=True)) if baslik_el else ""
            if len(baslik) < 10:
                continue

            # Link (benzersizlik icin)
            link_el = rapor.find("a", href=True)
            link = link_el["href"] if link_el else ""
            if link and not link.startswith("http"):
                link = BASE_URL + link
            key = link or baslik[:80]
            if key in goruldu:
                continue
            goruldu.add(key)

            # Ozet metni
            ozet_el = rapor.find(["p", "div"], class_=re.compile(r"excerpt|summary|ozet|desc|entry"))
            ozet = ""
            if ozet_el:
                ozet = _temizle(ozet_el.get_text(strip=True))
            metin = f"{baslik}. {ozet}".strip(". ") if ozet else baslik
            if len(metin) < 10:
                continue

            # Tarih
            tarih_el = rapor.find(["time", "span", "div"],
                                   class_=re.compile(r"date|tarih|time|published"))
            tarih_str = ""
            if tarih_el:
                tarih_str = tarih_el.get("datetime", "") or tarih_el.get_text(strip=True)
            tarih = _tarih_ayristir(tarih_str)

            sonuclar.append({
                "baslik":    baslik[:120],
                "metin":     metin[:1000],
                "tarih":     tarih,
                "kaynak_id": key[:120],
            })

        print(f"    {len(sonuclar)} rapor bulundu.")

    except Exception as e:
        print(f"    [{hisse_kodu}] Hata: {e}")

    return sonuclar


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

def hisse_isle(scraper, hisse_kodu: str) -> int:
    print(f"\n[{hisse_kodu}] {BASE_URL}/?s={hisse_kodu}")
    raporlar = raporlari_cek(scraper, hisse_kodu)
    if not raporlar:
        return 0
    conn = sqlite3.connect(DB_YOLU)
    eklenen = sum(
        kaydet(conn, hisse_kodu, r["tarih"], r["baslik"], r["metin"], r["kaynak_id"])
        for r in raporlar
    )
    conn.close()
    print(f"  {eklenen} yeni kayit eklendi.")
    return eklenen


# ─── Ana Akış ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Is Yatirim Arastirma Raporu Toplayici")
    print(f"Hisseler: {list(HISSELER.keys())}")
    print("=" * 60)

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    toplam = 0
    for hisse in HISSELER:
        toplam += hisse_isle(scraper, hisse)
        time.sleep(random.uniform(GECIKME_MIN, GECIKME_MAX))

    print(f"\nToplam {toplam} yeni kayit eklendi.")
    print("BERT skorlama: python ml/duygu_analizi.py")


if __name__ == "__main__":
    main()
