"""
features.py — Ortak özellik mühendisliği modülü

Eğitim (model_egitimi.py), tahmin (app.py) ve backtest (backtest.py)
hep bu modülü kullanır — özellik tutarsızlığı olmaz.

Dışa açılan:
  ozellikler_hesapla(hisse_kodu, gun_sayisi=None) -> pd.DataFrame
  lag_ekle(df)                                    -> (pd.DataFrame, list[str])
  FINANSAL_OZELLIKLER, HIBRIT_OZELLIKLER, LAG_GUNLER, LAG_SUTUNLAR
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import sqlite3
import numpy as np
import pandas as pd
import pandas_ta as ta

from database import DB_YOLU

# ─── Sabitler ────────────────────────────────────────────────────────────────

LAG_GUNLER = [1, 2, 3, 5, 10]

LAG_SUTUNLAR = [
    "kapanis", "RSI", "hacim_oran", "hl_spread",
    "duygu_skoru", "duygu_momentum", "duygu_std7", "duygu_delta",
    "haber_duygu", "haber_momentum",
    "duygu_hacim", "haber_hacim", "duygu_abs_mom",
    "kaynak_sayisi", "konsensus", "std_kaynak",
]

FINANSAL_OZELLIKLER = [
    "acilis", "kapanis", "hacim",
    "RSI", "SMA_20", "SMA_50", "MACD", "MACD_signal",
    "BB_upper", "BB_lower", "BB_width",
    "ATR", "STOCH_k", "ROC",
    "hacim_oran", "hl_spread",
    "bist100_getiri", "usdtry_getiri", "petrol_getiri", "altin_getiri",
]

# Hisse bazlı ek finansal özellikler (sektöre özgü emtia fiyatları)
HISSE_OZEL_FINANSAL = {
    "EREGL": ["celik_hrc_getiri", "demir_cevheri_getiri"],       # Celik: HRC urun + demir cevheri girdi
    "PETKM": ["dogalgaz_getiri", "petrokimya_getiri"],            # Petrokimya: gaz girdi + sektor proxy
    "KCHOL": ["tuprs_hisse_getiri", "froto_getiri",              # Holding: istirak hisse getirileri
              "toaso_getiri", "ykbnk_getiri"],
    # SAHOL: akbnk+enery kötüleştirdi (%50.9 → %49.6), kaldırıldı
    # TUPRS: crack spread (kerosen+benzin) holdout'u %62.4'e cikardi ama
    # walk-forward %49.8 → overfitting. petrol_getiri base feature'da zaten var.
}


def finansal_ozellikler_al(hisse_kodu: str) -> list:
    """Hisseye özgü finansal özellik listesi döndürür."""
    ozel = HISSE_OZEL_FINANSAL.get(hisse_kodu, [])
    return FINANSAL_OZELLIKLER + ozel

DUYGU_OZELLIKLER = [
    "duygu_skoru", "duygu_momentum", "duygu_std7", "duygu_delta",
    "haber_duygu", "haber_momentum",
    "duygu_hacim", "haber_hacim", "duygu_abs_mom",
    "kaynak_sayisi", "konsensus", "std_kaynak",
]

HIBRIT_OZELLIKLER = FINANSAL_OZELLIKLER + DUYGU_OZELLIKLER


def hibrit_ozellikler_al(hisse_kodu: str) -> list:
    """Hisseye özgü hibrit özellik listesi döndürür."""
    return finansal_ozellikler_al(hisse_kodu) + DUYGU_OZELLIKLER


# ─── Tutarlılık Sinyali ───────────────────────────────────────────────────────

def tutarlilik_hesapla(kaynak_df: pd.DataFrame, tarihler: pd.Series) -> pd.DataFrame:
    """
    Kaynak bazlı duygu tutarlılık sinyalleri:
      kaynak_sayisi : kaç farklı kaynak veri sağladı (0-N)
      konsensus     : kaynakların kaçı aynı yöne işaret ediyor (0-1)
      std_kaynak    : kaynaklar arası standart sapma
    """
    tum_tarihler = tarihler.unique()
    if kaynak_df.empty:
        return pd.DataFrame({
            "tarih":         tum_tarihler,
            "kaynak_sayisi": 0.0,
            "konsensus":     0.5,
            "std_kaynak":    0.0,
        })

    pivot = kaynak_df.pivot_table(index="tarih", columns="kaynak",
                                   values="skor", aggfunc="mean")
    pivot = pivot.reindex(tum_tarihler)

    ort = pivot.mean(axis=1, skipna=True)
    konsensus_vals = []
    for i in range(len(pivot)):
        row = pivot.iloc[i].dropna()
        if len(row) <= 1:
            konsensus_vals.append(0.5)
        else:
            ov = ort.iloc[i]
            if pd.isna(ov) or ov == 0:
                konsensus_vals.append(0.5)
            else:
                konsensus_vals.append(
                    float((np.sign(row) == np.sign(ov)).sum() / len(row))
                )

    return pd.DataFrame({
        "tarih":         pivot.index,
        "kaynak_sayisi": pivot.notna().sum(axis=1).values.astype(float),
        "std_kaynak":    pivot.std(axis=1, skipna=True).fillna(0.0).values,
        "konsensus":     konsensus_vals,
    })


# ─── Ana Özellik Hesaplama ────────────────────────────────────────────────────

def ozellikler_hesapla(hisse_kodu: str, gun_sayisi: int = None) -> pd.DataFrame:
    """
    Verilen hisse için tüm özellikleri hesaplar ve döndürür.
    hedef kolonu YOK — eğitim kodu kendi ekler.
    lag kolonları YOK — lag_ekle() ile sonradan ekle.

    gun_sayisi: None ise tüm tarih geçmişi, int ise son N gün.
    """
    conn = sqlite3.connect(DB_YOLU)

    if gun_sayisi:
        fiyat_df = pd.read_sql_query(
            "SELECT tarih, acilis, kapanis, yuksek, dusuk, hacim "
            "FROM gunluk_fiyatlar WHERE hisse_kodu = ? "
            "ORDER BY tarih DESC LIMIT ?",
            conn, params=(hisse_kodu, gun_sayisi)
        )
    else:
        fiyat_df = pd.read_sql_query(
            "SELECT tarih, acilis, kapanis, yuksek, dusuk, hacim "
            "FROM gunluk_fiyatlar WHERE hisse_kodu = ? ORDER BY tarih",
            conn, params=(hisse_kodu,)
        )

    duygu_df = pd.read_sql_query(
        "SELECT tarih, ortalama_skor AS duygu_skoru FROM gunluk_duygu "
        "WHERE hisse_kodu = ? ORDER BY tarih",
        conn, params=(hisse_kodu,)
    )
    haber_df = pd.read_sql_query(
        "SELECT DATE(tarih) AS tarih, AVG(duygu_skoru) AS haber_duygu "
        "FROM haberler WHERE hisse_kodu = ? AND duygu_skoru IS NOT NULL "
        "GROUP BY DATE(tarih) ORDER BY tarih",
        conn, params=(hisse_kodu,)
    )
    kaynak_df = pd.read_sql_query(
        "SELECT DATE(tarih) AS tarih, kaynak, AVG(duygu_skoru) AS skor "
        "FROM haberler WHERE hisse_kodu = ? AND duygu_skoru IS NOT NULL "
        "GROUP BY DATE(tarih), kaynak ORDER BY tarih",
        conn, params=(hisse_kodu,)
    )
    makro_df = pd.read_sql_query(
        "SELECT tarih, bist100, usdtry, petrol, altin, "
        "celik_hrc, demir_cevheri, dogalgaz, petrokimya, "
        "kerosen, benzin, eurusd, bugday, "
        "tuprs_hisse, froto, toaso, ykbnk, akbnk, enery FROM makro_veriler ORDER BY tarih",
        conn
    )
    conn.close()

    if fiyat_df.empty or len(fiyat_df) < 30:
        return pd.DataFrame()

    df = fiyat_df.merge(duygu_df, on="tarih", how="left")
    df = df.merge(haber_df, on="tarih", how="left")
    df = df.sort_values("tarih").reset_index(drop=True)

    # Tatil/eksik fiyat satırlarını at — NaN fiyatlar rolling göstergeleri bozar
    df = df.dropna(subset=["kapanis", "acilis", "yuksek", "dusuk"]).reset_index(drop=True)

    # ── Duygu sinyalleri ────────────────────────────────────────────────────
    raw_duygu = df["duygu_skoru"].ffill(limit=365).fillna(0.0)
    duygu_ma7 = raw_duygu.rolling(window=7, min_periods=1).mean()
    df["duygu_skoru"]    = duygu_ma7
    df["duygu_momentum"] = raw_duygu - duygu_ma7          # ham - 7g ort = ani sapma
    df["duygu_std7"]     = raw_duygu.rolling(window=7, min_periods=1).std().fillna(0.0)
    df["duygu_delta"]    = raw_duygu.diff(1).fillna(0.0)  # gün gün değişim

    raw_haber = df["haber_duygu"].ffill(limit=30).fillna(0.0)
    haber_ma7 = raw_haber.rolling(window=7, min_periods=1).mean()
    df["haber_duygu"]    = haber_ma7
    df["haber_momentum"] = raw_haber - haber_ma7

    # ── Kaynak tutarlılık sinyalleri ────────────────────────────────────────
    tut_df = tutarlilik_hesapla(kaynak_df, df["tarih"])
    df = df.merge(tut_df, on="tarih", how="left")
    df["kaynak_sayisi"] = df["kaynak_sayisi"].fillna(0.0).rolling(7, min_periods=1).mean()
    df["konsensus"]     = df["konsensus"].fillna(0.5).rolling(7, min_periods=1).mean()
    df["std_kaynak"]    = df["std_kaynak"].fillna(0.0).rolling(7, min_periods=1).mean()

    # ── Makro getiriler ─────────────────────────────────────────────────────
    if not makro_df.empty:
        _tum_makro = [
            "bist100", "usdtry", "petrol", "altin",
            "celik_hrc", "demir_cevheri", "dogalgaz", "petrokimya",
            "kerosen", "benzin", "eurusd", "bugday",
            "tuprs_hisse", "froto", "toaso", "ykbnk", "akbnk", "enery",
        ]
        for col in _tum_makro:
            if col in makro_df.columns:
                makro_df[f"{col}_getiri"] = makro_df[col].pct_change(fill_method=None)
        makro_cols = ["tarih"] + [
            f"{c}_getiri" for c in _tum_makro if c in makro_df.columns
        ]
        df = df.merge(makro_df[makro_cols], on="tarih", how="left")
        for col in makro_cols[1:]:
            df[col] = df[col].ffill(limit=5).fillna(0.0)
    else:
        for col in ["bist100_getiri", "usdtry_getiri", "petrol_getiri", "altin_getiri"]:
            df[col] = 0.0

    # ── Teknik göstergeler ──────────────────────────────────────────────────
    k = df["kapanis"]
    df["RSI"]         = ta.rsi(k, length=14)
    df["SMA_20"]      = ta.sma(k, length=20)
    df["SMA_50"]      = ta.sma(k, length=50)

    macd              = ta.macd(k)
    df["MACD"]        = macd["MACD_12_26_9"]  if macd is not None else 0.0
    df["MACD_signal"] = macd["MACDs_12_26_9"] if macd is not None else 0.0

    bb           = ta.bbands(k, length=20)
    bb_upper_col = [c for c in bb.columns if c.startswith("BBU")][0] if bb is not None else None
    bb_lower_col = [c for c in bb.columns if c.startswith("BBL")][0] if bb is not None else None
    df["BB_upper"] = bb[bb_upper_col] if bb is not None else k
    df["BB_lower"] = bb[bb_lower_col] if bb is not None else k
    df["BB_width"] = (df["BB_upper"] - df["BB_lower"]) / k

    df["ATR"]     = ta.atr(df["yuksek"], df["dusuk"], k, length=14)
    stoch         = ta.stoch(df["yuksek"], df["dusuk"], k)
    df["STOCH_k"] = stoch["STOCHk_14_3_3"] if stoch is not None else 50.0
    df["ROC"]     = ta.roc(k, length=10)

    df["hacim_oran"] = df["hacim"] / df["hacim"].rolling(20).mean()
    df["hl_spread"]  = (df["yuksek"] - df["dusuk"]) / k

    # ── Etkileşim özellikleri ───────────────────────────────────────────────
    df["duygu_hacim"]   = df["duygu_skoru"] * df["hacim_oran"]
    df["haber_hacim"]   = df["haber_duygu"] * df["hacim_oran"]
    df["duygu_abs_mom"] = df["duygu_momentum"].abs()

    df["tarih"] = pd.to_datetime(df["tarih"])
    return df.sort_values("tarih").reset_index(drop=True)


# ─── Lag Özellikleri ──────────────────────────────────────────────────────────

def lag_ekle(df: pd.DataFrame, sadece_sutunlar: list = None) -> tuple:
    """
    LAG_SUTUNLAR listesindeki (veya sadece_sutunlar) sütunlar için
    LAG_GUNLER kadar gecikmeli özellikler ekler.

    Döndürür: (df_with_lags, lag_col_names)
    """
    hedef_sutunlar = sadece_sutunlar if sadece_sutunlar is not None else LAG_SUTUNLAR
    lag_cols = []
    yeni = {}
    for sutun in hedef_sutunlar:
        if sutun not in df.columns:
            continue
        for lag in LAG_GUNLER:
            col_name = f"{sutun}_lag{lag}"
            yeni[col_name] = df[sutun].shift(lag)
            lag_cols.append(col_name)
    df = pd.concat([df, pd.DataFrame(yeni, index=df.index)], axis=1)
    return df, lag_cols
