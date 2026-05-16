"""
model_egitimi.py — XGBoost ile finansal ve hibrit model egitimi
Calistir: python model_egitimi.py

Her hisse icin iki model egitilir:
  1. sadece_finansal : fiyat + hacim + teknik gostergeler + lag ozellikler
  2. hibrit          : finansal + BERT duygu skoru + duygu lag ozellikleri

XGBoost secilme nedeni:
  - ~1200 satir egitim verisiyle LSTM "her seyi YUKSELIS say" tuzagina duser
  - XGBoost kucuk veri setlerinde guclu, overfitting'e direncli
  - Lag ozelliklerle temporal baglamlari yakalar (pencere yerine)
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import os
import json
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import accuracy_score, f1_score, classification_report

warnings.filterwarnings("ignore", message="X does not have valid feature names")
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier, early_stopping as lgbm_early_stopping, log_evaluation as lgbm_log_evaluation
from database import HISSELER
from features import (
    ozellikler_hesapla, lag_ekle,
    FINANSAL_OZELLIKLER, HIBRIT_OZELLIKLER, LAG_GUNLER,
    finansal_ozellikler_al, hibrit_ozellikler_al,
)


# ─── Ayarlar ─────────────────────────────────────────────────────────────────
HOLDOUT_BAS     = "2025-10-01"
HOLDOUT_BIT     = "2026-04-14"
VAL_ORANI       = 0.10
MODELLER_KLASOR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "models")

# Walk-forward: kac yil train ederek test edilecek
# Ornek: [("2021-01-01","2023-12-31","2024-01-01","2024-12-31"), ...]
WF_KATLARI = [
    ("2021-01-01", "2023-06-30", "2023-07-01", "2023-12-31"),
    ("2021-01-01", "2024-06-30", "2024-07-01", "2024-12-31"),
    ("2021-01-01", "2025-06-30", "2025-07-01", "2026-04-14"),
]

# ─── Veri Hazirlama ───────────────────────────────────────────────────────────

def hedef_ekle(df: pd.DataFrame, esik: float = 0.01) -> pd.DataFrame:
    """Hedef kolonu ekler ve gürültülü günleri atar. features.py'nin üstüne eklenir."""
    gunluk_getiri = (df["kapanis"].shift(-1) - df["kapanis"]) / df["kapanis"]
    df = df.copy()
    df["hedef"] = np.nan
    df.loc[gunluk_getiri >  esik, "hedef"] = 1
    df.loc[gunluk_getiri < -esik, "hedef"] = 0
    return df.dropna(subset=["hedef"]).dropna().iloc[:-1].reset_index(drop=True)


def lag_ozellikler_ekle(df: pd.DataFrame, ozellikler: list) -> tuple:
    """features.lag_ekle() wrapperi — sadece ozellik listesinde olan lag'leri dondurur."""
    df, tum_lag_cols = lag_ekle(df)
    secilen_lag_cols = [c for c in tum_lag_cols
                        if any(c.startswith(o + "_lag") for o in ozellikler)]
    return df, secilen_lag_cols


# ─── Model ────────────────────────────────────────────────────────────────────

def xgb_olustur(scale_pos_weight: float = 1.0) -> XGBClassifier:
    """
    XGBoost siniflandirici — kucuk finansal veri setleri icin optimize edilmis.
    scale_pos_weight ile sinif dengesizligi duzeltilir.
    """
    return XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        early_stopping_rounds=30,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )


def lgbm_olustur(scale_pos_weight: float = 1.0) -> LGBMClassifier:
    return LGBMClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=20,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )


def esigi_optimize_et(model, X_val: np.ndarray, y_val: np.ndarray) -> float:
    """Validation setinde macro-F1 skorunu maksimize eden esigi bulur.
    Macro F1: hem DUSUS hem YUKSELIS siniflarini dengeli degerlendirur,
    modelin sadece bir sinifi tahmin etmesini onler."""
    tahminler = model.predict_proba(X_val)[:, 1]
    en_iyi_esik, en_iyi_f1 = 0.5, 0.0
    for esik in np.arange(0.30, 0.71, 0.05):
        y_pred = (tahminler >= esik).astype(int)
        f = f1_score(y_val, y_pred, zero_division=0, average="macro")
        if f > en_iyi_f1:
            en_iyi_f1   = f
            en_iyi_esik = esik
    return round(float(en_iyi_esik), 2)


# ─── Walk-Forward Validation ─────────────────────────────────────────────────

def walk_forward_degerlendir(df_full: pd.DataFrame, ozellikler: list,
                              tam_ozellikler: list,
                              algoritma: str = "xgb") -> dict:
    """
    3 katmanli walk-forward validation:
      Kat 1: 2021-2023 egit → 2023H2 test
      Kat 2: 2021-2024 egit → 2024H2 test
      Kat 3: 2021-2025 egit → 2025H2-2026 test
    Her katta ortalama accuracy ve F1 hesapla.
    """
    acc_listesi, f1_listesi = [], []

    for train_bas, train_bit, test_bas, test_bit in WF_KATLARI:
        train_mask = (df_full["tarih"] >= train_bas) & (df_full["tarih"] <= train_bit)
        test_mask  = (df_full["tarih"] >= test_bas)  & (df_full["tarih"] <= test_bit)

        df_tr = df_full[train_mask].dropna(subset=tam_ozellikler + ["hedef"])
        df_te = df_full[test_mask].dropna(subset=tam_ozellikler  + ["hedef"])

        if len(df_tr) < 100 or len(df_te) < 20:
            continue

        X_tr = df_tr[tam_ozellikler].values; y_tr = df_tr["hedef"].values
        X_te = df_te[tam_ozellikler].values; y_te = df_te["hedef"].values

        # Val seti: train'in son %10'u
        val_cut = int(len(X_tr) * 0.90)
        X_val, y_val = X_tr[val_cut:], y_tr[val_cut:]
        X_tr,  y_tr  = X_tr[:val_cut],  y_tr[:val_cut]

        n_pos = y_tr.sum()
        n_neg = len(y_tr) - n_pos
        spw   = n_neg / n_pos if n_pos > 0 else 1.0

        m = _model_fit(algoritma, X_tr, y_tr, X_val, y_val, spw)

        esik = esigi_optimize_et(m, X_val, y_val)
        y_pred = (m.predict_proba(X_te)[:, 1] >= esik).astype(int)

        acc_listesi.append(accuracy_score(y_te, y_pred))
        f1_listesi.append(f1_score(y_te, y_pred, zero_division=0))

    if not acc_listesi:
        return {"wf_acc_ort": None, "wf_f1_ort": None, "wf_katlar": 0}

    return {
        "wf_acc_ort": round(float(np.mean(acc_listesi)), 6),
        "wf_f1_ort":  round(float(np.mean(f1_listesi)),  6),
        "wf_acc_std": round(float(np.std(acc_listesi)),   6),
        "wf_f1_std":  round(float(np.std(f1_listesi)),    6),
        "wf_katlar":  len(acc_listesi),
        "wf_detay":   [{"acc": round(a, 4), "f1": round(f, 4)}
                       for a, f in zip(acc_listesi, f1_listesi)],
    }


# ─── Tek Model Egitimi ────────────────────────────────────────────────────────

def _model_fit(model_turu: str, X_tr, y_tr, X_val, y_val, spw: float):
    if model_turu == "xgb":
        m = xgb_olustur(spw)
        m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    else:
        m = lgbm_olustur(spw)
        m.fit(X_tr, y_tr,
              eval_set=[(X_val, y_val)],
              callbacks=[lgbm_early_stopping(30, verbose=False),
                         lgbm_log_evaluation(-1)])
    return m


def ic_filtrele(df: pd.DataFrame, ozellikler: list, esik: float = 0.02) -> list:
    """IC < esik olan ozellikleri at — sadece egitim verisi uzerinde cagrilmali."""
    secilen = []
    for col in ozellikler:
        if col in df.columns:
            ic = abs(df[col].corr(df["hedef"]))
            if ic >= esik or np.isnan(ic):
                secilen.append(col)
    # En az 5 ozellik kalsin
    if len(secilen) < 5:
        secilen = ozellikler
    return secilen


def _tam_ozellik_filtrele(tam_ham: list, ozellikler_filtrelenmis: list) -> list:
    """IC filtresi sonrasi tam ozellik listesinden elenen ozelliklerin lag'lerini de kaldir."""
    return [c for c in tam_ham
            if c in ozellikler_filtrelenmis
            or any(c.startswith(o + "_lag") for o in ozellikler_filtrelenmis)]


def tek_model_egit(df: pd.DataFrame, ozellikler: list, etiket: str,
                   hisse_kodu: str) -> dict:
    # Lag ozelliklerini tam veri seti uzerinde hesapla (zaman serisi butunlugu icin)
    df2, lag_cols = lag_ozellikler_ekle(df.copy(), ozellikler)
    tam_ozellikler_ham = ozellikler + [c for c in lag_cols if c in df2.columns]
    df2 = df2.dropna(subset=tam_ozellikler_ham + ["hedef"]).reset_index(drop=True)

    y = df2["hedef"].values

    # Sabit tarih bazli holdout — her run ayni periyodu test eder
    # train: yalnizca holdout oncesi — post-holdout verisi egitimi kirletmesin
    test_mask  = (df2["tarih"] >= HOLDOUT_BAS) & (df2["tarih"] <= HOLDOUT_BIT)
    train_mask = df2["tarih"] < HOLDOUT_BAS

    df_tr = df2[train_mask].reset_index(drop=True)
    df_te = df2[test_mask].reset_index(drop=True)

    if len(df_te) < 20:
        # Sabit holdout yeterli veri yoksa yuzde bazliya don
        n = len(df2)
        test_boyut  = int(n * 0.20)
        val_boyut   = int(n * VAL_ORANI)
        train_bitis = n - test_boyut - val_boyut
        # IC filtresi: sadece training kismi uzerinde — test bilgisi sizmasin
        ozellikler    = ic_filtrele(df2.iloc[:train_bitis], ozellikler)
        tam_ozellikler = _tam_ozellik_filtrele(tam_ozellikler_ham, ozellikler)
        X_df  = df2[tam_ozellikler]
        X_tr  = X_df.iloc[:train_bitis].values
        X_val = X_df.iloc[train_bitis: train_bitis + val_boyut].values
        X_te  = X_df.iloc[train_bitis + val_boyut:].values
        y_tr  = y[:train_bitis]
        y_val = y[train_bitis: train_bitis + val_boyut]
        y_te  = y[train_bitis + val_boyut:]
    else:
        # IC filtresi: sadece df_tr uzerinde — holdout test seti gorulmemis kalsin
        ozellikler    = ic_filtrele(df_tr, ozellikler)
        tam_ozellikler = _tam_ozellik_filtrele(tam_ozellikler_ham, ozellikler)
        val_boyut   = int(len(df_tr) * VAL_ORANI)
        train_bitis = len(df_tr) - val_boyut
        X_tr  = df_tr[tam_ozellikler].iloc[:train_bitis].values
        X_val = df_tr[tam_ozellikler].iloc[train_bitis:].values
        X_te  = df_te[tam_ozellikler].values
        y_tr  = df_tr["hedef"].values[:train_bitis]
        y_val = df_tr["hedef"].values[train_bitis:]
        y_te  = df_te["hedef"].values

    n_pos = y_tr.sum()
    n_neg = len(y_tr) - n_pos
    spw   = n_neg / n_pos if n_pos > 0 else 1.0

    # Model secimi validation setinde yapilir — test seti yalnizca raporlama icin
    kazanan_model, kazanan_acc_val, kazanan_esik, kazanan_turu = None, -1, 0.5, "xgb"
    for mt in ["xgb", "lgbm"]:
        m = _model_fit(mt, X_tr, y_tr, X_val, y_val, spw)
        esik = esigi_optimize_et(m, X_val, y_val)
        pred = (m.predict_proba(X_val)[:, 1] >= esik).astype(int)
        a = accuracy_score(y_val, pred)
        if a > kazanan_acc_val:
            kazanan_model, kazanan_acc_val = m, a
            kazanan_esik, kazanan_turu = esik, mt

    # Secilen modeli holdout test setinde degerlendir (sadece raporlama)
    y_pred     = (kazanan_model.predict_proba(X_te)[:, 1] >= kazanan_esik).astype(int)
    kazanan_acc = accuracy_score(y_te, y_pred)
    kazanan_f1  = f1_score(y_te, y_pred, zero_division=0, average="macro")
    f1_pos      = f1_score(y_te, y_pred, zero_division=0)

    wf = walk_forward_degerlendir(df2, ozellikler, tam_ozellikler, algoritma=kazanan_turu)

    print(f"    [{etiket}|{kazanan_turu.upper()}] HoldOut -> Acc:{kazanan_acc:.4f} F1:{kazanan_f1:.4f} Esik:{kazanan_esik}")
    if wf["wf_katlar"] > 0:
        print(f"    [{etiket}] WalkFwd -> Acc:{wf['wf_acc_ort']:.4f}"
              f"(+-{wf['wf_acc_std']:.4f}) F1:{wf['wf_f1_ort']:.4f}"
              f"(+-{wf['wf_f1_std']:.4f}) [{wf['wf_katlar']} kat]")
        for i, d in enumerate(wf["wf_detay"]):
            print(f"      Kat{i+1}: Acc={d['acc']:.4f} F1={d['f1']:.4f}")
    print(classification_report(y_te, y_pred,
                                 target_names=["DUSUS", "YUKSELIS"],
                                 zero_division=0))

    os.makedirs(MODELLER_KLASOR, exist_ok=True)
    joblib.dump(kazanan_model,
                os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{etiket}_model.pkl"))
    meta = {"ozellikler": tam_ozellikler, "esik": kazanan_esik,
            "algoritma": kazanan_turu}
    with open(os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{etiket}_meta.json"),
              "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False)

    return {
        "accuracy": round(kazanan_acc, 6),
        "f1": round(f1_pos, 6),
        "f1_macro": round(kazanan_f1, 6),
        "esik": kazanan_esik,
        "algoritma": kazanan_turu,
        "wf": wf,
    }


# ─── Hisse Egitimi ────────────────────────────────────────────────────────────

def hisse_egit(hisse_kodu: str):
    print(f"\n{'='*55}")
    print(f"[{hisse_kodu}] XGBoost Model Egitimi")
    print(f"{'='*55}")

    df = ozellikler_hesapla(hisse_kodu)
    if df.empty:
        print("  Veri bulunamadi, atlaniyor.")
        return

    import shutil

    en_iyi_sonuc = None

    for esik in [0.005, 0.01]:
        df_e = hedef_ekle(df.copy(), esik=esik)
        if len(df_e) < 200:
            print(f"  [esik={esik}] Yetersiz veri ({len(df_e)} satir), atlaniyor.")
            continue

        etiket_esik = f"{'05' if esik == 0.005 else '1'}pct"
        print(f"\n  --- Esik: ±%{esik*100:.1f} | {len(df_e)} satir ---")

        fin_ozellikler = finansal_ozellikler_al(hisse_kodu)
        hib_ozellikler = hibrit_ozellikler_al(hisse_kodu)

        print(f"  [1/2] Finansal ({etiket_esik}) egitiliyor...")
        m_fin = tek_model_egit(df_e, fin_ozellikler,
                               f"finansal_{etiket_esik}", hisse_kodu)

        print(f"  [2/2] Hibrit ({etiket_esik}) egitiliyor...")
        m_hib = tek_model_egit(df_e, hib_ozellikler,
                               f"hibrit_{etiket_esik}", hisse_kodu)

        iy_acc = round(m_hib["accuracy"] - m_fin["accuracy"], 6)
        iy_f1  = round(m_hib["f1_macro"] - m_fin["f1_macro"], 6)

        def _wf_acc(m):
            wf = m.get("wf", {})
            return wf.get("wf_acc_ort") if wf.get("wf_katlar", 0) > 0 else m["accuracy"]

        fin_wf = _wf_acc(m_fin)
        hib_wf = _wf_acc(m_hib)
        print(f"  Finansal -> WalkFwd:%{fin_wf*100:.1f} HoldOut:%{m_fin['accuracy']*100:.1f} F1:{m_fin['f1_macro']:.3f}  |  "
              f"Hibrit -> WalkFwd:%{hib_wf*100:.1f} HoldOut:%{m_hib['accuracy']*100:.1f} F1:{m_hib['f1_macro']:.3f}")

        for tip, m, wf_acc in [("finansal", m_fin, fin_wf), ("hibrit", m_hib, hib_wf)]:
            if en_iyi_sonuc is None or wf_acc > en_iyi_sonuc["acc"]:
                en_iyi_sonuc = {
                    "esik": esik, "etiket": etiket_esik,
                    "tip": tip, "acc": wf_acc,
                    "holdout_acc": m["accuracy"],
                    "f1_macro": m["f1_macro"], "algoritma": m["algoritma"],
                    "m_fin": m_fin, "m_hib": m_hib,
                    "iy_acc": iy_acc, "iy_f1": iy_f1,
                }

    if en_iyi_sonuc is None:
        print("  Hic gecerli sonuc bulunamadi.")
        return

    # En iyi kombinasyonu best olarak kaydet
    es = en_iyi_sonuc
    kaynak_model = os.path.join(MODELLER_KLASOR,
                                f"{hisse_kodu}_{es['tip']}_{es['etiket']}_model.pkl")
    kaynak_meta  = os.path.join(MODELLER_KLASOR,
                                f"{hisse_kodu}_{es['tip']}_{es['etiket']}_meta.json")
    hedef_model  = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_best_model.pkl")
    hedef_meta   = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_best_meta.json")
    shutil.copy2(kaynak_model, hedef_model)
    shutil.copy2(kaynak_meta,  hedef_meta)

    metriks = {
        "hisse_kodu":      hisse_kodu,
        "en_iyi_esik":     es["esik"],
        "en_iyi_tip":      es["tip"],
        "en_iyi_algo":     es["algoritma"],
        "sadece_finansal": es["m_fin"],
        "hibrit":          es["m_hib"],
        "iyilesme_acc":    es["iy_acc"],
        "iyilesme_f1":     es["iy_f1"],
    }
    yol = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_metriks.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(metriks, f, indent=2, ensure_ascii=False)

    print(f"\n  *** EN IYI: esik=±%{es['esik']*100:.1f} | "
          f"[{es['tip'].upper()}|{es['algoritma'].upper()}] | "
          f"WalkFwd:%{es['acc']*100:.1f} HoldOut:%{es['holdout_acc']*100:.1f} F1:{es['f1_macro']:.3f} ***")
    print(f"  Metriks: {yol}")


# ─── Ana Akis ────────────────────────────────────────────────────────────────

def main():
    print("XGBoost Model Egitimi - Finansal vs Hibrit")
    print(f"Ozellikler: {len(FINANSAL_OZELLIKLER)} finansal + 8 duygu + 3 tutarlilik (kaynak_sayisi/konsensus/std_kaynak) + lag ozellikleri")
    print(f"Lag gunler: {LAG_GUNLER}\n")
    for hisse_kodu in HISSELER:
        hisse_egit(hisse_kodu)
    print("\nTum modeller egitildi.")


if __name__ == "__main__":
    main()
