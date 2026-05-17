"""
app.py — Flask Backend API
Çalıştır: python app.py

Endpoint'ler:
  GET /                              → index.html
  GET /api/hisseler                  → takip edilen 10 hisse listesi
  GET /api/fiyat/<hisse_kodu>        → son 90 günlük OHLCV verisi (JSON)
  GET /api/duygu/<hisse_kodu>        → günlük duygu skoru serisi (JSON)
  GET /api/tahmin/<hisse_kodu>       → XGBoost/LightGBM tahmini: YÜKSELİŞ/DÜŞÜŞ + güven %
  GET /api/karsilastirma/<hisse_kodu>→ iki modelin accuracy/F1 karşılaştırması
"""

import os
from dotenv import load_dotenv
load_dotenv()
import json
import sqlite3
import threading
import subprocess
import sys
import hashlib
import time
from functools import wraps
import numpy as np
import joblib
import pandas as pd
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
from apscheduler.schedulers.background import BackgroundScheduler
from database import DB_YOLU, HISSELER
from model_utils import CalibreliModel  # noqa: F401 — pickle deserialization için gerekli
from features import ozellikler_hesapla, lag_ekle, HIBRIT_OZELLIKLER

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY ortam değişkeni ayarlanmamış.")

ADMIN_HASH = os.environ.get("ADMIN_SIFRE_HASH")
if not ADMIN_HASH:
    raise RuntimeError("ADMIN_SIFRE_HASH ortam değişkeni ayarlanmamış.")


def login_gerekli(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"hata": "Yetkisiz. Lütfen giriş yapın."}), 401
        return f(*args, **kwargs)
    return decorated

MODELLER_KLASOR = "models"
KLASOR          = os.path.dirname(os.path.abspath(__file__))
PIPELINE_LOG    = os.path.join(KLASOR, "logs", "pipeline_log.txt")
HOLDOUT_BAS     = "2025-10-01"  # model_egitimi.py ile senkron tutulmalı

_pipeline_durum = {"calisiyor": False, "mod": None, "son_calisma": None, "son_sonuc": None}
_pipeline_kilit = threading.Lock()

# ─── Model Onbellegi ──────────────────────────────────────────────────────────
_model_cache = {}
_meta_cache  = {}

def model_yukle(hisse_kodu: str, tip: str = "best"):
    """
    tip: "best" (otomatik secim), "hibrit" veya "finansal"
    "best" → model_egitimi.py tarafindan secilen en iyi model kullanilir.
    XGBoost modeli ve meta (ozellikler + esik) dondurur.
    """
    anahtar = f"{hisse_kodu}_{tip}"
    if anahtar not in _model_cache:
        model_yolu = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{tip}_model.pkl")
        meta_yolu  = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{tip}_meta.json")
        # best modeli yoksa hibrit, o da yoksa finansale don
        if not os.path.exists(model_yolu):
            for fallback in ["hibrit", "finansal"]:
                model_yolu = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{fallback}_model.pkl")
                meta_yolu  = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_{fallback}_meta.json")
                if os.path.exists(model_yolu):
                    break
            else:
                return None, None
        _model_cache[anahtar] = joblib.load(model_yolu)
        if os.path.exists(meta_yolu):
            with open(meta_yolu, encoding="utf-8") as f:
                _meta_cache[anahtar] = json.load(f)
        else:
            _meta_cache[anahtar] = {"ozellikler": HIBRIT_OZELLIKLER, "esik": 0.5}
    return _model_cache[anahtar], _meta_cache[anahtar]


# ─── DB Yardımcıları ─────────────────────────────────────────────────────────

def db_sorgu(sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    return rows


# ─── Endpoint'ler ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/api/hisseler")
def hisseler_listesi():
    rows = db_sorgu("SELECT hisse_kodu, sirket_adi FROM hisseler ORDER BY hisse_kodu")
    return jsonify(rows)


@app.route("/api/fiyat/<hisse_kodu>")
def fiyat_verisi(hisse_kodu: str):
    hisse_kodu = hisse_kodu.upper()
    rows = db_sorgu(
        "SELECT tarih, acilis, kapanis, yuksek, dusuk, hacim "
        "FROM gunluk_fiyatlar WHERE hisse_kodu = ? "
        "ORDER BY tarih DESC LIMIT 90",
        (hisse_kodu,)
    )
    rows.reverse()  # Kronolojik sıra (en eskiden en yeniye)
    return jsonify(rows)


@app.route("/api/duygu/<hisse_kodu>")
def duygu_verisi(hisse_kodu: str):
    hisse_kodu = hisse_kodu.upper()
    rows = db_sorgu(
        "SELECT tarih, ortalama_skor, kayit_sayisi "
        "FROM gunluk_duygu WHERE hisse_kodu = ? "
        "ORDER BY tarih DESC LIMIT 90",
        (hisse_kodu,)
    )
    rows.reverse()
    return jsonify(rows)


def df_olustur(hisse_kodu: str, gun_sayisi: int = 180) -> pd.DataFrame:
    """features.py üzerinden tüm özellikleri hesaplar + lag ekler."""
    df = ozellikler_hesapla(hisse_kodu, gun_sayisi=gun_sayisi)
    if df.empty:
        return df
    df, _ = lag_ekle(df)
    return df.dropna().reset_index(drop=True)


@app.route("/api/tahmin/<hisse_kodu>")
def tahmin_yap(hisse_kodu: str):
    hisse_kodu = hisse_kodu.upper()

    model, meta = model_yukle(hisse_kodu, tip="best")
    if model is None:
        return jsonify({"hata": f"[{hisse_kodu}] icin egitilmis model bulunamadi."}), 404

    optimal_esik   = meta.get("esik", 0.5)
    tam_ozellikler = meta.get("ozellikler", HIBRIT_OZELLIKLER)

    df = df_olustur(hisse_kodu, gun_sayisi=120)
    if df.empty:
        return jsonify({"hata": "Yeterli fiyat verisi yok."}), 400

    son_satir = df.iloc[[-1]]
    eksik = [c for c in tam_ozellikler if c not in son_satir.columns]
    if eksik:
        return jsonify({"hata": f"Eksik ozellikler: {eksik}"}), 500

    X        = son_satir[tam_ozellikler]
    olasilik = float(model.predict_proba(X)[0][1])
    yon      = "YÜKSELİŞ" if olasilik >= optimal_esik else "DÜŞÜŞ"
    guven    = round(olasilik * 100 if olasilik >= optimal_esik else (1 - olasilik) * 100, 1)

    metriks_yolu = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_metriks.json")
    model_bilgi  = {}
    if os.path.exists(metriks_yolu):
        with open(metriks_yolu, encoding="utf-8") as mf:
            m = json.load(mf)
        model_bilgi = {
            "model_tipi":  m.get("en_iyi_tip", "?"),
            "algoritma":   m.get("en_iyi_algo", "xgb").upper(),
            "esik_filtre": f"±%{m.get('en_iyi_esik', 0.01)*100:.1f}",
        }

    son_duygu = float(df["duygu_skoru"].iloc[-1])

    return jsonify({
        "hisse_kodu":      hisse_kodu,
        "son_tarih":       str(df["tarih"].iloc[-1])[:10],
        "son_kapanis":     float(df["kapanis"].iloc[-1]),
        "duygu_skoru":     round(son_duygu, 4) if abs(son_duygu) > 0.0001 else None,
        "tahmin_yon":      yon,
        "yukselis_olasiligi": round(olasilik * 100, 1),  # ham olasılık her zaman
        "guven_yuzdesi":   guven,
        "optimal_esik":    optimal_esik,
        **model_bilgi,
    })


@app.route("/api/sinyal_gecmisi/<hisse_kodu>")
def sinyal_gecmisi(hisse_kodu: str):
    """
    Son 30 işlem gününün geriye dönük tahmin geçmişi.
    Her gün için: tahmin yönü, gerçek yön, doğru mu?
    """
    hisse_kodu = hisse_kodu.upper()
    model, meta = model_yukle(hisse_kodu, tip="best")
    if model is None:
        return jsonify({"hata": f"[{hisse_kodu}] model bulunamadi."}), 404

    optimal_esik   = meta.get("esik", 0.5)
    tam_ozellikler = meta.get("ozellikler", HIBRIT_OZELLIKLER)

    df = df_olustur(hisse_kodu, gun_sayisi=300)
    if df.empty or len(df) < 5:
        return jsonify({"hata": "Yeterli veri yok."}), 400

    # Sadece holdout donemini goster — egitim verisi uzerindeki tahminler
    # modelin kendi egitim setindeki basarisini olcer, kullaniciya yaniltici bilgi verir
    df = df[df["tarih"] >= HOLDOUT_BAS].reset_index(drop=True)
    if len(df) < 5:
        return jsonify({"hata": "Holdout donemi icin yeterli veri yok."}), 400

    eksik = [c for c in tam_ozellikler if c not in df.columns]
    if eksik:
        return jsonify({"hata": f"Eksik ozellikler: {eksik}"}), 500

    X_all       = df[tam_ozellikler]
    olasiliklar = model.predict_proba(X_all)[:, 1]

    # Son 30 gün (son satır hariç — gerçek yön bilinmiyor)
    son_n  = min(30, len(df) - 1)
    gecmis = []
    for i in range(len(df) - son_n - 1, len(df) - 1):
        tarih       = str(df["tarih"].iloc[i])[:10]
        kapanis_bu  = float(df["kapanis"].iloc[i])
        kapanis_son = float(df["kapanis"].iloc[i + 1])
        olasilik    = float(olasiliklar[i])
        tahmin_yon  = "YÜKSELİŞ" if olasilik >= optimal_esik else "DÜŞÜŞ"
        gercek_yon  = "YÜKSELİŞ" if kapanis_son > kapanis_bu else "DÜŞÜŞ"
        guven       = round(olasilik * 100 if olasilik >= optimal_esik else (1 - olasilik) * 100, 1)
        gecmis.append({
            "tarih":       tarih,
            "kapanis":     round(kapanis_bu, 2),
            "tahmin_yon":  tahmin_yon,
            "gercek_yon":  gercek_yon,
            "dogru_mu":    tahmin_yon == gercek_yon,
            "guven":       guven,
            "olasilik":    round(olasilik, 4),
        })

    dogru_sayisi = sum(1 for g in gecmis if g["dogru_mu"])

    # Yükseliş ve düşüş tahminleri için ayrı doğruluk
    yuk_tahminler = [g for g in gecmis if g["tahmin_yon"] == "YÜKSELİŞ"]
    dus_tahminler = [g for g in gecmis if g["tahmin_yon"] == "DÜŞÜŞ"]
    yuk_dogru = sum(1 for g in yuk_tahminler if g["dogru_mu"])
    dus_dogru = sum(1 for g in dus_tahminler if g["dogru_mu"])

    return jsonify({
        "hisse_kodu":      hisse_kodu,
        "toplam":          len(gecmis),
        "dogru_sayisi":    dogru_sayisi,
        "dogruluk":        round(dogru_sayisi / len(gecmis) * 100, 1) if gecmis else 0,
        "yukselis_toplam": len(yuk_tahminler),
        "yukselis_dogru":  yuk_dogru,
        "yukselis_acc":    round(yuk_dogru / len(yuk_tahminler) * 100, 1) if yuk_tahminler else None,
        "dusus_toplam":    len(dus_tahminler),
        "dusus_dogru":     dus_dogru,
        "dusus_acc":       round(dus_dogru / len(dus_tahminler) * 100, 1) if dus_tahminler else None,
        "gecmis":          list(reversed(gecmis)),
    })


@app.route("/api/tum_hisseler_ozet")
def tum_hisseler_ozet():
    """Tüm hisseler için metriks özetini döndürür."""
    sonuc = []
    for hisse_kodu, sirket_adi in HISSELER.items():
        metriks_yolu = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_metriks.json")
        if not os.path.exists(metriks_yolu):
            continue
        with open(metriks_yolu, encoding="utf-8") as f:
            m = json.load(f)
        en_iyi_tip  = m.get("en_iyi_tip", "?")
        en_iyi_algo = m.get("en_iyi_algo", "?").upper()
        en_iyi_esik = m.get("en_iyi_esik", 0.01)
        # JSON key: "sadece_finansal" veya "hibrit"
        json_key = "sadece_finansal" if en_iyi_tip == "finansal" else en_iyi_tip
        m_data = m.get(json_key, {})
        wf_acc      = m_data.get("wf_acc") or m_data.get("accuracy", 0)
        holdout_acc = m_data.get("accuracy", 0)
        f1          = m_data.get("f1_macro", 0)
        sonuc.append({
            "hisse_kodu":   hisse_kodu,
            "sirket_adi":   sirket_adi,
            "model_tipi":   en_iyi_tip,
            "algoritma":    en_iyi_algo,
            "esik":         f"±%{en_iyi_esik * 100:.1f}",
            "accuracy":     round(wf_acc * 100, 1),
            "holdout_acc":  round(holdout_acc * 100, 1),
            "f1_macro":     round(f1, 3),
        })
    sonuc.sort(key=lambda x: -x["accuracy"])
    return jsonify(sonuc)


@app.route("/api/duygu_trend/<hisse_kodu>")
def duygu_trend(hisse_kodu: str):
    """
    Hisse icin haftalik / aylik / 3aylik / 6aylik duygu trendi.

    Parametreler:
      ?periyot=haftalik | aylik | 3aylik | 6aylik   (varsayilan: aylik)

    Doner:
      [
        { "donem": "2026-W14", "ort_skor": 0.42, "kayit_sayisi": 8,
          "degisim": +0.07 },   ← bir onceki doneme gore fark
        ...
      ]
    """
    from flask import request
    hisse_kodu = hisse_kodu.upper()
    periyot    = request.args.get("periyot", "aylik").lower()

    # SQL GROUP BY ifadesi ve donem uzunlugu (gun)
    periyot_ayar = {
        "haftalik": ("strftime('%Y-W%W', tarih)", 7),
        "aylik":    ("strftime('%Y-%m',    tarih)", 30),
        "3aylik":   ("strftime('%Y', tarih) || '-Q' || CAST((CAST(strftime('%m',tarih) AS INT) + 2) / 3 AS TEXT)", 91),
        "6aylik":   ("strftime('%Y', tarih) || '-H' || "
                     "CASE WHEN CAST(strftime('%m',tarih) AS INT) <= 6 "
                     "THEN '1' ELSE '2' END", 182),
    }
    if periyot not in periyot_ayar:
        return jsonify({"hata": f"Gecersiz periyot: {periyot}. "
                                "haftalik/aylik/3aylik/6aylik olabilir."}), 400

    grup_ifade, _ = periyot_ayar[periyot]

    # Haftalık: son 52 hafta, Aylık: son 24 ay, diğerleri: son 12 dönem
    limit_gun = {"haftalik": 365, "aylik": 730, "3aylik": 1095, "6aylik": 1460}
    gun = limit_gun.get(periyot, 730)

    rows = db_sorgu(f"""
        SELECT
            {grup_ifade}          AS donem,
            AVG(ortalama_skor)    AS ort_skor,
            SUM(kayit_sayisi)     AS kayit_sayisi,
            MIN(tarih)            AS donem_baslangic,
            MAX(tarih)            AS donem_bitis
        FROM gunluk_duygu
        WHERE hisse_kodu = ?
          AND tarih >= DATE('now', '-{gun} days')
        GROUP BY donem
        ORDER BY donem
    """, (hisse_kodu,))

    if not rows:
        return jsonify({"hata": f"[{hisse_kodu}] icin duygu verisi bulunamadi."}), 404

    # Donemler arasi degisim hesapla
    sonuc = []
    for i, r in enumerate(rows):
        onceki_skor = rows[i - 1]["ort_skor"] if i > 0 else None
        degisim = (round(r["ort_skor"] - onceki_skor, 4)
                   if onceki_skor is not None else None)
        sonuc.append({
            "donem":          r["donem"],
            "donem_baslangic": r["donem_baslangic"],
            "donem_bitis":    r["donem_bitis"],
            "ort_skor":       round(r["ort_skor"], 4),
            "kayit_sayisi":   r["kayit_sayisi"],
            "degisim":        degisim,
        })

    return jsonify({
        "hisse_kodu": hisse_kodu,
        "periyot":    periyot,
        "veriler":    sonuc,
    })


@app.route("/api/onem/<hisse_kodu>")
def ozellik_onem(hisse_kodu: str):
    """
    En iyi modelin feature importance listesini döndürür (ilk 20 özellik).
    """
    hisse_kodu = hisse_kodu.upper()
    model, meta = model_yukle(hisse_kodu, tip="best")
    if model is None:
        return jsonify({"hata": f"[{hisse_kodu}] model bulunamadi."}), 404

    if not hasattr(model, "feature_importances_"):
        return jsonify({"hata": "Bu model feature importance desteklemiyor."}), 400

    ozellikler = meta.get("ozellikler", [])
    # LGBM: varsayılan split sayısı yerine gain değeri kullan (float, XGBoost ile karşılaştırılabilir)
    if hasattr(model, "booster_"):
        importances = model.booster_.feature_importance(importance_type="gain").tolist()
    else:
        importances = model.feature_importances_.tolist()
    pairs = sorted(zip(ozellikler, importances), key=lambda x: -x[1])[:20]
    return jsonify([{"ozellik": n, "onem": round(v, 6)} for n, v in pairs])


@app.route("/api/karsilastirma/<hisse_kodu>")
def karsilastirma(hisse_kodu: str):
    """
    models/<HISSE>_metriks.json dosyasından finansal vs hibrit model
    accuracy ve F1 skorlarını döndürür.
    """
    hisse_kodu  = hisse_kodu.upper()
    metriks_yolu = os.path.join(MODELLER_KLASOR, f"{hisse_kodu}_metriks.json")

    if not os.path.exists(metriks_yolu):
        return jsonify({"hata": f"[{hisse_kodu}] metriks dosyasi bulunamadi. Once model_egitimi.py calistirin."}), 404

    with open(metriks_yolu, "r", encoding="utf-8") as f:
        metriks = json.load(f)

    return jsonify(metriks)


# ─── Backtest ────────────────────────────────────────────────────────────────

@app.route("/api/backtest/<hisse_kodu>")
def backtest_hisse(hisse_kodu: str):
    from ml.backtest import backtest_hesapla
    sonuc = backtest_hesapla(hisse_kodu.upper())
    if "hata" in sonuc:
        return jsonify(sonuc), 404
    return jsonify(sonuc)


@app.route("/api/backtest/ozet")
def backtest_ozet():
    from ml.backtest import tum_hisseler_backtest
    return jsonify(tum_hisseler_backtest(list(HISSELER.keys())))


# ─── Pipeline ────────────────────────────────────────────────────────────────

def _pipeline_calistir(mod="tam"):
    with _pipeline_kilit:
        if _pipeline_durum["calisiyor"]:
            return
        _pipeline_durum["calisiyor"] = True
        _pipeline_durum["mod"] = mod

    try:
        sonuc = subprocess.run(
            [sys.executable, os.path.join(KLASOR, "pipeline.py"), "--mod", mod],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=KLASOR, timeout=7200,
        )
        basarili = sonuc.returncode == 0
    except Exception:
        basarili = False
    finally:
        _model_cache.clear()
        _meta_cache.clear()
        with _pipeline_kilit:
            _pipeline_durum["calisiyor"]  = False
            _pipeline_durum["mod"]        = None
            _pipeline_durum["son_calisma"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            _pipeline_durum["son_sonuc"]  = "basarili" if basarili else "hata"


@app.route("/api/pipeline/durum")
def pipeline_durum():
    son_log = []
    if os.path.exists(PIPELINE_LOG):
        with open(PIPELINE_LOG, encoding="utf-8", errors="replace") as f:
            satırlar = f.readlines()
        son_log = [s.rstrip() for s in satırlar[-15:]]
    return jsonify({
        "calisiyor":   _pipeline_durum["calisiyor"],
        "mod":         _pipeline_durum["mod"],
        "son_calisma": _pipeline_durum["son_calisma"],
        "son_sonuc":   _pipeline_durum["son_sonuc"],
        "log":         son_log,
    })


@app.route("/api/login", methods=["POST"])
def login():
    data  = request.get_json(silent=True) or {}
    sifre = data.get("sifre", "")
    if hashlib.sha256(sifre.encode()).hexdigest() == ADMIN_HASH:
        session["admin"] = True
        return jsonify({"mesaj": "Giriş başarılı."})
    time.sleep(1)  # brute-force yavaşlatma
    return jsonify({"hata": "Hatalı şifre."}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("admin", None)
    return jsonify({"mesaj": "Çıkış yapıldı."})


@app.route("/api/pipeline/baslat", methods=["POST"])
@login_gerekli
def pipeline_baslat():
    with _pipeline_kilit:
        if _pipeline_durum["calisiyor"]:
            return jsonify({"hata": "Pipeline zaten çalışıyor."}), 409
    threading.Thread(target=_pipeline_calistir, args=("tam",), daemon=True).start()
    return jsonify({"mesaj": "Pipeline başlatıldı."})


@app.route("/api/pipeline/veri_guncelle", methods=["POST"])
@login_gerekli
def veri_guncelle():
    with _pipeline_kilit:
        if _pipeline_durum["calisiyor"]:
            return jsonify({"hata": "Pipeline zaten çalışıyor."}), 409
    threading.Thread(target=_pipeline_calistir, args=("veri",), daemon=True).start()
    return jsonify({"mesaj": "Veri güncelleme başlatıldı."})


@app.route("/api/pipeline/model_egit", methods=["POST"])
@login_gerekli
def model_egit():
    with _pipeline_kilit:
        if _pipeline_durum["calisiyor"]:
            return jsonify({"hata": "Pipeline zaten çalışıyor."}), 409
    threading.Thread(target=_pipeline_calistir, args=("model",), daemon=True).start()
    return jsonify({"mesaj": "Model eğitimi başlatıldı."})


# ─── Başlat ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Hafta içi her gün 07:00'de otomatik güncelleme (BIST Pzt-Cum çalışır)
    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(_pipeline_calistir, "cron", day_of_week="mon-fri", hour=7, minute=0)
    scheduler.start()

    app.run(debug=False, port=5000, use_reloader=False)
