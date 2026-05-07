"""
hissenet_toplayici.py — Hisse.net hisse haberleri toplama
Calistir: python collectors/hissenet_toplayici.py

Her hisse icin hisse.net/borsa/hisseler/{slug} sayfasindaki
haber basliklarini ve KAP haberlerini toplar.
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

KAYNAK      = "HISSENET"
BASE_URL    = "https://www.hisse.net"
GECIKME_MIN = 2.5
GECIKME_MAX = 5.0

HISSE_SLUGLAR = {
    "THYAO": "thyao-turk-hava-yollari",
    "GARAN": "garan-garanti-bbva",
    "KCHOL": "kchol-koc-holding",
    "EREGL": "eregl-eregli-demir-celik",
    "TUPRS": "tuprs-tupras",
    "BIMAS": "bimas-bim-magazalari",
    "ASELS": "asels-aselsan",
    "SAHOL": "sahol-sabanci-holding",
    "SISE":  "sise-sise-cam",
    "PETKM": "petkm-petkim",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.hisse.net/",
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
    m = re.search(r"(\d+)\s*(dakika|saat|gün|gun|hafta|ay)", ham.lower())
    if m:
        n, birim = int(m.group(1)), m.group(2)
        delta = {"dakika": 0, "saat": 0, "gün": n, "gun": n, "hafta": n*7, "ay": n*30}
        return str((datetime.today() - timedelta(days=delta.get(birim, 0))).date())
    return str(datetime.today().date())


def _temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


# ─── Haber Çekme ─────────────────────────────────────────────────────────────

def haberleri_cek(scraper, hisse_kodu: str, slug: str) -> list[dict]:
    sonuclar = []
    url = f"{BASE_URL}/borsa/hisseler/{slug}"

    try:
        r = scraper.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print(f"    HTTP {r.status_code} — {url}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")

        # Ana haber blokları: div.news-item > a.item-title
        news_items = soup.select("div.news-item")
        bulunan = 0
        goruldu_link = set()

        for item in news_items:
            baslik_el = item.select_one("a.item-title") or item.find("a", href=re.compile(r"/haber/"))
            if not baslik_el:
                continue

            baslik = _temizle(baslik_el.get_text(strip=True))
            if len(baslik) < 10:
                continue

            link = baslik_el.get("href", "")
            if not link.startswith("http"):
                link = BASE_URL + link
            if link in goruldu_link:
                continue
            goruldu_link.add(link)

            # Tarih: span veya time elementi
            tarih_str = ""
            tarih_el = item.find(["time", "span"], class_=re.compile(r"tarih|date|time|ago"))
            if tarih_el:
                tarih_str = tarih_el.get("datetime", "") or tarih_el.get_text(strip=True)
            tarih = _tarih_ayristir(tarih_str)

            sonuclar.append({
                "baslik":    baslik[:120],
                "metin":     baslik,
                "tarih":     tarih,
                "kaynak_id": link,
            })
            bulunan += 1

        print(f"    ana sayfa: {bulunan} haber.")

        # KAP haberleri linki varsa ekstra çek
        kap_link = soup.find("a", string=re.compile(r"KAP|kap", re.I))
        if kap_link and kap_link.get("href"):
            kap_url = kap_link["href"]
            if not kap_url.startswith("http"):
                kap_url = BASE_URL + kap_url
            time.sleep(random.uniform(2, 3))
            r2 = scraper.get(kap_url, headers=HEADERS, timeout=25)
            if r2.status_code == 200:
                soup2 = BeautifulSoup(r2.text, "html.parser")
                kap_items = soup2.select("div.news-item a.item-title") or soup2.select("a[href*='/haber/']")
                kap_bulunan = 0
                for a in kap_items:
                    baslik = _temizle(a.get_text(strip=True))
                    if len(baslik) < 10:
                        continue
                    link = a.get("href", "")
                    if not link.startswith("http"):
                        link = BASE_URL + link
                    if link in goruldu_link:
                        continue
                    goruldu_link.add(link)
                    sonuclar.append({
                        "baslik":    baslik[:120],
                        "metin":     baslik,
                        "tarih":     str(datetime.today().date()),
                        "kaynak_id": link,
                    })
                    kap_bulunan += 1
                print(f"    kap haberleri: {kap_bulunan} haber.")

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
    slug = HISSE_SLUGLAR.get(hisse_kodu)
    if not slug:
        return 0
    print(f"\n[{hisse_kodu}] {BASE_URL}/borsa/hisseler/{slug}")
    haberler = haberleri_cek(scraper, hisse_kodu, slug)
    print(f"  {len(haberler)} benzersiz haber bulundu.")
    if not haberler:
        return 0
    conn = sqlite3.connect(DB_YOLU)
    eklenen = sum(
        kaydet(conn, hisse_kodu, h["tarih"], h["baslik"], h["metin"], h["kaynak_id"])
        for h in haberler
    )
    conn.close()
    print(f"  {eklenen} yeni kayit eklendi.")
    return eklenen


# ─── Ana Akış ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Hisse.net Haber Toplayici")
    print(f"Hisseler: {list(HISSELER.keys())}")
    print("=" * 60)

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    toplam = 0
    for hisse in HISSELER:
        toplam += hisse_isle(scraper, hisse)
        time.sleep(random.uniform(2, 4))

    print(f"\nToplam {toplam} yeni kayit eklendi.")
    print("BERT skorlama icin: python ml/duygu_analizi.py")


if __name__ == "__main__":
    main()
