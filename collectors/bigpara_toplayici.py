"""
bigpara_toplayici.py — BigPara (Hurriyet) hisse teknik yorumlar + haberler
Calistir: python collectors/bigpara_toplayici.py

Her hisse icin:
  1. Teknik Yorum — otomatik gunluk teknik analiz metni (rowContent650)
  2. Hisse Haberleri — hisseye ozel haberler
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

KAYNAK      = "BIGPARA"
BASE_URL    = "https://bigpara.hurriyet.com.tr"
GECIKME_MIN = 2.0
GECIKME_MAX = 4.5

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
    "Referer": "https://bigpara.hurriyet.com.tr/",
}


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _tarih_ayristir(ham: str) -> str:
    if not ham:
        return str(datetime.today().date())
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", ham)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ham)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return str(datetime.today().date())


def _temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


# ─── Veri Çekme ──────────────────────────────────────────────────────────────

def verileri_cek(scraper, hisse_kodu: str, slug: str) -> list[dict]:
    sonuclar = []
    detay_base = f"{BASE_URL}/borsa/hisse-fiyatlari/{slug}-detay"

    sayfalar = [
        (f"{detay_base}/hisse-haberleri/", "haber"),
    ]

    for url, tur in sayfalar:
        try:
            r = scraper.get(url, headers=HEADERS, timeout=25)
            if r.status_code != 200:
                print(f"    HTTP {r.status_code} — {tur}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            if tur == "teknik_yorum":
                # Ana teknik yorum metni — rowContent650 div
                el = soup.find(class_="rowContent650")
                if el:
                    metin = _temizle(el.get_text(separator=" ", strip=True))
                    if len(metin) > 30:
                        sonuclar.append({
                            "baslik":    f"{hisse_kodu} Teknik Yorum {datetime.today().date()}",
                            "metin":     metin[:2000],
                            "tarih":     str(datetime.today().date()),
                            "kaynak_id": f"bigpara_teknik_{hisse_kodu}_{datetime.today().date()}",
                        })
                        print(f"    teknik_yorum: 1 kayit ({len(metin)} karakter)")
                    else:
                        print(f"    teknik_yorum: icerik bulunamadi")
                else:
                    print(f"    teknik_yorum: rowContent650 yok")

            elif tur == "haber":
                # Haber linkleri — /haberler/ veya /haberdetay/ iceren linkler
                haber_links = soup.find_all("a", href=re.compile(r"/haberler/|/haberdetay/"))
                goruldu = set()
                bulunan = 0
                for a in haber_links:
                    link = a["href"]
                    if not link.startswith("http"):
                        link = BASE_URL + link
                    if link in goruldu:
                        continue
                    goruldu.add(link)

                    baslik = _temizle(a.get_text(strip=True))
                    if len(baslik) < 10:
                        continue

                    # Tarih - parent elementi kontrol et
                    parent = a.find_parent(["li", "div", "article"])
                    tarih_str = ""
                    if parent:
                        t = parent.find(["time", "span"], class_=re.compile(r"tarih|date|time"))
                        if t:
                            tarih_str = t.get("datetime", "") or t.get_text(strip=True)
                    tarih = _tarih_ayristir(tarih_str)

                    sonuclar.append({
                        "baslik":    baslik[:120],
                        "metin":     baslik,
                        "tarih":     tarih,
                        "kaynak_id": link,
                    })
                    bulunan += 1
                print(f"    haber: {bulunan} kayit")

        except Exception as e:
            print(f"    [{hisse_kodu}/{tur}] Hata: {e}")

        time.sleep(random.uniform(GECIKME_MIN, GECIKME_MAX))

    # Duplikat temizle
    goruldu, benzersiz = set(), []
    for h in sonuclar:
        if h["kaynak_id"] not in goruldu:
            goruldu.add(h["kaynak_id"])
            benzersiz.append(h)
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

def hisse_isle(scraper, hisse_kodu: str) -> int:
    slug = HISSE_SLUGLAR.get(hisse_kodu)
    if not slug:
        return 0
    print(f"\n[{hisse_kodu}] {BASE_URL}/borsa/hisse-fiyatlari/{slug}-detay/")
    veriler = verileri_cek(scraper, hisse_kodu, slug)
    print(f"  {len(veriler)} benzersiz kayit.")
    if not veriler:
        return 0
    conn = sqlite3.connect(DB_YOLU)
    eklenen = sum(
        kaydet(conn, hisse_kodu, v["tarih"], v["baslik"], v["metin"], v["kaynak_id"])
        for v in veriler
    )
    conn.close()
    print(f"  {eklenen} yeni kayit eklendi.")
    return eklenen


# ─── Ana Akış ─────────────────────────────────────────────────────��──────────

def main():
    print("=" * 60)
    print("BigPara Teknik Yorum + Haber Toplayici")
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
    print("BERT skorlama: python ml/duygu_analizi.py")


if __name__ == "__main__":
    main()
