"""
telegram_toplayici.py — Telegram kanal/grup mesajlarini toplar
Calistir: python telegram_toplayici.py

Gereksinimler:
  - Telethon kurulu olmali: pip install telethon
  - Oturum dosyasi olusturulmali: python telegram_giris.py (bir kez)

Calisma mantigi:
  - Hisse bazi kanallar/gruplar tanimlanir
  - Her kanalin son N mesaji cekilir
  - Hisse kodu/sirket adi gecen mesajlar filtrelenir
  - BERT duygu skoru hesaplanir
  - tweetler tablosuna kaydedilir (tweet_id = "tg_{kanal}_{mesaj_id}")

Guvenli kullanim:
  - Rate limit: her istek arasinda insan benzeri bekleme
  - Sadece PUBLIC kanallar okunur (girilmis olmak gerekmez)
  - Hic mesaj gondermez, sadece okur
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import asyncio
import io
import os
import random
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import FloodWaitError, ChannelPrivateError
from database import DB_YOLU

# Windows'ta emoji/unicode karakterlerin print hatasi vermemesi icin
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── Ayarlar ─────────────────────────────────────────────────────────────────

# telegram_giris.py ile olusturulan session dosyasi
SESSION_DOSYASI = "telegram_session"

# my.telegram.org'dan alinan bilgiler — .env dosyasindan okunur
import dotenv as _dotenv; _dotenv.load_dotenv()
API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

# Kac gunluk mesaj geriye dogru cekilsin
KACINCI_GUN = 365

# Kanal basi en fazla kac mesaj
MAX_MESAJ_KANAL = 2000

# Her hisse icin public Telegram kanal/grup listesi
# Kanal adlari @olmadan yazilir (ornek: "borsaistanbul")
# Public kanallar icin: t.me/kanaladi URL'sinden son kismini al
# Guncel kanallar icin: Telegram aramasinda "THYAO" veya "borsa" ara
HISSE_KANALLARI = {
    # Kullanici tarafindan dogrulanan kanallar (14 Nisan 2026)
    "THYAO": [
        "thyaohissem",        # THY hisse birligi - 15.369 uye
        "thyaohisseleri",     # Turk Havayollari Hisse (ANA GRUP) - 3.148 uye
        "thyao_hisse_analiz", # THYAO HISSE ANALIZ - 2.549 uye
        "thyaohissechat",     # Turk Hava Yollari Hisse - 2.605 uye
    ],
    "GARAN": [
        "garanhisse",         # Dogrulandi
        "garantibbva",        # Dogrulandi
        "garantihissemm",     # Garanti hisse birligi - 1.299 uye
    ],
    "KCHOL": [
        "kchol_kocholdinghisse", # KOC HOLDING HISSE - 8.047 uye
        "kchol_sahol",           # Kchol + Sahol Hisse - 8.353 uye
        "kcholhissem",           # Koc holding hisse birligi - 561 uye
    ],
    "EREGL": [
        "ereglhisse",         # Erdemir Eregli Hisse - 6.594 uye
        "Ereglihisse",        # Eregli Demir Celik Hisse - 1.045 uye
        "hisseeregli",        # Eregli hisse kanali
        "ereglhissem",        # Eregli hisse birlik kanali
        "eregli_kardemir",    # Eregl + Kardemir birlesik kanal
    ],
    "TUPRS": [
        "tuprs_hisse",        # Tupras Hisse - 9.965 uye
        "tuprshissemiz",      # Tupras Hisse (ANA GRUP) - 4.290 uye
        "tuprs_hisse_analiz", # TUPRS HISSE ANALIZ - 854 uye
        "tupras_aselsan",     # Tuprs + Asels Hisse - 8.213 uye
    ],
    "BIMAS": [
        "bimashisse",         # Dogrulandi - 438 mesaj
        "bimashissen",        # Bim Market Hisse Grubu - 1.648 uye
        "bimashissesi",       # Bimas Hisse (ANA GRUP) - 603 uye
        "bimas1",             # Bim marketler hisse birligi - 1.820 uye
        "bimashisseyorum",    # Bimas Hisse Yorum - 288 uye
    ],
    "ASELS": [
        "aselshisse",         # Dogrulandi
        "aselsanhissem",      # Aselsan hisse birligi - 7.554 uye
        "asels_hisse_analiz", # ASELSAN HISSE ANALIZ - 3.466 uye
        "asels_hisse",        # Aselsan Hisse - 1.842 uye
        "tupras_aselsan",     # Tuprs + Asels Hisse - 8.213 uye
    ],
    "SAHOL": [
        "saholhisse",         # Dogrulandi
        "kchol_sahol",        # Kchol + Sahol Hisse - 8.353 uye
        "saholhissesi",       # Sahol Hisse (ANA GRUP) - Dogrulandi
        "saholhissem",        # Sahol hisse birligi - Dogrulandi
    ],
    "SISE": [
        "sise_hisse",         # Sise Hisse - 5.629 uye
        "sise_quagr",         # Sise + Quagr Hisse - 10.627 uye
    ],
    "PETKM": [
        "petkmhisse",         # Dogrulandi - 2.148 uye
        "petkimanaliz",       # Dogrulandi
        "petkm_hisse",        # PETKIM HISSE - Dogrulandi
        "petkmhissem",        # Petkim hisse birligi - Dogrulandi
    ],
}

# Tum hisseler icin ortak genel Borsa kanallar
GENEL_KANALLAR = [
    "finansgundem",    # Dogrulandi
    "turkiyeborsasi",  # Dogrulandi
]

BERT_MODEL = "savasy/bert-base-turkish-sentiment-cased"

# Bekleme araliklari (saniye)
BEKLEME_MESAJ   = (0.05, 0.2)
BEKLEME_KANAL   = (0.5, 1.5)
BEKLEME_FLOOD   = (30, 90)


# ─── BERT ────────────────────────────────────────────────────────────────────

def bert_yukle():
    print(f"BERT yukleniyor: {BERT_MODEL} ...", flush=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Cihaz: {device}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BERT_MODEL)
    model.to(device)
    model.eval()
    print("  BERT hazir.\n", flush=True)
    return tokenizer, model, device


def duygu_skoru_hesapla(metin: str, tokenizer, model, device: str) -> float:
    if not metin.strip():
        return 0.0
    inputs = tokenizer(metin, return_tensors="pt", padding=True,
                       truncation=True, max_length=128)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=1)
    return round(probs[0][1].item() - probs[0][0].item(), 6)


# ─── Metin Temizleme ─────────────────────────────────────────────────────────

def metni_temizle(metin: str) -> str:
    metin = re.sub(r"http\S+", "", metin)
    metin = re.sub(r"@\w+", "", metin)
    metin = re.sub(r"#(\w+)", r"\1", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


def hisse_iceriyor_mu(metin: str, hisse_kodu: str) -> bool:
    """Mesajin bu hisseyle ilgili olup olmadigini kontrol eder."""
    metin_lower = metin.lower()
    hisse_lower = hisse_kodu.lower()
    return (
        hisse_lower in metin_lower or
        f"#{hisse_lower}" in metin_lower
    )


# ─── Veritabani ──────────────────────────────────────────────────────────────

def mesaj_kaydet(conn: sqlite3.Connection, tweet_id: str, hisse_kodu: str,
                 tarih: str, metin: str, skor: float) -> bool:
    c = conn.cursor()
    try:
        c.execute(
            """INSERT OR IGNORE INTO tweetler
               (tweet_id, hisse_kodu, tarih, metin, duygu_skoru)
               VALUES (?, ?, ?, ?, ?)""",
            (tweet_id, hisse_kodu, tarih, metin, skor),
        )
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"  [DB] Kayit hatasi: {e}")
        return False


# ─── Kanal Okuma ─────────────────────────────────────────────────────────────

async def kanal_isle(client: TelegramClient, kanal_adi: str,
                     hisse_kodu: str, hisse_filtre: bool,
                     conn: sqlite3.Connection,
                     baslangic: datetime) -> int:
    """
    Tek bir Telegram kanalini isle.
    hisse_filtre=True ise sadece hisse_kodu gecen mesajlar alinir.
    """
    kaydedilen = 0
    try:
        entity = await client.get_entity(kanal_adi)
        print(f"    Kanal bulundu: {kanal_adi}")
    except (ValueError, ChannelPrivateError):
        print(f"    [!] Kanal erisilemez veya bulunamadi: {kanal_adi}")
        return 0
    except FloodWaitError as e:
        print(f"    [FloodWait] {e.seconds}s bekleniyor...")
        await asyncio.sleep(e.seconds + 10)
        return 0
    except Exception as e:
        print(f"    [!] {kanal_adi}: {e}")
        return 0

    try:
        async for mesaj in client.iter_messages(
            entity,
            limit=MAX_MESAJ_KANAL,
            offset_date=datetime.now(),
            reverse=False,
        ):
            if not isinstance(mesaj, Message) or not mesaj.text:
                continue

            # Tarih filtresi
            if mesaj.date.replace(tzinfo=None) < baslangic:
                break

            ham_metin = mesaj.text
            temiz = metni_temizle(ham_metin)

            if len(temiz) < 10:
                continue

            # Genel kanalda hisse filtresi
            if hisse_filtre and not hisse_iceriyor_mu(temiz, hisse_kodu):
                continue

            tweet_id = f"tg_{kanal_adi}_{mesaj.id}"
            tarih_str = mesaj.date.strftime("%Y-%m-%d %H:%M:%S")

            if mesaj_kaydet(conn, tweet_id, hisse_kodu, tarih_str, temiz, None):
                kaydedilen += 1
                print(f"      [{kaydedilen:3d}] {tarih_str[:10]}  {temiz[:60]}")

            await asyncio.sleep(random.uniform(*BEKLEME_MESAJ))

    except FloodWaitError as e:
        bekle = e.seconds + random.randint(10, 30)
        print(f"    [FloodWait] {bekle}s bekleniyor...")
        await asyncio.sleep(bekle)
    except Exception as e:
        print(f"    [!] Mesaj okuma hatasi ({kanal_adi}): {e}")

    return kaydedilen


async def hisse_isle(client: TelegramClient, hisse_kodu: str,
                     conn: sqlite3.Connection,
                     baslangic: datetime) -> int:
    kanallar = HISSE_KANALLARI.get(hisse_kodu, [])
    toplam = 0

    print(f"\n[{hisse_kodu}] {len(kanallar)} ozel + {len(GENEL_KANALLAR)} genel kanal")

    for kanal in kanallar:
        print(f"  Ozel kanal: @{kanal}")
        n = await kanal_isle(
            client, kanal, hisse_kodu,
            hisse_filtre=False,
            conn=conn, baslangic=baslangic,
        )
        toplam += n
        print(f"  @{kanal}: {n} mesaj kaydedildi")
        await asyncio.sleep(random.uniform(*BEKLEME_KANAL))

    for kanal in GENEL_KANALLAR:
        print(f"  Genel kanal: @{kanal} ({hisse_kodu} filtreli)")
        n = await kanal_isle(
            client, kanal, hisse_kodu,
            hisse_filtre=True,
            conn=conn, baslangic=baslangic,
        )
        toplam += n
        if n > 0:
            print(f"  @{kanal}: {n} {hisse_kodu} mesaji kaydedildi")
        await asyncio.sleep(random.uniform(*BEKLEME_KANAL))

    return toplam


# ─── Ana Akis ────────────────────────────────────────────────────────────────

async def main():
    # Kurulum kontrolu
    if not API_ID or not API_HASH:
        print("""
[Hata] API bilgileri eksik!

1. telegram_giris.py dosyasini ac
2. API_ID ve API_HASH alanlarini doldur
3. python telegram_giris.py calistir (bir kez)
4. Bu dosyadaki API_ID ve API_HASH alanlarini da guncelle
5. Tekrar python telegram_toplayici.py calistir
""")
        return

    session = Path(f"{SESSION_DOSYASI}.session")
    if not session.exists():
        print(f"[Hata] {session} bulunamadi. Once: python telegram_giris.py")
        return

    baslangic = datetime.now() - timedelta(days=KACINCI_GUN)

    print("=" * 65)
    print("Telegram Mesaj Toplayici")
    print(f"Session  : {SESSION_DOSYASI}")
    print(f"Aralik   : Son {KACINCI_GUN} gun")
    print(f"Max mesaj: kanal basi {MAX_MESAJ_KANAL}")
    print("=" * 65)

    conn = sqlite3.connect(DB_YOLU, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")  # Concurrent erisimde lock onler

    async with TelegramClient(SESSION_DOSYASI, API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"Giris: {me.first_name} (@{me.username})\n")

        toplam = 0
        hisseler = list(HISSE_KANALLARI.keys())
        for hisse in hisseler:
            n = await hisse_isle(client, hisse, conn, baslangic)
            toplam += n
            print(f"[{hisse}] Toplam: {n} mesaj")

    conn.close()
    print(f"\nBitti. {toplam} mesaj kaydedildi.")
    print("Duygu guncelle: python duygu_analizi.py")


if __name__ == "__main__":
    asyncio.run(main())
