"""
pipeline.py — Gunluk veri guncelleme ve model yenileme zinciri
Calistir: python pipeline.py

Adimlar (sirayla):
  1. veri_cekici.py       → yeni fiyat + makro veri indir
  2. haber_toplayici.py   → Google News / BigPara / KAP haberleri
  3. eksisozluk_toplayici.py → Eksi Sozluk yorumlari (yeni entry'ler)
  4. investing_toplayici.py  → Investing.com forum yorumlari
  5. duygu_analizi.py     → BERT ile yeni kayitlari skorla
  6. model_egitimi.py     → Modelleri yeniden egit (yeni veriyle)

Zamanlanmis calistirma icin:
  Windows Gorev Zamanlayicisi:
    Eylem: python C:\path\pipeline.py
    Tetikleyici: Her gun 07:00
"""

import subprocess
import sys
import os
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PYTHON      = sys.executable
KLASOR      = os.path.dirname(os.path.abspath(__file__))
LOG_DOSYASI = os.path.join(KLASOR, "logs", "pipeline_log.txt")

ADIMLAR = [
    ("Fiyat & Makro Veri",    "collectors/veri_cekici.py"),
    ("Haber Toplama",         "collectors/haber_toplayici.py"),
    ("Eksi Sozluk",           "collectors/eksisozluk_toplayici.py"),
    ("Investing.com",         "collectors/investing_toplayici.py"),
    ("Telegram",              "collectors/telegram_toplayici.py"),
    ("Mynet Finans",          "collectors/mynet_toplayici.py"),
    ("Hisse.net",             "collectors/hissenet_toplayici.py"),
    ("BigPara",               "collectors/bigpara_toplayici.py"),
    ("KAP Bildirimleri",      "collectors/kap_toplayici.py"),
    ("Is Yatirim Arastirma",  "collectors/isyatirim_toplayici.py"),
    ("Duygu Analizi (BERT)",  "ml/duygu_analizi.py"),
    ("Model Egitimi",         "ml/model_egitimi.py"),
]

# Gunluk hizli pipeline: borsa kapanisi sonrasi ~15 dk
# Finansal veri + BERT skorlama + model yenileme
GUNLUK_ADIMLAR = [
    ("Fiyat & Makro Veri",    "collectors/veri_cekici.py"),
    ("Duygu Analizi (BERT)",  "ml/duygu_analizi.py"),
    ("Model Egitimi",         "ml/model_egitimi.py"),
]

# Haftalik tam pipeline: Telegram dahil ~3-4 saat
HAFTALIK_ADIMLAR = ADIMLAR


def log(mesaj: str):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    os.makedirs(os.path.dirname(LOG_DOSYASI), exist_ok=True)
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        f.write(satir + "\n")


def adim_calistir(isim: str, script: str) -> bool:
    yol = os.path.join(KLASOR, script)
    log(f"--- {isim} basliyor ({script}) ---")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        sonuc = subprocess.run(
            [PYTHON, "-u", yol],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=KLASOR,
            timeout=1800,   # 30 dakika zaman asimi
            env=env,
        )
        if sonuc.stdout:
            for satir in sonuc.stdout.strip().splitlines()[-10:]:  # Son 10 satir
                log(f"  > {satir}")
        if sonuc.returncode != 0:
            log(f"  [HATA] {isim} cikis kodu: {sonuc.returncode}")
            if sonuc.stderr:
                for satir in sonuc.stderr.strip().splitlines()[-5:]:
                    log(f"  ! {satir}")
            return False
        log(f"  [OK] {isim} tamamlandi.")
        return True
    except subprocess.TimeoutExpired:
        log(f"  [HATA] {isim} zaman asimi (30 dk).")
        return False
    except Exception as e:
        log(f"  [HATA] {isim}: {e}")
        return False


VERI_ADIMLARI  = [a for a in ADIMLAR if a[1] != "ml/model_egitimi.py"]
MODEL_ADIMLARI = [a for a in ADIMLAR if a[1] == "ml/model_egitimi.py"]


def main(adimlar=None):
    if adimlar is None:
        adimlar = ADIMLAR
    log("=" * 55)
    log("BIST Pipeline Basladi")
    log("=" * 55)

    basarili, basarisiz = 0, 0

    for isim, script in adimlar:
        if adim_calistir(isim, script):
            basarili += 1
        else:
            basarisiz += 1

    log("=" * 55)
    log(f"Pipeline bitti: {basarili} basarili, {basarisiz} basarisiz")
    log("=" * 55)

    return basarisiz == 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mod", choices=["tam", "veri", "model"], default="tam",
                        help="tam=tum adimlar, veri=sadece toplayicilar+BERT, model=sadece egitim")
    args = parser.parse_args()

    if args.mod == "veri":
        secilen = VERI_ADIMLARI
    elif args.mod == "model":
        secilen = MODEL_ADIMLARI
    else:
        secilen = ADIMLAR

    ok = main(secilen)
    sys.exit(0 if ok else 1)
