"""Sadece 6 problemli hisseyi yeniden eğitir — Change 1 (INVESTING_FORUM + EKSISOZLUK filtresi) testi."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml.model_egitimi import hisse_egit

HEDEF_HISSELER = ["EREGL", "THYAO", "KCHOL", "SAHOL", "ASELS", "GARAN"]

print("Change 1 testi: INVESTING_FORUM + EKSISOZLUK filtrelenmiş features.py ile yeniden eğitim")
print("="*70)
for hisse in HEDEF_HISSELER:
    hisse_egit(hisse)

print("\n=== ÖZET ===")
import json
BASELINE = {
    # Change 1 sonrası değerler (Change 2 baseline'ı)
    "EREGL": {"fin": 0.545, "hib": 0.509},
    "THYAO": {"fin": 0.533, "hib": 0.498},
    "KCHOL": {"fin": 0.510, "hib": 0.514},
    "SAHOL": {"fin": 0.507, "hib": 0.486},
    "ASELS": {"fin": 0.505, "hib": 0.494},
    "GARAN": {"fin": 0.514, "hib": 0.520},
}
modeller_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
for hisse in HEDEF_HISSELER:
    yol = os.path.join(modeller_dir, f"{hisse}_metriks.json")
    try:
        with open(yol) as f:
            m = json.load(f)
        yeni_fin = m["sadece_finansal"]["wf_acc"]
        yeni_hib = m["hibrit"]["wf_acc"]
        b = BASELINE[hisse]
        fin_degisim = (yeni_fin - b["fin"]) * 100
        hib_degisim = (yeni_hib - b["hib"]) * 100
        fark_degisim = (yeni_hib - yeni_fin) - (b["hib"] - b["fin"])
        print(f"{hisse}: Fin {b['fin']*100:.1f}%→{yeni_fin*100:.1f}% ({fin_degisim:+.1f}pp) | "
              f"Hib {b['hib']*100:.1f}%→{yeni_hib*100:.1f}% ({hib_degisim:+.1f}pp) | "
              f"Hib-Fin fark: {(b['hib']-b['fin'])*100:.1f}pp→{(yeni_hib-yeni_fin)*100:.1f}pp ({fark_degisim*100:+.1f}pp)")
    except Exception as e:
        print(f"{hisse}: Metriks okunamadı — {e}")
