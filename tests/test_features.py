"""
tests/test_features.py — features.py smoke testleri

Calistir: pytest tests/ -v
DB baglantisi gerektirmeyen pure-logic fonksiyonlari test eder.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest

from features import (
    tutarlilik_hesapla,
    lag_ekle,
    FINANSAL_OZELLIKLER,
    HIBRIT_OZELLIKLER,
    LAG_GUNLER,
    LAG_SUTUNLAR,
)


# ─── tutarlilik_hesapla ───────────────────────────────────────────────────────

def test_tutarlilik_bos_kaynak_varsayilan_degerler():
    """Kaynak verisi yoksa sabit varsayilanlar donmeli."""
    tarihler = pd.Series(["2024-01-01", "2024-01-02"])
    sonuc = tutarlilik_hesapla(pd.DataFrame(), tarihler)

    assert len(sonuc) == 2
    assert (sonuc["kaynak_sayisi"] == 0.0).all()
    assert (sonuc["konsensus"] == 0.5).all()
    assert (sonuc["std_kaynak"] == 0.0).all()


def test_tutarlilik_tek_kaynak_konsensus_belirsiz():
    """Tek kaynak oldugunda karsilastirilacak baska kaynak yok — konsensus 0.5 olmali."""
    tarihler = pd.Series(["2024-01-01"])
    kaynak_df = pd.DataFrame({
        "tarih": ["2024-01-01"],
        "kaynak": ["google"],
        "skor": [0.8],
    })
    sonuc = tutarlilik_hesapla(kaynak_df, tarihler)
    satir = sonuc[sonuc["tarih"] == "2024-01-01"]
    assert satir["konsensus"].iloc[0] == 0.5


def test_tutarlilik_iki_ayni_yonde_kaynak_tam_konsensus():
    """Iki kaynak ayni yonde gosterse konsensus 1.0 olmali."""
    tarihler = pd.Series(["2024-01-01"])
    kaynak_df = pd.DataFrame({
        "tarih": ["2024-01-01", "2024-01-01"],
        "kaynak": ["google", "bloomberg"],
        "skor": [0.6, 0.8],
    })
    sonuc = tutarlilik_hesapla(kaynak_df, tarihler)
    satir = sonuc[sonuc["tarih"] == "2024-01-01"]
    assert satir["konsensus"].iloc[0] == pytest.approx(1.0)
    assert satir["kaynak_sayisi"].iloc[0] == pytest.approx(2.0)


def test_tutarlilik_tam_zit_kaynaklar_belirsiz_konsensus():
    """Iki kaynak tam zit (+0.7 ve -0.7): ortalama=0 → yön yok → 0.5 (belirsiz)."""
    tarihler = pd.Series(["2024-01-01"])
    kaynak_df = pd.DataFrame({
        "tarih": ["2024-01-01", "2024-01-01"],
        "kaynak": ["google", "bloomberg"],
        "skor": [0.7, -0.7],
    })
    sonuc = tutarlilik_hesapla(kaynak_df, tarihler)
    satir = sonuc[sonuc["tarih"] == "2024-01-01"]
    # ort=0 → kod bilinçli 0.5 döndürür (yön sinyali yok)
    assert satir["konsensus"].iloc[0] == pytest.approx(0.5)


def test_tutarlilik_asimetrik_zit_kaynaklar_dusuk_konsensus():
    """Asimetrik zit kaynaklar: ortalama != 0 → konsensus < 1 olmali."""
    tarihler = pd.Series(["2024-01-01"])
    # ort = (0.8 + (-0.2)) / 2 = 0.3 > 0
    # sign(0.8)==sign(0.3) → evet; sign(-0.2)==sign(0.3) → hayir
    # konsensus = 1/2 = 0.5
    kaynak_df = pd.DataFrame({
        "tarih": ["2024-01-01", "2024-01-01"],
        "kaynak": ["google", "bloomberg"],
        "skor": [0.8, -0.2],
    })
    sonuc = tutarlilik_hesapla(kaynak_df, tarihler)
    satir = sonuc[sonuc["tarih"] == "2024-01-01"]
    assert satir["konsensus"].iloc[0] < 1.0


def test_tutarlilik_eksik_tarih_bos_doner():
    """Haberi olmayan tarihler NaN/0 deger almali (reindex)."""
    tarihler = pd.Series(["2024-01-01", "2024-01-03"])
    kaynak_df = pd.DataFrame({
        "tarih": ["2024-01-01"],
        "kaynak": ["google"],
        "skor": [0.5],
    })
    sonuc = tutarlilik_hesapla(kaynak_df, tarihler)
    assert len(sonuc) == 2


# ─── lag_ekle ────────────────────────────────────────────────────────────────

def test_lag_ekle_dogru_sutun_sayisi():
    """N sutun icin N * len(LAG_GUNLER) lag kolonu olusturmali."""
    df = pd.DataFrame({
        "kapanis": range(20),
        "RSI": range(20),
    })
    _, lag_cols = lag_ekle(df, sadece_sutunlar=["kapanis", "RSI"])
    assert len(lag_cols) == 2 * len(LAG_GUNLER)


def test_lag_ekle_kolonlar_dataframede_var():
    """Uretilen lag kolonlari DataFrame'de bulunmali."""
    df = pd.DataFrame({"kapanis": range(10)})
    df_lag, lag_cols = lag_ekle(df, sadece_sutunlar=["kapanis"])
    for col in lag_cols:
        assert col in df_lag.columns


def test_lag_ekle_lag1_bir_adim_gecikme():
    """lag1 kolonu bir gun onceki degeri icermeli."""
    df = pd.DataFrame({"kapanis": [10.0, 20.0, 30.0]})
    df_lag, _ = lag_ekle(df, sadece_sutunlar=["kapanis"])
    assert df_lag["kapanis_lag1"].iloc[1] == pytest.approx(10.0)
    assert df_lag["kapanis_lag1"].iloc[2] == pytest.approx(20.0)


def test_lag_ekle_lag5_bes_adim_gecikme():
    """lag5 kolonu 5 gun onceki degeri icermeli."""
    df = pd.DataFrame({"kapanis": [float(i) for i in range(10)]})
    df_lag, _ = lag_ekle(df, sadece_sutunlar=["kapanis"])
    assert df_lag["kapanis_lag5"].iloc[5] == pytest.approx(0.0)
    assert df_lag["kapanis_lag5"].iloc[9] == pytest.approx(4.0)


def test_lag_ekle_olmayan_sutun_atlanir():
    """DataFrame'de olmayan sutun icin lag kolonu uretilmemeli."""
    df = pd.DataFrame({"kapanis": range(5)})
    _, lag_cols = lag_ekle(df, sadece_sutunlar=["kapanis", "MEVCUT_DEGIL"])
    lag_isimler = [c.split("_lag")[0] for c in lag_cols]
    assert "MEVCUT_DEGIL" not in lag_isimler


def test_lag_ekle_varsayilan_sutunlar_lag_sutunlari():
    """sadece_sutunlar belirtilmezse LAG_SUTUNLAR'daki mevcut kolonlara gore lag uretmeli."""
    df = pd.DataFrame({sutun: range(20) for sutun in ["kapanis", "RSI"]})
    _, lag_cols = lag_ekle(df)
    assert any("kapanis_lag" in c for c in lag_cols)


# ─── Ozellik Listeleri Tutarliligi ───────────────────────────────────────────

def test_hibrit_finansal_iceriyor():
    """HIBRIT_OZELLIKLER, FINANSAL_OZELLIKLER'in tum elemanlarini icermeli."""
    for f in FINANSAL_OZELLIKLER:
        assert f in HIBRIT_OZELLIKLER, f"{f} HIBRIT_OZELLIKLER'de eksik"


def test_finansal_ozellikler_tekrar_yok():
    """FINANSAL_OZELLIKLER icinde tekrar eden eleman olmamali."""
    assert len(FINANSAL_OZELLIKLER) == len(set(FINANSAL_OZELLIKLER))


def test_hibrit_ozellikler_tekrar_yok():
    """HIBRIT_OZELLIKLER icinde tekrar eden eleman olmamali."""
    assert len(HIBRIT_OZELLIKLER) == len(set(HIBRIT_OZELLIKLER))


def test_lag_gunler_sirali_pozitif():
    """LAG_GUNLER pozitif tam sayilardan olusup sirali olmali."""
    assert all(g > 0 for g in LAG_GUNLER)
    assert LAG_GUNLER == sorted(LAG_GUNLER)
