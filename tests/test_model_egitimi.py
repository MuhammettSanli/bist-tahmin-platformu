"""
tests/test_model_egitimi.py — model_egitimi.py smoke testleri

Calistir: pytest tests/ -v
Gercek DB veya model dosyasi gerektirmez; saf logic fonksiyonlari test eder.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

from ml.model_egitimi import (
    hedef_ekle,
    ic_filtrele,
    _tam_ozellik_filtrele,
    esigi_optimize_et,
    xgb_olustur,
    lgbm_olustur,
)


# ─── Yardimci ────────────────────────────────────────────────────────────────

def _temiz_df(n: int = 100) -> pd.DataFrame:
    """NaN icermeyen minimal DataFrame — hedef_ekle icin."""
    np.random.seed(42)
    kapanis = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({
        "tarih":  pd.date_range("2022-01-01", periods=n, freq="B"),
        "kapanis": kapanis,
        "RSI":     np.random.uniform(30, 70, n),
        "hacim_oran": np.random.uniform(0.5, 2.0, n),
    })


def _egitim_seti(n: int = 150):
    """XGBoost/LightGBM icin train / val seti."""
    np.random.seed(42)
    X = np.random.randn(n, 5)
    y = np.random.randint(0, 2, n)
    kesme = int(n * 0.8)
    return X[:kesme], y[:kesme], X[kesme:], y[kesme:]


# ─── hedef_ekle ──────────────────────────────────────────────────────────────

def test_hedef_ekle_kolon_var():
    """Cikti DataFrame'de 'hedef' kolonu bulunmali."""
    sonuc = hedef_ekle(_temiz_df())
    assert "hedef" in sonuc.columns


def test_hedef_ekle_nan_yok():
    """hedef kolonu NaN icermemeli."""
    sonuc = hedef_ekle(_temiz_df())
    assert sonuc["hedef"].isna().sum() == 0


def test_hedef_ekle_sadece_0_1():
    """hedef degerleri yalnizca 0 veya 1 olmali."""
    sonuc = hedef_ekle(_temiz_df())
    assert set(sonuc["hedef"].unique()).issubset({0.0, 1.0})


def test_hedef_ekle_son_satir_atilir():
    """Son gun icin gercek yön bilinmiyor — iloc[:-1] ile atilmali."""
    df = _temiz_df(n=50)
    sonuc = hedef_ekle(df, esik=0.0)  # esik=0 -> gurultulu gun yok, sadece son satir atilir
    assert len(sonuc) <= len(df) - 1


def test_hedef_ekle_genis_esik_az_satir():
    """Cok genis esik (gurultulu gunler) veri azaltmali."""
    df = _temiz_df(n=200)
    dar  = hedef_ekle(df.copy(), esik=0.001)
    genis = hedef_ekle(df.copy(), esik=0.05)
    assert len(genis) <= len(dar)


# ─── ic_filtrele ─────────────────────────────────────────────────────────────

def test_ic_filtrele_yuksek_korelasyon_korunur():
    """Hedefle yuksek korelasyonlu ozellik esigi gececek."""
    np.random.seed(0)
    n = 300
    hedef = np.random.randint(0, 2, n).astype(float)
    df = pd.DataFrame({
        "hedef":     hedef,
        "guclu_f":   hedef + np.random.randn(n) * 0.05,  # ~yüksek korelasyon
        "zayif_f":   np.random.randn(n),                  # ~sifir korelasyon
    })
    secilen = ic_filtrele(df, ["guclu_f", "zayif_f"], esik=0.1)
    assert "guclu_f" in secilen


def test_ic_filtrele_dusuk_ic_atilir():
    """Dusuk IC'li ozellik esigi gecememeli (min 5 fallback yoksa)."""
    np.random.seed(1)
    n = 300
    cols = [f"f{i}" for i in range(10)]
    df = pd.DataFrame({"hedef": np.random.randint(0, 2, n).astype(float)})
    for c in cols:
        df[c] = np.random.randn(n)  # hedef ile korelasyonsuz
    secilen = ic_filtrele(df, cols, esik=0.5)
    # Esik cok yuksek → hic gecemez → fallback: tum ozellikler donmeli
    assert secilen == cols


def test_ic_filtrele_en_az_5_fallback():
    """3 ozellik olup hicbiri esigi gecemezse 3'u (hepsi) donmeli."""
    np.random.seed(2)
    n = 200
    df = pd.DataFrame({
        "hedef": np.random.randint(0, 2, n).astype(float),
        "a": np.random.randn(n),
        "b": np.random.randn(n),
        "c": np.random.randn(n),
    })
    secilen = ic_filtrele(df, ["a", "b", "c"], esik=0.99)
    assert set(secilen) == {"a", "b", "c"}


def test_ic_filtrele_mevcut_olmayan_kolon_hata_vermez():
    """DataFrame'de olmayan kolon IC hesabinda atlanmali, hata vermemeli."""
    df = pd.DataFrame({"hedef": [1, 0, 1], "var": [0.5, 0.6, 0.7]})
    # 2 ozellik esigi gesse bile fallback <5 kurali tam listeyi dondurur
    # Onemli: hata VERMEMELI
    secilen = ic_filtrele(df, ["var", "yok"], esik=0.0)
    assert isinstance(secilen, list)
    assert "var" in secilen


# ─── _tam_ozellik_filtrele ───────────────────────────────────────────────────

def test_tam_filtrele_hayatta_kalan_korunur():
    """IC'den gecen ozellik ve lag'leri listede kalmali."""
    tam_ham = ["RSI", "RSI_lag1", "RSI_lag2", "hacim_oran", "hacim_oran_lag1"]
    secilen = _tam_ozellik_filtrele(tam_ham, ["RSI"])
    assert "RSI" in secilen
    assert "RSI_lag1" in secilen
    assert "RSI_lag2" in secilen


def test_tam_filtrele_elenen_ve_laglar_kaldirilir():
    """IC'den gecemeyen ozellik ve laglarinin listeden cikmasi lazim."""
    tam_ham = ["RSI", "RSI_lag1", "hacim_oran", "hacim_oran_lag1"]
    secilen = _tam_ozellik_filtrele(tam_ham, ["RSI"])
    assert "hacim_oran" not in secilen
    assert "hacim_oran_lag1" not in secilen


def test_tam_filtrele_orijinal_liste_degismez():
    """Fonksiyon tam_ham listesini in-place degistirmemeli."""
    tam_ham = ["RSI", "RSI_lag1", "hacim_oran"]
    kopyasi = tam_ham[:]
    _tam_ozellik_filtrele(tam_ham, ["RSI"])
    assert tam_ham == kopyasi


# ─── esigi_optimize_et ───────────────────────────────────────────────────────

def test_esigi_optimize_et_aralik():
    """Optimize edilen esik 0.30-0.70 araliginda olmali."""
    X_tr, y_tr, X_val, y_val = _egitim_seti()
    m = xgb_olustur()
    m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    esik = esigi_optimize_et(m, X_val, y_val)
    assert 0.30 <= esik <= 0.70


def test_esigi_optimize_et_adim_hassasiyeti():
    """Esik 0.05 adimlarla optimize edildiginden 0.05'in katlari olmali."""
    X_tr, y_tr, X_val, y_val = _egitim_seti()
    m = xgb_olustur()
    m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    esik = esigi_optimize_et(m, X_val, y_val)
    # 0.30, 0.35, 0.40 ... 0.70 — tam sayi kontrolu
    assert round(esik * 100) % 5 == 0


# ─── Model Fabrika Fonksiyonlari ─────────────────────────────────────────────

def test_xgb_olustur_dogru_tip():
    assert isinstance(xgb_olustur(), XGBClassifier)


def test_xgb_olustur_scale_pos_weight():
    m = xgb_olustur(scale_pos_weight=3.0)
    assert m.scale_pos_weight == pytest.approx(3.0)


def test_lgbm_olustur_dogru_tip():
    assert isinstance(lgbm_olustur(), LGBMClassifier)


def test_lgbm_olustur_scale_pos_weight():
    m = lgbm_olustur(scale_pos_weight=2.5)
    assert m.scale_pos_weight == pytest.approx(2.5)


def test_xgb_early_stopping_ayarli():
    """XGBoost early_stopping_rounds parametresi ayarlanmis olmali."""
    m = xgb_olustur()
    assert m.early_stopping_rounds == 30


def test_xgb_fit_predict_calisir():
    """XGBoost'un uctan uca fit + predict_proba zinciri hata vermemeli."""
    X_tr, y_tr, X_val, y_val = _egitim_seti()
    m = xgb_olustur()
    m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    proba = m.predict_proba(X_val)
    assert proba.shape == (len(X_val), 2)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)


def test_lgbm_fit_predict_calisir():
    """LightGBM'in uctan uca fit + predict_proba zinciri hata vermemeli."""
    from lightgbm import early_stopping as lgbm_es, log_evaluation as lgbm_le
    X_tr, y_tr, X_val, y_val = _egitim_seti()
    m = lgbm_olustur()
    m.fit(X_tr, y_tr,
          eval_set=[(X_val, y_val)],
          callbacks=[lgbm_es(30, verbose=False), lgbm_le(-1)])
    proba = m.predict_proba(X_val)
    assert proba.shape == (len(X_val), 2)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)
