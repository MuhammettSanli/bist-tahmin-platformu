"""
haber_toplayici.py — Google News RSS + BigPara finansal haber toplama
Calistir: python haber_toplayici.py

Kaynaklar:
  1. Google News RSS — Turkce hisse haberleri (genis arsiv, ucretsiz)
  2. BigPara (Hurriyet Finans) — Bist haber sayfasindan basliklar

Not: KAP (kap.org.tr) JavaScript ile render edilir, BeautifulSoup ile scrape
     yapilamaz. Google News daha kapsamli ve erisimi kolay bir alternatifdir.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sqlite3
import requests
import time
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
from database import DB_YOLU, HISSELER

CALISTIRILACAK_HISSELER = list(HISSELER.keys())  # Tum 10 hisse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Her hisse kodu icin Google News arama sorgusu
HISSE_ARAMALARI = {
    "THYAO": 'THYAO "Turk Hava Yollari" THY borsa',
    "GARAN": 'GARAN "Garanti BBVA" borsa',
    "KCHOL": 'KCHOL "Koc Holding" borsa',
    "EREGL": 'EREGL "Eregli" demir celik borsa',
    "TUPRS": 'TUPRS "Tupras" borsa',
    "BIMAS": 'BIMAS "BIM" magazalari borsa',
    "ASELS": 'ASELS "Aselsan" borsa',
    "SAHOL": 'SAHOL "Sabanci Holding" borsa',
    "SISE":  'SISE "Sise Cam" borsa',
    "PETKM": 'PETKM "Petkim" borsa',
}

GECIKME_SANIYE = 1.5


# ─── Metin Temizleme ─────────────────────────────────────────────────────────

def metni_temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)
    metin = re.sub(r"[^\u0000-\u024F\u0370-\u03FF]", "", metin)   # emoji kaldir
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


# ─── Google News RSS ─────────────────────────────────────────────────────────

def google_news_cek(hisse_kodu: str) -> list[dict]:
    """
    Google News RSS feed'den hisse ile ilgili Turkce haberleri ceker.
    RSS formati: <item><title>...</title><pubDate>...</pubDate></item>
    """
    sorgu = HISSE_ARAMALARI.get(hisse_kodu, hisse_kodu)
    encoded = requests.utils.quote(sorgu)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=tr&gl=TR&ceid=TR:tr"
    )
    sonuclar = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()

        root = ET.fromstring(r.content)
        items = root.findall(".//item")

        for item in items[:60]:
            baslik   = item.findtext("title", "").strip()
            pub_date = item.findtext("pubDate", "").strip()

            if not baslik:
                continue

            # Tarih ayrıştır: "Mon, 12 Apr 2026 14:30:00 GMT"
            tarih = _tarih_ayristir_rss(pub_date)

            temiz_baslik = metni_temizle(baslik)
            if len(temiz_baslik) < 5:
                continue

            sonuclar.append({
                "tarih":  tarih,
                "baslik": temiz_baslik,
                "metin":  temiz_baslik,
            })

    except ET.ParseError as e:
        print(f"  [GoogleNews/{hisse_kodu}] XML parse hatasi: {e}")
    except Exception as e:
        print(f"  [GoogleNews/{hisse_kodu}] Hata: {e}")

    return sonuclar


def _tarih_ayristir_rss(tarih_str: str) -> str:
    """RSS pubDate formatini YYYY-MM-DD'ye cevirir."""
    if not tarih_str:
        return str(datetime.today().date())
    # "Mon, 12 Apr 2026 14:30:00 GMT"
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(tarih_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(datetime.today().date())


# ─── Bloomberg HT RSS ────────────────────────────────────────────────────────

def bloomberght_cek(hisse_kodu: str) -> list[dict]:
    """
    Bloomberg HT genel RSS feed'i ceker, hisse kodu ile filtreler.
    """
    SIRKET_ANAHTAR = {
        "THYAO": ["thyao", "türk hava", "turkish airlines", "thy"],
        "GARAN": ["garan", "garanti"],
        "KCHOL": ["kchol", "koç holding", "koc holding"],
        "EREGL": ["eregl", "ereğli", "erdemir"],
        "TUPRS": ["tuprs", "tüpraş", "tupras"],
        "BIMAS": ["bimas", "bim mağaza", "bim market"],
        "ASELS": ["asels", "aselsan"],
        "SAHOL": ["sahol", "sabancı", "sabanci"],
        "SISE":  ["sise", "şişecam", "sisecam"],
        "PETKM": ["petkm", "petkim"],
    }
    anahtar_kelimeler = SIRKET_ANAHTAR.get(hisse_kodu, [hisse_kodu.lower()])

    sonuclar = []
    try:
        r = requests.get(
            "https://www.bloomberght.com/rss.xml",
            headers=HEADERS, timeout=15
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for item in root.findall(".//item"):
            baslik  = item.findtext("title", "").strip()
            desc    = item.findtext("description", "").strip()
            pubdate = item.findtext("pubDate", "").strip()
            tam_metin = f"{baslik} {desc}".lower()
            if not any(k in tam_metin for k in anahtar_kelimeler):
                continue
            tarih = _tarih_ayristir_rss(pubdate)
            temiz = metni_temizle(f"{baslik}. {desc}" if desc else baslik)
            if len(temiz) >= 10:
                sonuclar.append({"tarih": tarih, "baslik": baslik, "metin": temiz})
    except Exception as e:
        print(f"  [BloombergHT/{hisse_kodu}] Hata: {e}")

    return sonuclar


# ─── Anahtar Kelime Tablosu (tüm kaynaklar için ortak) ──────────────────────

HISSE_ANAHTAR = {
    "THYAO": ["thyao", "türk hava", "turkish airlines", "thy"],
    "GARAN": ["garan", "garanti bbva", "garanti bankası", "garanti bankas"],
    "KCHOL": ["kchol", "koç holding", "koc holding"],
    "EREGL": ["eregl", "ereğli", "erdemir"],
    "TUPRS": ["tuprs", "tüpraş", "tupras"],
    "BIMAS": ["bimas", "bim mağaza", "bim market", "bim a.ş"],
    "ASELS": ["asels", "aselsan"],
    "SAHOL": ["sahol", "sabancı holding", "sabanci"],
    "SISE":  ["sise", "şişecam", "sisecam"],
    "PETKM": ["petkm", "petkim"],
}


def _rss_filtreli_cek(hisse_kodu: str, feed_url: str, kaynak_adi: str,
                       atom: bool = False) -> list[dict]:
    """
    Genel RSS/Atom feed'i ceker ve hisse anahtar kelimeleriyle filtreler.
    atom=True: Atom <feed>/<entry> formati
    """
    anahtar = HISSE_ANAHTAR.get(hisse_kodu, [hisse_kodu.lower()])
    sonuclar = []
    try:
        r = requests.get(feed_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)

        if atom:
            ns = "{http://www.w3.org/2005/Atom}"
            items = root.findall(f".//{ns}entry")
            title_tag, date_tag = f"{ns}title", f"{ns}updated"
        else:
            items = root.findall(".//item")
            title_tag, date_tag = "title", "pubDate"

        for item in items:
            baslik  = (item.findtext(title_tag) or "").strip()
            pubdate = (item.findtext(date_tag) or "").strip()
            desc    = (item.findtext("description") or
                       item.findtext("{http://www.w3.org/2005/Atom}summary") or "").strip()
            tam = f"{baslik} {desc}".lower()

            if not any(k in tam for k in anahtar):
                continue

            tarih = _tarih_ayristir_rss(pubdate)
            temiz = metni_temizle(f"{baslik}. {desc}" if desc else baslik)
            if len(temiz) >= 10:
                sonuclar.append({"tarih": tarih, "baslik": baslik, "metin": temiz})
    except Exception as e:
        print(f"  [{kaynak_adi}/{hisse_kodu}] Hata: {e}")
    return sonuclar


def ek_rss_cek(hisse_kodu: str) -> dict[str, list]:
    """
    Hürriyet, Dünya, AA Ekonomi, NTV, Haberturk, Milliyet RSS kaynaklarından haber ceker.
    Her kaynak icin ayri liste dondurur.
    """
    return {
        "HURRIYET": _rss_filtreli_cek(
            hisse_kodu,
            "https://www.hurriyet.com.tr/rss/ekonomi",
            "Hurriyet",
        ),
        "DUNYA": _rss_filtreli_cek(
            hisse_kodu,
            "https://www.dunya.com/rss",
            "Dunya",
        ),
        "AA": _rss_filtreli_cek(
            hisse_kodu,
            "https://www.aa.com.tr/tr/rss/default?cat=ekonomi",
            "AA",
            atom=True,
        ),
        "NTV": _rss_filtreli_cek(
            hisse_kodu,
            "https://www.ntv.com.tr/ekonomi.rss",
            "NTV",
        ),
        "HABERTURK": _rss_filtreli_cek(
            hisse_kodu,
            "https://www.haberturk.com/rss/haber/ekonomi.xml",
            "Haberturk",
        ),
        "MILLIYET": _rss_filtreli_cek(
            hisse_kodu,
            "https://www.milliyet.com.tr/rss/rssNew/ekonomi-kategorisi/",
            "Milliyet",
        ),
    }


def kap_bildirimleri_cek(hisse_kodu: str) -> list[dict]:
    """
    KAP (kap.org.tr) bildirimleri icin iki yontem:
      1. KAP JSON API (dogrudan erisim)
      2. Google News RSS ile 'KAP bildirim' arama (fallback)
    """
    sonuclar = []

    # Yontem 1: KAP JSON API
    SIRKET_KODLARI = {
        "THYAO": "350",  "GARAN": "208",  "KCHOL": "253",
        "EREGL": "175",  "TUPRS": "374",  "BIMAS": "545",
        "ASELS": "362",  "SAHOL": "341",  "SISE":  "337",
        "PETKM": "288",
    }
    member_oid = SIRKET_KODLARI.get(hisse_kodu)
    if member_oid:
        try:
            url = (
                f"https://www.kap.org.tr/tr/api/disclosures"
                f"?memberOid={member_oid}&pageIndex=0&pageSize=50"
            )
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and r.text.strip().startswith("["):
                import json as _json
                items = _json.loads(r.text)
                for item in items:
                    baslik = (item.get("disclosureTitle") or
                              item.get("title") or
                              item.get("subject") or "").strip()
                    ozet   = (item.get("disclosureSummary") or
                              item.get("summary") or "").strip()
                    tarih_str = (item.get("disclosureDate") or
                                 item.get("date") or "")
                    metin  = f"{baslik}. {ozet}".strip(" .")
                    tarih  = _tarih_ayristir_rss(tarih_str[:25])
                    if len(metin) >= 10:
                        sonuclar.append({"tarih": tarih, "baslik": baslik, "metin": metin})
                if sonuclar:
                    return sonuclar
        except Exception as e:
            print(f"  [KAP API/{hisse_kodu}] Hata: {e}")

    # Yontem 2: Google News RSS - KAP bildirim araması (fallback)
    SIRKET_ADLARI = {
        "THYAO": "Turk Hava Yollari", "GARAN": "Garanti BBVA",
        "KCHOL": "Koc Holding",       "EREGL": "Eregli Demir",
        "TUPRS": "Tupras",            "BIMAS": "BIM Magazalari",
        "ASELS": "Aselsan",           "SAHOL": "Sabanci Holding",
        "SISE":  "Sisecam",           "PETKM": "Petkim",
    }
    sirket_adi = SIRKET_ADLARI.get(hisse_kodu, hisse_kodu)
    sorgu = f'{hisse_kodu} OR "{sirket_adi}" KAP bildirim SPK temttu faaliyet'
    encoded = requests.utils.quote(sorgu)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=tr&gl=TR&ceid=TR:tr"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:30]:
            baslik  = item.findtext("title", "").strip()
            pubdate = item.findtext("pubDate", "").strip()
            if not baslik:
                continue
            # Sadece KAP/SPK/bildirim icerenler
            if not any(k in baslik.lower() for k in
                       ["kap", "spk", "bildirim", "temett", "faaliyet",
                        "kamuoyu", "bist", "fiyat tespit"]):
                continue
            tarih = _tarih_ayristir_rss(pubdate)
            temiz = metni_temizle(baslik)
            if len(temiz) >= 10:
                sonuclar.append({"tarih": tarih, "baslik": temiz, "metin": temiz})
    except Exception as e:
        print(f"  [KAP-GNews/{hisse_kodu}] Hata: {e}")

    return sonuclar


def mynet_finans_cek(hisse_kodu: str) -> list[dict]:
    """
    Mynet Ekonomi RSS + Google News ikinci sorgu ile ek haber ceker.
    """
    # Google News ikinci gecis: farkli arama terimi
    HISSE_ARAMALARI2 = {
        "THYAO": 'THY hisse senedi analiz yatirim',
        "GARAN": 'Garanti Bankasi hisse senedi analiz',
        "KCHOL": 'Koc Holding hisse senedi analiz',
        "EREGL": 'Eregli Demir hisse analiz borsa',
        "TUPRS": 'Tupras hisse analiz petrol rafinerisi',
        "BIMAS": 'BIM Magazalar hisse analiz perakende',
        "ASELS": 'Aselsan hisse analiz savunma',
        "SAHOL": 'Sabanci Holding hisse analiz',
        "SISE":  'Sisecam hisse analiz cam',
        "PETKM": 'Petkim hisse analiz petrokimya',
    }
    sorgu   = HISSE_ARAMALARI2.get(hisse_kodu, hisse_kodu)
    encoded = requests.utils.quote(sorgu)
    url     = f"https://news.google.com/rss/search?q={encoded}&hl=tr&gl=TR&ceid=TR:tr"
    sonuclar = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:40]:
            baslik  = item.findtext("title", "").strip()
            pubdate = item.findtext("pubDate", "").strip()
            if not baslik:
                continue
            tarih = _tarih_ayristir_rss(pubdate)
            temiz = metni_temizle(baslik)
            if len(temiz) >= 5:
                sonuclar.append({"tarih": tarih, "baslik": temiz, "metin": temiz})
    except Exception as e:
        print(f"  [GNews2/{hisse_kodu}] Hata: {e}")
    return sonuclar


# ─── Veritabanına Kaydet ─────────────────────────────────────────────────────

def haberleri_kaydet(hisse_kodu: str, haberler: list[dict], kaynak: str) -> int:
    if not haberler:
        return 0
    conn = sqlite3.connect(DB_YOLU)
    c    = conn.cursor()
    n = 0
    for h in haberler:
        baslik = h.get("baslik", "")
        metin  = h.get("metin", baslik)
        tarih  = h.get("tarih", str(datetime.today().date()))

        if not baslik:
            continue

        # Ayni tarih + baslik + kaynak kombinasyonu varsa atla (duplicate onleme)
        mevcut = c.execute(
            "SELECT 1 FROM haberler WHERE hisse_kodu=? AND tarih=? AND baslik=? AND kaynak=?",
            (hisse_kodu, tarih, baslik, kaynak),
        ).fetchone()
        if mevcut:
            continue

        try:
            c.execute(
                """INSERT INTO haberler
                       (hisse_kodu, tarih, baslik, metin, kaynak, duygu_skoru)
                   VALUES (?, ?, ?, ?, ?, NULL)""",
                (hisse_kodu, tarih, baslik, metin, kaynak),
            )
            n += 1
        except Exception as e:
            print(f"  Kayit hatasi ({kaynak}): {e}")

    conn.commit()
    conn.close()
    return n


# ─── Ana Akış ────────────────────────────────────────────────────────────────

def tum_haberleri_topla():
    print("=" * 60)
    print("Haber Toplama: GNews x2 + KAP + Hurriyet + Dunya + AA + NTV + Haberturk + Milliyet")
    print(f"Hisseler: {CALISTIRILACAK_HISSELER}")
    print("=" * 60)

    toplam = 0
    for hisse_kodu in CALISTIRILACAK_HISSELER:
        print(f"\n[{hisse_kodu}]")

        # Google News RSS
        gnews = google_news_cek(hisse_kodu)
        n_gnews = haberleri_kaydet(hisse_kodu, gnews, kaynak="GNEWS")
        print(f"  Google News  : {n_gnews}/{len(gnews)} haber kaydedildi.")
        time.sleep(GECIKME_SANIYE)

        # Google News ikinci sorgu (analiz odakli)
        gnews2 = mynet_finans_cek(hisse_kodu)
        n_g2 = haberleri_kaydet(hisse_kodu, gnews2, kaynak="GNEWS2")
        print(f"  GNews2       : {n_g2}/{len(gnews2)} haber kaydedildi.")
        time.sleep(GECIKME_SANIYE)

        # KAP bildirimleri
        kap = kap_bildirimleri_cek(hisse_kodu)
        n_kap = haberleri_kaydet(hisse_kodu, kap, kaynak="KAP")
        print(f"  KAP          : {n_kap}/{len(kap)} bildirim kaydedildi.")
        time.sleep(GECIKME_SANIYE)

        # Ek RSS kaynakları (Hürriyet, Dünya, ParaAnaliz, AA)
        ek = ek_rss_cek(hisse_kodu)
        n_ek = 0
        for kaynak_adi, haberler in ek.items():
            n = haberleri_kaydet(hisse_kodu, haberler, kaynak=kaynak_adi)
            n_ek += n
            if haberler:
                print(f"  {kaynak_adi:<12} : {n}/{len(haberler)} haber kaydedildi.")
        time.sleep(GECIKME_SANIYE)

        toplam += n_gnews + n_g2 + n_kap + n_ek

    print(f"\nToplam {toplam} yeni haber kaydedildi.")


if __name__ == "__main__":
    tum_haberleri_topla()
