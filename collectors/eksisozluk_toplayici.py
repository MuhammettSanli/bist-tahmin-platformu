"""
eksisozluk_toplayici.py — Eksi Sozluk hisse yorumlarini toplar
Calistir: python eksisozluk_toplayici.py

Cloudflare bypass icin cloudscraper kullanir (pip install cloudscraper).
Her hisse icin eksi sozluk'teki entry'leri ve iceriklerini ceker.
Uzun form Turkce yorumlar — haber basliklarindan farkli, gercek kullanici gorisi.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sqlite3
import time
import random
import re
from datetime import datetime
import cloudscraper
from bs4 import BeautifulSoup
from database import DB_YOLU, HISSELER

# ─── Ayarlar ─────────────────────────────────────────────────────────────────

CALISTIRILACAK_HISSELER = list(HISSELER.keys())

# Her hisse icin Eksi Sozluk arama terimi + bilinen entry slug'i
# slug--entry_id ciftleri (kesfedildi, sabit kullan)
HISSE_ENTRIES = {
    "THYAO": [("thyao",   "1419424")],
    "GARAN": [("garan",   "190093")],
    "KCHOL": [("kchol",   "741949")],
    "EREGL": [("eregl",   "190098")],
    "TUPRS": [("tuprs",   "190094")],
    "BIMAS": [("bimas",   "3200272")],
    "ASELS": [("asels",   "1103904")],
    "SAHOL": [("sahol",   "619802")],
    "SISE":  [("sise",    "3867895")],
    "PETKM": [("petkm",   "1824606")],
}

MAX_SAYFA_ARAMA = 3      # Arama sonuclari kac sayfa taransin
MAX_SAYFA_ENTRY = 999    # Her entry kac sayfa okunsin (sayfa basi 10 entry, 999=tum sayfalar)
MIN_METIN_UZUNLUK = 20   # En az bu kadar karakter olmali
GECIKME_MIN = 2.0
GECIKME_MAX = 5.0
KAYNAK = "EKSISOZLUK"

BASE_URL = "https://eksisozluk.com"


# ─── Scraper Olusturma ───────────────────────────────────────────────────────

def scraper_olustur():
    """Cloudflare atlayan cloudscraper session olusturur."""
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )


# ─── Arama ve Entry Bulma ────────────────────────────────────────────────────

def entry_leri_bul(scraper, arama_terimi: str) -> list[dict]:
    """
    Verilen terimi Eksi Sozluk'te arar, bulunan entry slug + id listesi doner.
    """
    encoded = arama_terimi.replace(" ", "+")
    url = f"{BASE_URL}/?q={encoded}"
    entry_ler = []

    try:
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # Arama sonucu olarak dogrudan entry sayfasina yonlendirme kontrol et
        if "/entry/" in r.url or "eksisozluk.com/" in r.url and "?q=" not in r.url:
            # Dogrudan entry sayfasina geldik
            m = re.search(r"eksisozluk\.com/([\w-]+)--(\d+)", r.url)
            if m:
                entry_ler.append({"slug": m.group(1), "entry_id": m.group(2)})
                return entry_ler

        # Arama sonuc listesi
        for link in soup.select("ul.topic-list li a, .search-result a"):
            href = link.get("href", "")
            m = re.search(r"/([\w-]+)--(\d+)", href)
            if m:
                entry_ler.append({"slug": m.group(1), "entry_id": m.group(2)})

        # Alternatif: autocomplete API
        if not entry_ler:
            ac_url = f"{BASE_URL}/autocomplete/topic?q={encoded}&_={int(time.time()*1000)}"
            try:
                ac_r = scraper.get(ac_url, timeout=10)
                if ac_r.status_code == 200:
                    for item in ac_r.json():
                        slug = item.get("Key", "").lower().replace(" ", "-")
                        entry_id = str(item.get("Value", ""))
                        if slug and entry_id:
                            entry_ler.append({"slug": slug, "entry_id": entry_id})
            except Exception:
                pass

    except Exception as e:
        print(f"  [Arama/{arama_terimi}] Hata: {e}")

    return entry_ler


# ─── Entry Icerigi Cekme ─────────────────────────────────────────────────────

def entry_icerik_cek(scraper, slug: str, entry_id: str, sayfa: int = 1) -> list[dict]:
    """
    Bir Eksi Sozluk entry sayfasindaki tum entry'leri (yorumlari) ceker.
    Her entry: metin + tarih bilgisini icerir.
    """
    url = f"{BASE_URL}/{slug}--{entry_id}"
    params = {"p": sayfa} if sayfa > 1 else {}
    sonuclar = []

    try:
        r = scraper.get(url, params=params, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        for li in soup.select("li[data-id]"):
            # Metin
            metin_el = li.select_one("div.content")
            if not metin_el:
                continue
            metin = metin_el.get_text(separator=" ", strip=True)
            if len(metin) < MIN_METIN_UZUNLUK:
                continue

            # Tarih — "28.11.2005 10:37 ~ 05.10.2006 02:23" → ilk tarih alinir
            tarih_el = li.select_one("a.entry-date")
            tarih_ham = tarih_el.get_text(strip=True).split("~")[0].strip() if tarih_el else ""
            tarih = _tarih_ayristir(tarih_ham)

            # Entry ID (benzersiz)
            kaynak_id = li.get("data-id", "")

            sonuclar.append({
                "metin":     metin,
                "tarih":     tarih,
                "kaynak_id": kaynak_id,
            })

    except Exception as e:
        print(f"  [Entry/{slug}/s{sayfa}] Hata: {e}")

    return sonuclar


def _tarih_ayristir(tarih_ham: str) -> str:
    """Eksi Sozluk tarih formatlarini YYYY-MM-DD'ye cevirir."""
    if not tarih_ham:
        return str(datetime.today().date())
    # Eksi Sozluk formati: "12.04.2026 14:30" veya "12.04.2026"
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(tarih_ham[:16], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(datetime.today().date())


# ─── Veritabani Kayit ────────────────────────────────────────────────────────

def entry_kaydet(conn: sqlite3.Connection, hisse_kodu: str,
                 tarih: str, metin: str, kaynak_id: str) -> bool:
    c = conn.cursor()
    if kaynak_id:
        mevcut = c.execute(
            "SELECT 1 FROM haberler WHERE kaynak=? AND baslik=?",
            (KAYNAK, kaynak_id)
        ).fetchone()
    else:
        mevcut = c.execute(
            "SELECT 1 FROM haberler WHERE hisse_kodu=? AND tarih=? AND metin=? AND kaynak=?",
            (hisse_kodu, tarih, metin, KAYNAK)
        ).fetchone()
    if mevcut:
        return False
    try:
        c.execute(
            """INSERT INTO haberler (hisse_kodu, tarih, baslik, metin, kaynak, duygu_skoru)
               VALUES (?, ?, ?, ?, ?, NULL)""",
            (hisse_kodu, tarih, kaynak_id or metin[:60], metin, KAYNAK)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  [DB] Hata: {e}")
        return False


# ─── Hisse Isleme ─────────────────────────────────────────────────────────────

def sayfa_sayisi_bul(scraper, slug: str, entry_id: str) -> int:
    """Entry'nin kac sayfasi oldugunu bulur."""
    try:
        r = scraper.get(f"{BASE_URL}/{slug}--{entry_id}", timeout=20)
        from bs4 import BeautifulSoup as BS
        soup = BS(r.text, "lxml")
        pager = soup.select_one("div.pager[data-pagecount]")
        if pager:
            return int(pager.get("data-pagecount", 1))
    except Exception:
        pass
    return 1


def hisse_isle(scraper, hisse_kodu: str):
    entries = HISSE_ENTRIES.get(hisse_kodu, [])
    conn    = sqlite3.connect(DB_YOLU)
    toplam  = 0

    print(f"\n[{hisse_kodu}] {len(entries)} entry islenecek.")

    for slug, entry_id in entries:
        toplam_sayfa = sayfa_sayisi_bul(scraper, slug, entry_id)
        cek_sayfa    = min(toplam_sayfa, MAX_SAYFA_ENTRY)
        print(f"  /{slug}--{entry_id}  ({toplam_sayfa} sayfa, {cek_sayfa} cekilecek)")

        for sayfa in range(1, cek_sayfa + 1):
            icerikler = entry_icerik_cek(scraper, slug, entry_id, sayfa)
            if not icerikler:
                break

            eklenen = sum(
                entry_kaydet(conn, hisse_kodu, ic["tarih"], ic["metin"], ic["kaynak_id"])
                for ic in icerikler
            )
            toplam += eklenen
            print(f"    Sayfa {sayfa}/{cek_sayfa}: {eklenen}/{len(icerikler)} yeni")

            # Sayfa icerik dondurmezse dur; ama sadece duplicate varsa devam et
            # (ilk calistirmada orta sayfalar zaten cekilmemis olabilir)

            time.sleep(random.uniform(GECIKME_MIN, GECIKME_MAX))

    conn.close()
    print(f"  [{hisse_kodu}] Toplam {toplam} yeni entry eklendi.")
    return toplam


# ─── Ana Akis ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Eksi Sozluk Hisse Yorum Toplayici (cloudscraper)")
    print(f"Hisseler: {CALISTIRILACAK_HISSELER}")
    print("=" * 60)

    scraper = scraper_olustur()
    toplam  = 0

    for hisse in CALISTIRILACAK_HISSELER:
        n = hisse_isle(scraper, hisse)
        toplam += n
        time.sleep(random.uniform(5, 10))  # Hisseler arasi uzun bekleme

    print(f"\nToplam {toplam} entry eklendi.")
    print("Duygu skorlamak icin: python duygu_analizi.py")


if __name__ == "__main__":
    main()
