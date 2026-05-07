"""
mynet_toplayici.py — Mynet Finans hisse haberleri toplama
Calistir: python collectors/mynet_toplayici.py

Her hisse icin finans.mynet.com'daki haber listesini HTML olarak parse eder.
Haber basligi + ozeti BERT skorlama icin haberler tablosuna kaydedilir.
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

KAYNAK       = "MYNET_FINANS"
BASE_URL     = "https://finans.mynet.com"
GECIKME_MIN  = 2.5
GECIKME_MAX  = 5.5
MAX_SAYFA    = 3     # Her hisse icin kac sayfa taransın

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://finans.mynet.com/",
}


# ─── Tarih Ayrıştırma ────────────────────────────────────────────────────────

def _tarih_ayristir(ham: str) -> str:
    if not ham:
        return str(datetime.today().date())
    ham = ham.strip()
    # DD.MM.YYYY veya DD/MM/YYYY
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", ham)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ham)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # "X saat önce", "X gün önce"
    m_rel = re.search(r"(\d+)\s*(saat|gün|gun|hafta|ay)", ham.lower())
    if m_rel:
        n, birim = int(m_rel.group(1)), m_rel.group(2)
        delta = {"saat": 0, "gün": n, "gun": n, "hafta": n*7, "ay": n*30}
        return str((datetime.today() - timedelta(days=delta.get(birim, 0))).date())
    return str(datetime.today().date())


def _metni_temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


# ─── Haber Çekme ─────────────────────────────────────────────────────────────

def haberleri_cek(scraper, slug: str) -> list[dict]:
    """
    Ana hisse sayfası + yorumlar alt sayfasını tarar.
    Haberler: <a href="/borsa/haberdetay/..."> linkleri
    Yorumlar:  #serversideComments içindeki <dd> tagleri (server-side render)
    """
    sonuclar = []
    urls = [
        f"{BASE_URL}/borsa/hisseler/{slug}/",
        f"{BASE_URL}/borsa/hisseler/{slug}/yorumlar/",
    ]

    for url in urls:
        try:
            r = scraper.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"    HTTP {r.status_code} — {url}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            bulunan = 0

            # 1) Kullanici yorumlari: #serversideComments > dl > dd
            yorum_bolumu = soup.find(id="serversideComments")
            if yorum_bolumu:
                for dd in yorum_bolumu.find_all("dd"):
                    metin = _metni_temizle(dd.get_text(separator=" ", strip=True))
                    if len(metin) < 15:
                        continue
                    sonuclar.append({
                        "metin":     metin,
                        "baslik":    metin[:80],
                        "tarih":     str(datetime.today().date()),
                        "kaynak_id": metin[:80],
                    })
                    bulunan += 1

            # 2) Haber linkleri: /borsa/haberdetay/{id}/
            haber_linkler = soup.find_all(
                "a", href=re.compile(r"/borsa/haberdetay/")
            )
            goruldu_link = set()
            for a in haber_linkler:
                link = a["href"]
                if not link.startswith("http"):
                    link = BASE_URL + link
                if link in goruldu_link:
                    continue
                goruldu_link.add(link)

                baslik = _metni_temizle(a.get_text(strip=True))
                if len(baslik) < 10:
                    continue

                # Tarihi parent elementten bul
                parent = a.find_parent(["li", "div", "article"])
                tarih_str = ""
                if parent:
                    t = parent.find(["time", "span"], class_=re.compile(r"tarih|date|time"))
                    if t:
                        tarih_str = t.get("datetime", "") or t.get_text(strip=True)
                tarih = _tarih_ayristir(tarih_str)

                sonuclar.append({
                    "metin":     baslik,
                    "baslik":    baslik[:120],
                    "tarih":     tarih,
                    "kaynak_id": link,
                })
                bulunan += 1

            print(f"    {url.split('/')[-2] or 'ana'}: {bulunan} kayit bulundu.")

        except Exception as e:
            print(f"    [{url}] Hata: {e}")

        time.sleep(random.uniform(GECIKME_MIN, GECIKME_MAX))

    # Duplikat temizle
    goruldu, benzersiz = set(), []
    for h in sonuclar:
        key = h["kaynak_id"]
        if key not in goruldu:
            goruldu.add(key)
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
        print(f"[{hisse_kodu}] slug tanimlanmamis.")
        return 0

    print(f"\n[{hisse_kodu}] {BASE_URL}/borsa/hisseler/{slug}/")
    haberler = haberleri_cek(scraper, slug)
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
    print("Mynet Finans Haber Toplayici")
    print(f"Hisseler: {list(HISSELER.keys())}")
    print(f"Sayfa limiti: {MAX_SAYFA} sayfa/hisse")
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
