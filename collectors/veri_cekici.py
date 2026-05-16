"""
veri_cekici.py — yfinance ile BIST finansal veri toplama
Çalıştır: python veri_cekici.py

Strateji: En güncel veriden geçmişe doğru indir ve kaydet.
Bu sayede yarım kalan bir çalıştırmada bile en taze veri DB'de olur.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sqlite3
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from database import DB_YOLU, HISSELER

# ─── Ayarlar ─────────────────────────────────────────────────────────────────
# Şu an sadece THYAO. Daha sonra HISSELER.keys() ile genişletilebilir.
CALISTIRILACAK_HISSELER = list(HISSELER.keys())  # Tum 10 hisse

YF_SUFFIX    = ".IS"          # Yahoo Finance BIST eki
KACINCI_YIL  = 5              # Kaç yıllık finansal veri
BITIS_TARIHI = datetime.today()
BASLANGIC_TARIHI = BITIS_TARIHI - timedelta(days=KACINCI_YIL * 365)


def fiyatlari_indir(hisse_kodu: str) -> pd.DataFrame:
    ticker = hisse_kodu + YF_SUFFIX
    baslangic = BASLANGIC_TARIHI.strftime("%Y-%m-%d")
    bitis     = BITIS_TARIHI.strftime("%Y-%m-%d")

    print(f"  [{ticker}] indiriliyor: {baslangic} -> {bitis} ({KACINCI_YIL} yil)")
    df = yf.download(ticker, start=baslangic, end=bitis, progress=False)

    if df.empty:
        print(f"  [{ticker}] veri alınamadı.")
        return pd.DataFrame()

    df = df.reset_index()
    # MultiIndex sütun varsa düzelt
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # ─ En güncel → en eski sırası ─────────────────────────────────────────
    # Böylece işlem yarıda kesilse bile DB'de en taze veriler bulunur.
    df = df.sort_values("Date", ascending=False).reset_index(drop=True)
    return df


def veritabanina_kaydet(hisse_kodu: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    conn = sqlite3.connect(DB_YOLU)
    c    = conn.cursor()
    eklenen = 0

    for _, row in df.iterrows():
        tarih = str(row["Date"])[:10]  # YYYY-MM-DD
        try:
            c.execute(
                """INSERT OR IGNORE INTO gunluk_fiyatlar
                   (hisse_kodu, tarih, acilis, kapanis, yuksek, dusuk, hacim)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    hisse_kodu,
                    tarih,
                    round(float(row["Open"]),   4),
                    round(float(row["Close"]),  4),
                    round(float(row["High"]),   4),
                    round(float(row["Low"]),    4),
                    int(row["Volume"]),
                ),
            )
            if c.rowcount > 0:
                eklenen += 1
        except Exception as e:
            print(f"    Satır atıldı ({tarih}): {e}")

    conn.commit()
    conn.close()
    return eklenen


def hisseleri_isle():
    print("=" * 55)
    print("Finansal Veri Toplama (Yeniden Eskiye)")
    print(f"Hisseler: {CALISTIRILACAK_HISSELER}")
    print("=" * 55)

    toplam = 0
    for hisse_kodu in CALISTIRILACAK_HISSELER:
        print(f"\n[{hisse_kodu}]")
        df      = fiyatlari_indir(hisse_kodu)
        eklenen = veritabanina_kaydet(hisse_kodu, df)
        print(f"  {eklenen} yeni kayit eklendi  (toplam satir: {len(df)})")
        toplam += eklenen

    print(f"\nBitti. Toplam {toplam} fiyat kaydi eklendi.")


# ─── Makro Veri ──────────────────────────────────────────────────────────────

MAKRO_SEMBOLLER = {
    "bist100":       "XU100.IS",  # BIST100 endeksi
    "usdtry":        "USDTRY=X",  # Dolar/TL kuru
    "petrol":        "BZ=F",      # Brent Ham Petrol
    "altin":         "GC=F",      # Altin fiyati
    "celik_hrc":     "HRC=F",     # Sicak Haddelenmis Celik (EREGL urun fiyati)
    "demir_cevheri": "TIO=F",     # Demir Cevheri (EREGL girdi maliyeti)
    "dogalgaz":      "NG=F",      # Dogal Gaz (PETKM/SISE uretim girdisi)
    "petrokimya":    "LYB",       # LyondellBasell (PETKM sektor proxy)
    "kerosen":       "HO=F",      # Isitma yagi = jet yakiti proxy (THYAO/TUPRS)
    "benzin":        "RB=F",      # RBOB benzin = rafineri urun marji (TUPRS crack spread)
    "eurusd":        "EURUSD=X",  # EUR/USD kuru (SISE ihracat geliri EUR cinsinden)
    "bugday":        "ZW=F",      # Bugday vadeli islemi (BIMAS gida hammadde maliyeti)
}


def makro_veri_indir() -> pd.DataFrame:
    """BIST100, USDTRY, Brent petrol ve altin gunluk kapanislarini indirir."""
    baslangic = BASLANGIC_TARIHI.strftime("%Y-%m-%d")
    bitis     = BITIS_TARIHI.strftime("%Y-%m-%d")
    print(f"\n[MAKRO] {baslangic} -> {bitis}")

    df_list = []
    for isim, sembol in MAKRO_SEMBOLLER.items():
        print(f"  {sembol} indiriliyor...")
        try:
            raw = yf.download(sembol, start=baslangic, end=bitis, progress=False)
            if raw.empty:
                print(f"    {sembol} bos geldi, atlaniyor.")
                continue
            raw = raw.reset_index()
            raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
            raw = raw[["Date", "Close"]].rename(columns={"Date": "tarih", "Close": isim})
            raw["tarih"] = raw["tarih"].astype(str).str[:10]
            df_list.append(raw.set_index("tarih"))
        except Exception as e:
            print(f"    {sembol} hatasi: {e}")

    if not df_list:
        print("  Hic makro veri alinamadi.")
        return pd.DataFrame()

    df = pd.concat(df_list, axis=1).reset_index()
    df = df.sort_values("tarih").reset_index(drop=True)
    print(f"  {len(df)} gun makro veri hazirlandi.")
    return df


def makro_veritabanina_kaydet(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    conn = sqlite3.connect(DB_YOLU)
    c    = conn.cursor()
    eklenen = 0
    for _, row in df.iterrows():
        try:
            def f(col): return float(row[col]) if col in row and pd.notna(row[col]) else None
            c.execute(
                """INSERT OR REPLACE INTO makro_veriler
                   (tarih, bist100, usdtry, petrol, altin,
                    celik_hrc, demir_cevheri, dogalgaz, petrokimya,
                    kerosen, benzin, eurusd, bugday)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(row["tarih"]),
                    f("bist100"), f("usdtry"), f("petrol"), f("altin"),
                    f("celik_hrc"), f("demir_cevheri"), f("dogalgaz"), f("petrokimya"),
                    f("kerosen"), f("benzin"), f("eurusd"), f("bugday"),
                )
            )
            if c.rowcount > 0:
                eklenen += 1
        except Exception as e:
            print(f"    Makro kayit hatasi: {e}")
    conn.commit()
    conn.close()
    return eklenen


if __name__ == "__main__":
    hisseleri_isle()
    df_makro = makro_veri_indir()
    n = makro_veritabanina_kaydet(df_makro)
    print(f"Makro: {n} kayit eklendi/guncellendi.")
