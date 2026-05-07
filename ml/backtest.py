"""
backtest.py — Holdout dönemi alım-satım simülasyonu

Strateji: Long-Only
  - Tahmin YÜKSELİŞ → o günün kapanışında gir, ertesi kapanışta çık
  - Tahmin DÜŞÜŞ    → nakit bekle
Benchmark: Aynı dönemde BIST100 buy-and-hold
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import os
import json
import numpy as np
import pandas as pd
import joblib

from features import ozellikler_hesapla, lag_ekle

MODELLER_KLASOR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "models")
HOLDOUT_BAS     = "2025-10-01"
HOLDOUT_BIT     = "2026-04-14"

RISKSIZ_FAIZ_GUNLUK = 0.35 / 252
KOMISYON_ORAN       = 0.0002  # %0.02 alis + %0.02 satis = toplam %0.04 per islem


def _model_yukle(hisse_kodu: str):
    for tip in ["best", "hibrit", "finansal"]:
        model_yolu = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{tip}_model.pkl")
        meta_yolu  = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{tip}_meta.json")
        if os.path.exists(model_yolu):
            model = joblib.load(model_yolu)
            if os.path.exists(meta_yolu):
                with open(meta_yolu, encoding="utf-8") as _f:
                    meta = json.load(_f)
            else:
                meta = {}
            return model, meta
    return None, None


def _df_olustur(hisse_kodu: str) -> pd.DataFrame:
    df = ozellikler_hesapla(hisse_kodu)
    if df.empty:
        return df
    df, _ = lag_ekle(df)
    return df.dropna().reset_index(drop=True)


def _sharpe(getiriler: pd.Series) -> float:
    fazla = getiriler - RISKSIZ_FAIZ_GUNLUK
    std   = fazla.std()
    return round(float(fazla.mean() / std * np.sqrt(252)), 3) if std > 0 else 0.0


def _max_drawdown(deger_serisi: pd.Series) -> float:
    tepe   = deger_serisi.cummax()
    dip    = (deger_serisi - tepe) / tepe
    return round(float(dip.min() * 100), 2)


def backtest_hesapla(hisse_kodu: str) -> dict:
    hisse_kodu = hisse_kodu.upper()
    model, meta = _model_yukle(hisse_kodu)
    if model is None:
        return {"hata": "Model bulunamadi."}

    esik       = meta.get("esik", 0.5)
    ozellikler = meta.get("ozellikler", [])

    df = _df_olustur(hisse_kodu)
    if df.empty:
        return {"hata": "Veri yetersiz."}

    eksik = [c for c in ozellikler if c not in df.columns]
    if eksik:
        return {"hata": f"Eksik ozellikler: {eksik}"}

    # Holdout penceresi
    df["tarih"] = pd.to_datetime(df["tarih"])
    ho = df[(df["tarih"] >= HOLDOUT_BAS) & (df["tarih"] <= HOLDOUT_BIT)].copy()
    if len(ho) < 10:
        return {"hata": "Holdout donemi icin yeterli veri yok."}

    X_ho       = ho[ozellikler].values
    olasiliklar = model.predict_proba(X_ho)[:, 1]

    # Portföy simülasyonu (long-only)
    portfoy   = 100.0
    benchmark = 100.0
    gunluk    = []
    portfoy_seri   = []
    benchmark_seri = []

    for i in range(len(ho) - 1):
        tarih      = ho.iloc[i]["tarih"].strftime("%Y-%m-%d")
        kapanis_bu  = float(ho.iloc[i]["kapanis"])
        kapanis_son = float(ho.iloc[i + 1]["kapanis"])
        bist_getiri = float(ho.iloc[i + 1].get("bist100_getiri", 0.0))

        olasilik   = float(olasiliklar[i])
        tahmin_yon = "YÜKSELİŞ" if olasilik >= esik else "DÜŞÜŞ"
        gercek_yon = "YÜKSELİŞ" if kapanis_son > kapanis_bu else "DÜŞÜŞ"

        hisse_getiri = (kapanis_son - kapanis_bu) / kapanis_bu

        if tahmin_yon == "YÜKSELİŞ":
            # Giriş + çıkış komisyonu düşülür
            net_getiri = hisse_getiri - 2 * KOMISYON_ORAN
            portfoy *= (1 + net_getiri)
        # DÜŞÜŞ → nakit → günlük risksiz faiz
        else:
            portfoy *= (1 + RISKSIZ_FAIZ_GUNLUK)

        benchmark *= (1 + bist_getiri)

        portfoy_seri.append(round(portfoy, 4))
        benchmark_seri.append(round(benchmark, 4))

        gunluk.append({
            "tarih":        tarih,
            "kapanis":      round(kapanis_bu, 2),
            "olasilik":     round(olasilik * 100, 1),
            "tahmin_yon":   tahmin_yon,
            "gercek_yon":   gercek_yon,
            "dogru_mu":     tahmin_yon == gercek_yon,
            "hisse_getiri": round(hisse_getiri * 100, 2),
            "portfoy":      round(portfoy, 2),
            "benchmark":    round(benchmark, 2),
        })

    if not gunluk:
        return {"hata": "Simülasyon verisi olusturulamadi."}

    portfoy_s   = pd.Series(portfoy_seri)
    benchmark_s = pd.Series(benchmark_seri)

    # Günlük portföy getirileri
    portfoy_getiriler = portfoy_s.pct_change().dropna()

    # İşlem sayısı (YÜKSELİŞ tahmin edilen günler)
    yukselis_gunler = sum(1 for g in gunluk if g["tahmin_yon"] == "YÜKSELİŞ")
    dogru_sayisi    = sum(1 for g in gunluk if g["dogru_mu"])

    return {
        "hisse_kodu":       hisse_kodu,
        "baslangic":        HOLDOUT_BAS,
        "bitis":            HOLDOUT_BIT,
        "gun_sayisi":       len(gunluk),
        "model_getiri":     round((portfoy - 100), 2),
        "benchmark_getiri": round((benchmark - 100), 2),
        "sharpe":           _sharpe(portfoy_getiriler),
        "max_drawdown":     _max_drawdown(portfoy_s),
        "kazanma_orani":    round(dogru_sayisi / len(gunluk) * 100, 1),
        "islem_gunleri":    yukselis_gunler,
        "toplam_gunler":    len(gunluk),
        "gunluk":           gunluk,
    }


def tum_hisseler_backtest(hisseler: list) -> list:
    sonuclar = []
    for hisse in hisseler:
        r = backtest_hesapla(hisse)
        if "hata" not in r:
            sonuclar.append({
                "hisse_kodu":       r["hisse_kodu"],
                "model_getiri":     r["model_getiri"],
                "benchmark_getiri": r["benchmark_getiri"],
                "fark":             round(r["model_getiri"] - r["benchmark_getiri"], 2),
                "sharpe":           r["sharpe"],
                "max_drawdown":     r["max_drawdown"],
                "kazanma_orani":    r["kazanma_orani"],
            })
    sonuclar.sort(key=lambda x: -x["model_getiri"])
    return sonuclar
