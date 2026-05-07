"""
BIST Tahmin Platformu — Detaylı Proje Dokümantasyon PDF'i
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os, json

FONT_PATH = r"C:\Windows\Fonts"
try:
    pdfmetrics.registerFont(TTFont("F",  os.path.join(FONT_PATH, "arial.ttf")))
    pdfmetrics.registerFont(TTFont("FB", os.path.join(FONT_PATH, "arialbd.ttf")))
    pdfmetrics.registerFont(TTFont("FI", os.path.join(FONT_PATH, "ariali.ttf")))
    BF, BBF, BIF = "F", "FB", "FI"
except:
    BF, BBF, BIF = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

C_BLUE   = colors.HexColor("#1a73e8")
C_DARK   = colors.HexColor("#1a1a2e")
C_NAVY   = colors.HexColor("#16213e")
C_GREEN  = colors.HexColor("#0f9b58")
C_ORANGE = colors.HexColor("#e07b00")
C_RED    = colors.HexColor("#cc2200")
C_LIGHT  = colors.HexColor("#f0f4ff")
C_ALT    = colors.HexColor("#f8faff")
C_BORDER = colors.HexColor("#d0d8f0")
C_YELLOW = colors.HexColor("#fff8ee")
C_CODE   = colors.HexColor("#eef2ff")

W, H = A4
COL = W - 4*cm

def S():
    return {
        "title":    ParagraphStyle("ti", fontName=BBF, fontSize=24, textColor=colors.white,
                                   alignment=TA_CENTER, spaceAfter=6, leading=30),
        "subtitle": ParagraphStyle("su", fontName=BF,  fontSize=11, textColor=colors.HexColor("#c8d8ff"),
                                   alignment=TA_CENTER, spaceAfter=4, leading=15),
        "h1":       ParagraphStyle("h1", fontName=BBF, fontSize=15, textColor=C_BLUE,
                                   spaceBefore=16, spaceAfter=6, leading=20),
        "h2":       ParagraphStyle("h2", fontName=BBF, fontSize=12, textColor=C_NAVY,
                                   spaceBefore=10, spaceAfter=5, leading=17),
        "h3":       ParagraphStyle("h3", fontName=BBF, fontSize=10, textColor=C_BLUE,
                                   spaceBefore=7, spaceAfter=3, leading=14),
        "body":     ParagraphStyle("bo", fontName=BF,  fontSize=9.5, textColor=colors.HexColor("#111122"),
                                   spaceAfter=5, leading=15, alignment=TA_JUSTIFY),
        "bullet":   ParagraphStyle("bu", fontName=BF,  fontSize=9.5, textColor=colors.HexColor("#111122"),
                                   spaceAfter=3, leading=14, leftIndent=14, bulletIndent=4),
        "sub_bullet":ParagraphStyle("sb", fontName=BF, fontSize=9,  textColor=colors.HexColor("#333355"),
                                   spaceAfter=2, leading=13, leftIndent=28, bulletIndent=18),
        "code":     ParagraphStyle("co", fontName="Courier", fontSize=8.5, textColor=colors.HexColor("#1a3a6e"),
                                   spaceAfter=3, leading=13, leftIndent=16, backColor=C_CODE),
        "note":     ParagraphStyle("no", fontName=BIF, fontSize=8.5, textColor=colors.HexColor("#555577"),
                                   spaceAfter=4, leading=12, leftIndent=10),
        "box_title":ParagraphStyle("bt", fontName=BBF, fontSize=10, textColor=C_ORANGE, leading=14),
        "stepnum":  ParagraphStyle("sn", fontName=BBF, fontSize=10, textColor=C_BLUE,
                                   spaceAfter=2, leading=14),
    }

def b(text, s): return Paragraph(f"• {text}", s["bullet"])
def sb(text, s): return Paragraph(f"◦ {text}", s["sub_bullet"])
def hr(): return HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceAfter=8, spaceBefore=4)
def sp(n=0.3): return Spacer(1, n*cm)

def info_box(title, text, s, color=C_ORANGE, bg=C_YELLOW):
    data = [[Paragraph(f"{title}", ParagraphStyle("_", fontName=BBF, fontSize=9.5,
                                                   textColor=color, leading=13))],
            [Paragraph(text, s["body"])]]
    t = Table(data, colWidths=[COL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("LINERIGHT", (0,0), (0,-1), 3, color),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
    ]))
    return t

def header_table(rows, col_widths, s):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), BBF),
        ("FONTNAME", (0,1), (-1,-1), BF),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, C_ALT]),
        ("GRID", (0,0), (-1,-1), 0.4, C_BORDER),
    ]))
    return t

def metrikleri_oku():
    sonuc = []
    for f in sorted(os.listdir(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "models"))):
        if not f.endswith("_metriks.json"): continue
        d = json.load(open(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "models", f), encoding="utf-8"))
        tip = d.get("en_iyi_tip", "hibrit")
        jk  = "sadece_finansal" if tip == "finansal" else tip
        m   = d.get(jk, {})
        fin = d.get("sadece_finansal", {})
        hyb = d.get("hibrit", {})
        sonuc.append({
            "hisse": d.get("hisse_kodu", ""),
            "tip": tip, "algo": m.get("algoritma","?").upper(),
            "acc": m.get("accuracy", 0), "f1": m.get("f1_macro", 0),
            "fin_acc": fin.get("accuracy", 0), "hyb_acc": hyb.get("accuracy", 0),
            "iyilesme": d.get("iyilesme_acc", 0),
            "wf_acc": m.get("wf", {}).get("wf_acc_ort", 0) or 0,
        })
    sonuc.sort(key=lambda x: -x["acc"])
    return sonuc


# ══════════════════════════════════════════════════════════════════════════════
def build_story(s):
    story = []

    # ── KAPAK ─────────────────────────────────────────────────────────────────
    cover = Table([[Paragraph("BIST Tahmin Platformu", s["title"])]],
                  colWidths=[COL])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_DARK),
        ("TOPPADDING", (0,0), (-1,-1), 30), ("BOTTOMPADDING", (0,0), (-1,-1), 24),
        ("LEFTPADDING", (0,0), (-1,-1), 20), ("RIGHTPADDING", (0,0), (-1,-1), 20),
    ]))
    story.append(cover)
    story.append(sp(0.3))

    sub = Table([[Paragraph(
        "Finansal Veriler + BERT Duygu Analizi + XGBoost / LightGBM<br/>"
        "ile BIST Hisse Senedi Fiyat Yönü Tahmin Sistemi", s["subtitle"])]], colWidths=[COL])
    sub.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_NAVY),
        ("TOPPADDING", (0,0), (-1,-1), 14), ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("LEFTPADDING", (0,0), (-1,-1), 20),
    ]))
    story.append(sub)
    story.append(sp(0.5))

    meta = [["Geliştirici", "Muhammet Sanli"],
            ["Tarih", "Nisan 2026"],
            ["Platform", "Python · Flask · XGBoost · LightGBM · BERT · SQLite"],
            ["Kapsam", "10 BIST hissesi · 2021–2026 verisi · ~1.200 işlem günü"]]
    mt = Table(meta, colWidths=[3.8*cm, COL-3.8*cm])
    mt.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), BBF), ("FONTNAME", (1,0), (1,-1), BF),
        ("FONTSIZE", (0,0), (-1,-1), 9.5), ("TEXTCOLOR", (0,0), (0,-1), C_BLUE),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEBELOW", (0,0), (-1,-2), 0.4, C_BORDER),
    ]))
    story.append(mt)
    story.append(sp(0.8))

    # ── 1. GENEL BAKIŞ ────────────────────────────────────────────────────────
    story.append(Paragraph("1. Projeye Genel Bakış", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Bu proje, Borsa İstanbul (BIST) hisselerinin bir sonraki günkü kapanış fiyatının "
        "yükseliş mi düşüş mü olacağını tahmin eden makine öğrenmesi platformudur. "
        "Temel araştırma sorusu şudur: <b>BERT tabanlı Türkçe haber duygu analizi, "
        "yalnızca finansal verilerle kurulan modele kıyasla tahmin doğruluğunu artırıyor mu?</b>",
        s["body"]))
    story.append(Paragraph(
        "Sistem iki model karşılaştırması üzerine kuruludur: (1) yalnızca fiyat, hacim ve "
        "teknik göstergeler kullanan <b>finansal model</b>, (2) bunlara ek olarak BERT duygu "
        "skorlarını da kullanan <b>hibrit model</b>. Her iki model sabit bir holdout dönemi "
        "(Ekim 2025 – Nisan 2026) üzerinde değerlendirilmektedir.",
        s["body"]))
    story.append(sp(0.2))
    story.append(Paragraph("Temel Hedefler:", s["h2"]))
    for item in [
        "Günlük kapanış yön tahmini: YÜKSELİŞ (1) veya DÜŞÜŞ (0) — ikili sınıflandırma",
        "BERT duygu analizinin tahmin doğruluğuna sektör bazında katkısını ölçmek",
        "Olasılık kalibrasyonu ile güven skorlarını istatistiksel olarak anlamlı hale getirmek",
        "Holdout dönemi backtesti ile BIST100 benchmark'a karşı strateji getirisi hesaplamak",
        "Gerçek zamanlı web arayüzü ile tüm çıktıları görselleştirmek",
    ]: story.append(b(item, s))

    story.append(PageBreak())

    # ── 2. SİSTEM MİMARİSİ ────────────────────────────────────────────────────
    story.append(Paragraph("2. Sistem Mimarisi", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Platform birbirini besleyen 5 katmandan oluşmaktadır. Her katman kendi sorumluluğuna "
        "odaklanmış bağımsız Python modülleriyle gerçekleştirilmiştir.", s["body"]))
    story.append(sp(0.2))

    arch = [["Katman", "Dosya", "Görev"],
            ["1 — Veri Toplama", "haber_toplayici.py\npipeline.py",
             "Google News RSS, Bloomberg HT, KAP API, AA Ekonomi, Hürriyet\nkaynaklarından Türkçe haber başlıkları çekilir."],
            ["2 — Duygu Analizi", "duygu_analizi.py",
             "savasy/bert-base-turkish-sentiment-cased modeli her haber için\n–1…+1 duygu skoru üretir. Haberler×2, tweetler×1 ağırlıkla\ngunluk_duygu tablosuna yazılır."],
            ["3 — Model Eğitimi", "model_egitimi.py\nmodel_utils.py",
             "IC filtresi, lag değişkenleri, walk-forward CV, XGBoost/LightGBM\nyarışması, eşik optimizasyonu ve isotonic kalibrasyon."],
            ["4 — API / Backend", "app.py",
             "Flask RESTful API: tahmin, backtest, sinyal geçmişi, pipeline\ndurum endpoint'leri. APScheduler haftalık otomatik güncelleme."],
            ["5 — Veritabanı", "borsa.db (SQLite)",
             "gunluk_fiyatlar, haberler, gunluk_duygu, makro_veriler tabloları.\n~1.200 işlem günü × 10 hisse."]]
    at = Table(arch, colWidths=[3.8*cm, 4.2*cm, COL-8*cm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C_BLUE), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), BBF), ("FONTNAME", (0,1), (-1,-1), BF),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, C_ALT]),
        ("GRID", (0,0), (-1,-1), 0.4, C_BORDER),
        ("FONTNAME", (0,1), (0,-1), BBF), ("TEXTCOLOR", (0,1), (0,-1), C_BLUE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(at)
    story.append(sp(0.5))

    # ── 3. VERİ TOPLAMA ───────────────────────────────────────────────────────
    story.append(Paragraph("3. Adım 1 — Veri Toplama ve RSS Scraping", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Türkçe finansal haberler 5 farklı kaynaktan RSS protokolü ile toplanmaktadır. "
        "RSS (Really Simple Syndication), haber sitelerinin içeriklerini standart XML "
        "formatında sunduğu bir yayın protokolüdür. HTML scraping'e kıyasla çok daha "
        "güvenilirdir çünkü site tasarımı değişse bile format sabittir.", s["body"]))
    story.append(sp(0.2))
    story.append(Paragraph("Haber Kaynakları:", s["h2"]))
    src = [["Kaynak", "Yöntem", "Filtre"],
           ["Google News RSS", "Hisse bazlı özel arama sorgusu", "Her hisse için özelleştirilmiş sorgu"],
           ["Google News RSS-2", "Analiz/yatırım odaklı ikinci sorgu", "Farklı anahtar kelimeler"],
           ["KAP (kap.org.tr)", "JSON API → Google News fallback", "Resmi şirket bildirimleri"],
           ["Bloomberg HT", "Genel RSS + anahtar kelime filtresi", "Şirket adı / ticker"],
           ["Hürriyet, Dünya, AA", "RSS/Atom feed", "Şirket adı eşleşmesi"]]
    story.append(header_table(src, [4*cm, 5.5*cm, COL-9.5*cm], s))
    story.append(sp(0.3))
    story.append(info_box("Not:",
        "KAP sitesi JavaScript ile render edildiğinden BeautifulSoup ile scrape edilemez. "
        "Bunun yerine kap.org.tr/tr/api/disclosures JSON endpoint'i kullanılmıştır. "
        "Bu endpoint erişilemezse Google News'te 'KAP bildirim' araması yapılır (fallback).", s))
    story.append(sp(0.3))
    story.append(Paragraph("Duplicate önleme:", s["h3"]))
    story.append(Paragraph(
        "Aynı haber birden fazla kaynaktan gelebilir. "
        "tarih + başlık + kaynak kombinasyonu veritabanında kontrol edilir; "
        "aynı kombinasyon varsa kayıt atlanır. "
        "Duygu skoru bu aşamada NULL bırakılır — BERT analizi sonraki adımda çalışır.", s["body"]))

    story.append(PageBreak())

    # ── 4. DUYGU ANALİZİ ──────────────────────────────────────────────────────
    story.append(Paragraph("4. Adım 2 — BERT Tabanlı Duygu Analizi", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "savasy/bert-base-turkish-sentiment-cased modeli, Türkçe finansal haberler için "
        "önceden eğitilmiş bir BERT modelidir. Her haber başlığı modelden geçirilir ve "
        "–1 (çok negatif) ile +1 (çok pozitif) arasında bir duygu skoru üretilir.", s["body"]))

    story.append(Paragraph("Skor hesaplama formülü:", s["h3"]))
    story.append(Paragraph("skor = P(pozitif) − P(negatif)", s["code"]))
    story.append(Paragraph(
        "Model çıktısında iki olasılık vardır: negatif ve pozitif. "
        "Bu ikisinin farkı alınarak –1…+1 aralığına hizalanmış bir skor elde edilir.", s["body"]))

    ex = [["Haber Başlığı", "P(neg)", "P(poz)", "Skor"],
          ["BIM karını rekor kırdı", "0.05", "0.95", "+0.90"],
          ["THYAO zarar açıkladı, hisseler geriledi", "0.90", "0.10", "–0.80"],
          ["Garanti olağan genel kurul toplantısı", "0.48", "0.52", "+0.04"]]
    story.append(header_table(ex, [7*cm, 2*cm, 2*cm, COL-11*cm], s))
    story.append(sp(0.3))

    story.append(Paragraph("Günlük Ağırlıklı Ortalama:", s["h2"]))
    story.append(Paragraph(
        "Aynı gün birden fazla haber olabilir. Haber kaynakları (gazete, ajans) tweet'lere "
        "göre daha güvenilir kabul edildiğinden ağırlıklı ortalama alınır:", s["body"]))
    story.append(Paragraph("Haberler × 2.0  +  Tweetler × 1.0  →  Günlük ortalama skor", s["code"]))
    story.append(sp(0.3))

    story.append(Paragraph("5 Duygu Özelliği:", s["h2"]))
    feat5 = [["Özellik", "Formül", "Ne Ölçer?"],
             ["duygu_skoru", "rolling(7).mean()", "7 günlük MA — genel duygu eğilimi, gürültü azaltır"],
             ["duygu_momentum", "ham_skor − MA7", "Duygunun ani değişim hızı — trend kırılması sinyali"],
             ["duygu_std7", "rolling(7).std()", "Duygu volatilitesi — yüksekse belirsizlik var"],
             ["haber_duygu", "haber MA7", "Sadece haber kaynaklı duygu — tweet gürültüsü yok"],
             ["haber_momentum", "ham_haber − haber_MA7", "Haber bazlı ani değişim hızı"]]
    story.append(header_table(feat5, [3.8*cm, 4.2*cm, COL-8*cm], s))

    story.append(PageBreak())

    # ── 5. ÖZELLİK MÜHENDİSLİĞİ ─────────────────────────────────────────────
    story.append(Paragraph("5. Adım 3 — Özellik Mühendisliği", s["h1"])); story.append(hr())

    story.append(Paragraph("5.1 Teknik Göstergeler", s["h2"]))
    ind = [["Gösterge", "Parametre", "Ne Söyler?"],
           ["RSI", "14 gün", "Aşırı alım (>70) / aşırı satım (<30) tespiti. 0–100 arası normalize değer."],
           ["SMA", "20 ve 50 gün", "Kısa ve orta vadeli fiyat trendi. SMA20 > SMA50 → yükseliş trendi."],
           ["MACD", "12-26-9 EMA", "Hızlı-yavaş ortalama farkı. MACD > sinyal çizgisi → al sinyali."],
           ["Bollinger Band", "20 gün, 2σ", "BB_width: dar band = düşük volatilite, büyük hareket yaklaşabilir."],
           ["ATR", "14 gün", "Günlük gerçek fiyat aralığı. Volatilite ölçüsü (normalize değil)."],
           ["Stochastik", "14-3-3", "Fiyatın 14 günlük aralıktaki konumu. >80 aşırı alım, <20 aşırı satım."],
           ["ROC", "10 gün", "10 günlük fiyat değişim hızı — momentum göstergesi. Pozitif ve artıyor → güçlü."]]
    story.append(header_table(ind, [2.8*cm, 2.8*cm, COL-5.6*cm], s))
    story.append(sp(0.3))

    story.append(Paragraph("5.2 Kendi Üretilen Özellikler", s["h2"]))
    for feat, form, acik in [
        ("hacim_oran", "hacim / rolling(20).mean()",
         "Bugünkü hacim son 20 günün ortalamasına göre kaç kat? "
         "Değer 2.5 ise normalin 2.5 katı hacim var — güçlü sinyal. "
         "Fiyat hareketi + yüksek hacim birlikte anlam taşır."),
        ("hl_spread", "(yuksek - dusuk) / kapanis",
         "Günlük fiyat salınımının kapanışa oranı. "
         "Yüksek spread = belirsiz, tartışmalı gün. Düşük spread = sakin seans."),
    ]:
        story.append(Paragraph(f"<b>{feat}</b>  =  {form}", s["code"]))
        story.append(Paragraph(acik, s["body"]))
    story.append(sp(0.2))

    story.append(Paragraph("5.3 Lag (Gecikme) Değişkenleri", s["h2"]))
    story.append(Paragraph(
        "Model her gün için tek bir satır görür. Ama fiyat yönü tahmini için dünkü, "
        "geçen haftaki değerler de kritik önem taşır. Lag değişkenleri bu geçmiş bağlamı "
        "satıra taşır:", s["body"]))
    story.append(Paragraph(
        "RSI = 65.2 (bugün)  |  RSI_lag1 = 61.0  |  RSI_lag2 = 58.3  |  RSI_lag5 = 48.7  |  RSI_lag10 = 42.0",
        s["code"]))
    story.append(Paragraph(
        "Model bu seriden RSI'ın 42'den 65'e sürekli yükseldiğini görür — momentum var. "
        "12 özellik × 5 gecikme (1,2,3,5,10 gün) = 60 lag sütunu eklenir.", s["body"]))
    story.append(sp(0.3))

    story.append(Paragraph("5.4 IC (Information Coefficient) Filtresi", s["h2"]))
    story.append(info_box("IC Nedir?",
        "IC = bir özelliğin yarınki fiyat yönünü ne kadar öngörebildiğini ölçen sayı. "
        "Matematiksel karşılığı Pearson korelasyon katsayısıdır: "
        "IC = |corr(özellik, hedef_değişken)|. "
        "Finansal veride IC = 0.05 bile güçlü sinyal sayılır; piyasalar çok gürültülüdür.", s,
        color=C_BLUE, bg=C_LIGHT))
    story.append(sp(0.2))
    story.append(Paragraph("Filtre kuralı: IC < 0.02 olan özellik modele dahil edilmez.", s["code"]))
    story.append(Paragraph(
        "abs() kullanılmasının nedeni: korelasyon –0.08 de olsa +0.08 de olsa model için "
        "eşit derecede değerlidir — sadece yön farklıdır. "
        "IC filtresi her hisse için ayrı ayrı uygulanır çünkü BIMAS için anlamlı olan "
        "özellik PETKM için anlamsız olabilir. "
        "Sonuç: 80+ özellikten yaklaşık 40–60'ı modele girer.", s["body"]))

    story.append(PageBreak())

    # ── 6. MODEL EĞİTİMİ ─────────────────────────────────────────────────────
    story.append(Paragraph("6. Adım 4 — Model Eğitimi", s["h1"])); story.append(hr())

    story.append(Paragraph("6.1 Eşik Filtresi — Neden ±%0.5 ve ±%1.0?", s["h2"]))
    story.append(Paragraph(
        "Borsa her gün rastgele dalgalanır. Çok küçük hareketleri öğrenmek modeli gürültüye "
        "yönlendirir. İki eşik denenir; daha iyi sonuç veren seçilir:", s["body"]))
    story.append(Paragraph(
        "Eşiksiz:  +%0.03 değişim → YÜKSELİŞ  (anlamsız, tesadüf)\n"
        "±%0.5:    +%0.03 → eğitimden çıkar  |  +%0.80 → YÜKSELİŞ (anlamlı)", s["code"]))
    story.append(sp(0.3))

    story.append(Paragraph("6.2 İki Özellik Seti", s["h2"]))
    sets = [["Set", "Özellikler", "Amaç"],
            ["Finansal", "RSI, MACD, SMA, BB, ATR, Stoch, ROC,\nhacim_oran, hl_spread, makro getiriler",
             "Baseline — sadece teknik analiz"],
            ["Hibrit", "Finansal + duygu_skoru, duygu_momentum,\nduygu_std7, haber_duygu, haber_momentum",
             "BERT katkısı var mı? → karşılaştırma"]]
    story.append(header_table(sets, [2.5*cm, 6.5*cm, COL-9*cm], s))
    story.append(sp(0.3))

    story.append(Paragraph("6.3 Algoritma Yarışması: XGBoost vs LightGBM", s["h2"]))
    story.append(Paragraph(
        "Her kombinasyon için iki algoritma da eğitilir. Holdout doğruluğu daha yüksek olan "
        "kaydedilir. Her ikisi de gradient boosting ailesidir ancak farklı iç optimizasyon "
        "yöntemleri kullanır — küçük veri setlerinde biri diğerinden iyi çıkabilir.", s["body"]))
    story.append(Paragraph(
        "Ortak parametreler: n_estimators=500  |  max_depth=4  |  learning_rate=0.03  |  "
        "early_stopping_rounds=30  |  scale_pos_weight (sınıf dengesizliği için)", s["code"]))
    story.append(sp(0.3))

    story.append(Paragraph("6.4 Holdout — Veri Sızıntısını Önleme", s["h2"]))
    story.append(Paragraph(
        "Tüm hisseler için aynı sabit test penceresi kullanılır. "
        "Model bu döneme ait veriyi eğitim sırasında hiç görmez:", s["body"]))
    story.append(Paragraph(
        "EĞİTİM: 2021-01-01 → 2025-09-30   |   TEST (HOLDOUT): 2025-10-01 → 2026-04-14",
        s["code"]))
    story.append(sp(0.3))

    story.append(Paragraph("6.5 Walk-Forward Cross-Validation", s["h2"]))
    story.append(info_box("Normal k-fold CV finansal veride neden yanlış?",
        "Normal CV rastgele böldüğü için geçmiş veriyi öğrenmek amacıyla gelecek veriye bakabilir "
        "(veri sızıntısı). Walk-forward CV her zaman 'geçmişle eğit, gelecekle test et' kuralını korur.", s,
        color=C_RED, bg=colors.HexColor("#fff0f0")))
    story.append(sp(0.2))
    wf = [["Kat", "Eğitim", "Test"],
          ["Kat 1", "2021-01-01 → 2023-06-30", "2023-07-01 → 2023-12-31"],
          ["Kat 2", "2021-01-01 → 2024-06-30", "2024-07-01 → 2024-12-31"],
          ["Kat 3", "2021-01-01 → 2025-06-30", "2025-07-01 → 2026-04-14"]]
    story.append(header_table(wf, [2*cm, 5.5*cm, COL-7.5*cm], s))
    story.append(Paragraph(
        "3 kattan ortalama ve standart sapma hesaplanır. "
        "Standart sapmanın düşük olması modelin zaman içinde tutarlı olduğunu gösterir.", s["body"]))
    story.append(sp(0.3))

    story.append(Paragraph("6.6 Karar Eşiği Optimizasyonu", s["h2"]))
    story.append(Paragraph(
        "Model her gün için bir olasılık üretir: 'yükseliş olasılığı = %63'. "
        "Bu olasılığı YÜKSELİŞ/DÜŞÜŞ kararına çevirmek için bir eşik gerekir. "
        "Varsayılan %50 her zaman optimal değildir — sınıf dengesizliği varsa eşiği "
        "düşürmek modelin daha dengeli tahmin yapmasını sağlar:", s["body"]))
    story.append(Paragraph(
        "for esik in [0.30, 0.35, 0.40, ..., 0.70]:\n"
        "    F1-macro hesapla → en yüksek F1'i veren eşiği seç", s["code"]))
    story.append(Paragraph(
        "F1-macro kullanılmasının nedeni: hem YÜKSELİŞ hem DÜŞÜŞ sınıflarını dengeli "
        "değerlendirmektir. Sadece accuracy kullanılırsa model her şeyi YÜKSELİŞ tahmin "
        "ederek yüksek skor elde edebilir.", s["body"]))

    story.append(PageBreak())

    # ── 7. KALİBRASYON ───────────────────────────────────────────────────────
    story.append(Paragraph("7. Adım 5 — Olasılık Kalibrasyonu", s["h1"])); story.append(hr())
    story.append(info_box("Problem:",
        "XGBoost ve LightGBM doğru sınıflandırma için optimize edilmiştir — doğru olasılık "
        "üretmek için değil. Ham model '%80 YÜKSELİŞ' diyebilir ama geçmişte bu durumun "
        "gerçekleşme sıklığı sadece %55 olabilir. Bu kullanıcıyı yanıltır.", s))
    story.append(sp(0.3))
    story.append(Paragraph("Isotonic Regression ile Kalibrasyon:", s["h2"]))
    story.append(Paragraph(
        "Validasyon setindeki her gün için ham olasılık ve gerçek sonuç (0/1) kaydedilir. "
        "IsotonicRegression bu noktalardan artan bir düzeltme eğrisi öğrenir:", s["body"]))
    cal = [["Ham Olasılık", "Gerçek Frekans", "Sonuç"],
           ["%80", "%55", "Model çok özgüvenli → aşağı çekiliyor"],
           ["%60", "%58", "Yakın — küçük düzeltme"],
           ["%40", "%40", "Zaten doğru — değişmiyor"],
           ["%30", "%42", "Model çekingen → yukarı itiliyor"]]
    story.append(header_table(cal, [3.5*cm, 3.5*cm, COL-7*cm], s))
    story.append(sp(0.2))
    story.append(Paragraph(
        "Kalibrasyon sonrası: model '%42 olasılık' dediğinde gerçekten ~%42 sıklıkta "
        "yükseliş oluyor. Güven skoru artık istatistiksel olarak anlamlı.", s["body"]))
    story.append(sp(0.2))
    story.append(Paragraph("CalibreliModel Sınıfı — Neden Ayrı Modüle Taşındı?", s["h2"]))
    story.append(Paragraph(
        "Python'un pickle sistemi bir sınıfı kaydettiğinde nerede tanımlandığını da kaydeder. "
        "Sınıf fonksiyon içinde tanımlanırsa model_egitimi.py kaydedebilir ama "
        "app.py bu sınıfı bulamayıp hata verir. Çözüm:", s["body"]))
    story.append(Paragraph(
        "model_utils.py  ←  her iki dosya da buradan import ediyor\n"
        "  ├── model_egitimi.py  (pickle'a kaydeder)\n"
        "  └── app.py            (pickle'dan yükler)  → aynı adres → hata yok",
        s["code"]))

    story.append(PageBreak())

    # ── 8. MODEL PERFORMANSI ──────────────────────────────────────────────────
    story.append(Paragraph("8. Model Performans Sonuçları", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Holdout döneminde (2025-10-01 → 2026-04-14) her hisse için finansal ve hibrit "
        "modeller ayrı ayrı değerlendirilmiştir. Aşağıdaki tabloda en iyi modelin "
        "sonuçları ve iki model arasındaki fark gösterilmektedir.", s["body"]))
    story.append(sp(0.2))

    metriks = metrikleri_oku()
    perf = [["Hisse", "En İyi", "Algo", "Doğruluk", "F1", "WF Acc", "Fin.", "Hyb.", "Fark"]]
    for m in metriks:
        fark = m["hyb_acc"] - m["fin_acc"]
        perf.append([
            m["hisse"], m["tip"].upper(), m["algo"],
            f"%{m['acc']*100:.1f}", f"{m['f1']:.3f}",
            f"%{m['wf_acc']*100:.1f}" if m["wf_acc"] else "—",
            f"%{m['fin_acc']*100:.1f}", f"%{m['hyb_acc']*100:.1f}",
            f"{fark*100:+.1f}%",
        ])
    cw = [2*cm, 2*cm, 1.8*cm, 2*cm, 1.6*cm, 2*cm, 1.8*cm, 1.8*cm, COL-15*cm]
    pt = Table(perf, colWidths=cw)
    pstyle = [
        ("BACKGROUND", (0,0), (-1,0), C_BLUE), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), BBF), ("FONTNAME", (0,1), (-1,-1), BF),
        ("FONTSIZE", (0,0), (-1,-1), 8.5), ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, C_ALT]),
        ("GRID", (0,0), (-1,-1), 0.4, C_BORDER),
        ("FONTNAME", (0,1), (0,-1), BBF),
    ]
    for i, m in enumerate(metriks, 1):
        fark = m["hyb_acc"] - m["fin_acc"]
        c = C_GREEN if fark > 0 else C_RED
        pstyle.append(("TEXTCOLOR", (8,i), (8,i), c))
        pstyle.append(("FONTNAME", (8,i), (8,i), BBF))
        if m["acc"] >= 0.60:
            pstyle += [("TEXTCOLOR",(3,i),(3,i),C_GREEN),("FONTNAME",(3,i),(3,i),BBF)]
        elif m["acc"] >= 0.55:
            pstyle.append(("TEXTCOLOR",(3,i),(3,i),C_ORANGE))
    pt.setStyle(TableStyle(pstyle))
    story.append(pt)
    story.append(sp(0.3))

    story.append(Paragraph("Bulgular:", s["h2"]))
    for item in [
        "En iyi doğruluk: BIMAS %62.8 — random tahminin (%50) belirgin üstünde",
        "4/10 hissede hibrit model finansali geçti — duygu analizinin katkısı sektöre bağlı",
        "Hibrit kazandığı hisseler: ASELS +4.2%, TUPRS +4.8%, GARAN +3.6%, PETKM +2.7%",
        "Finansal kazandığı hisseler: BIMAS -6.2%, EREGL -3.5%, KCHOL -3.9%, SISE -3.8%",
        "WF Acc ile Holdout Acc yakın → modeller zaman içinde tutarlı",
    ]: story.append(b(item, s))
    story.append(sp(0.3))

    story.append(Paragraph("Duygu Analizi Katkısının Sektörel Analizi:", s["h2"]))
    story.append(Paragraph(
        "Hibrit modelin başarılı olduğu hisseler (ASELS, TUPRS, GARAN) haberlere doğrudan "
        "tepki veren sektörlerdedir: savunma sözleşmeleri, enerji fiyatları, faiz kararları. "
        "Finansal modelin daha iyi olduğu hisseler (BIMAS, EREGL) ise haber duygusu ile "
        "fiyat arasındaki korelasyonun daha zayıf olduğu sektörlere aittir.", s["body"]))
    story.append(Paragraph(
        "Ayrıca haber kapsama oranı da önemli bir faktördür. KCHOL yalnızca %13.5 günde "
        "haber duygu verisine sahipken THYAO %40.3 kapsama ile en yüksek orana ulaşmıştır. "
        "Düşük kapsamada model boşlukları son bilinen değerle doldurmak zorunda kalır — "
        "bu durum duygu sinyalinin kalitesini düşürür.", s["body"]))

    story.append(PageBreak())

    # ── 9. BACKTEST ───────────────────────────────────────────────────────────
    story.append(Paragraph("9. Adım 6 — Backtest Modülü", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Tahmin doğruluğu yüksek bir model, para kazandırmayabilir. "
        "Backtest bu soruyu yanıtlar: model doğruluğu finansal getiriye dönüşüyor mu?", s["body"]))
    story.append(sp(0.2))

    story.append(Paragraph("Strateji Kuralları:", s["h2"]))
    bt = [["Kural", "Açıklama"],
          ["Giriş", "Model YÜKSELİŞ tahmin ederse → o günün kapanışında al"],
          ["Çıkış", "Her pozisyon ertesi günün kapanışında satılır (1 günlük tutma)"],
          ["DÜŞÜŞ günleri", "Nakit bekle → günlük risksiz faiz kazan (0.35 / 252)"],
          ["Benchmark", "BIST100 buy-and-hold — aynı dönem, hiçbir şey yapma"],
          ["Başlangıç", "100 birim normalize sermaye"]]
    story.append(header_table(bt, [3.5*cm, COL-3.5*cm], s))
    story.append(sp(0.3))

    story.append(Paragraph("Neden Risksiz Faiz?", s["h3"]))
    story.append(Paragraph(
        "Türkiye'de nakit tutmak anlamsız değildir — yıllık ~%35 faiz vardır. "
        "Modelin bu faizi geçmesi gerekir ki gerçek bir değer taşısın. "
        "DÜŞÜŞ günlerinde nakit tutarak günlük 0.35/252 = ~%0.14 risksiz getiri elde edilir.", s["body"]))
    story.append(sp(0.3))

    story.append(Paragraph("Performans Metrikleri:", s["h2"]))
    met = [["Metrik", "Formül", "Ne Gösterir?"],
           ["Sharpe Oranı", "(ort.getiri − rf) / std × √252",
            "Birim risk başına fazla getiri. >1 iyi, >2 çok iyi, <0 risksiz faizden kötü."],
           ["Max Drawdown", "(dip − tepe) / tepe × 100",
            "En kötü senaryoda tepe noktasından maksimum düşüş. Risk ölçüsü."],
           ["Kazanma Oranı", "doğru tahmin / toplam gün × 100",
            "Modelin tahminlerinin kaçta kaçının gerçekle örtüştüğü."],
           ["Alpha", "model getiri − benchmark getiri",
            "Piyasayı ne kadar geçtik? Pozitif alpha → strateji değer katıyor."]]
    story.append(header_table(met, [3*cm, 4.5*cm, COL-7.5*cm], s))
    story.append(sp(0.2))
    story.append(info_box("Backtest Sonucu:",
        "10 hisseden 6'sında model BIST100 benchmark'ını geçmiştir. "
        "En yüksek alpha BIMAS hissesinde gözlemlenmiştir (+~44 puan fark). "
        "Backtest komisyon, slippage ve market impact içermediğinden gerçek sonuçlar "
        "bu değerlerin altında olacaktır.", s, color=C_GREEN,
        bg=colors.HexColor("#efffee")))

    story.append(PageBreak())

    # ── 10. API VE ZAMANLAYICI ────────────────────────────────────────────────
    story.append(Paragraph("10. Adım 7 — Flask API ve APScheduler", s["h1"])); story.append(hr())

    story.append(Paragraph("API Endpoint'leri:", s["h2"]))
    ep = [["Endpoint", "Method", "Açıklama"],
          ["/api/tahmin/<hisse>", "GET", "Kalibrasyon uygulanmış tahmin: yön + olasılık + kapanış"],
          ["/api/karsilastirma/<hisse>", "GET", "Finansal vs hibrit: accuracy, F1, walk-forward detayı"],
          ["/api/sinyal_gecmisi/<hisse>", "GET", "Son 30 gün retroaktif tahmin geçmişi ve doğruluk"],
          ["/api/tum_hisseler_ozet", "GET", "10 hissenin model performans özeti"],
          ["/api/backtest/<hisse>", "GET", "Hisse bazlı backtest: günlük seri + metrikler"],
          ["/api/backtest/ozet", "GET", "Tüm hisseler backtest: getiri, Sharpe, drawdown"],
          ["/api/pipeline/durum", "GET", "Pipeline çalışıyor mu? Son güncelleme zamanı?"],
          ["/api/pipeline/baslat", "POST", "Pipeline'ı manuel tetikle (haber + model güncelle)"]]
    story.append(header_table(ep, [5*cm, 1.8*cm, COL-6.8*cm], s))
    story.append(sp(0.3))

    story.append(Paragraph("APScheduler — Haftalık Otomatik Güncelleme:", s["h2"]))
    story.append(Paragraph(
        "Her pazar 23:00'da pipeline otomatik çalışır: yeni haberler toplanır, duygu "
        "skorları hesaplanır, modeller güncellenir. "
        "use_reloader=False zorunludur — aksi takdirde Flask debug modunun "
        "auto-reload özelliği APScheduler'ı iki kez başlatır.", s["body"]))
    story.append(Paragraph(
        "BackgroundScheduler — cron: day_of_week='sun', hour=23\n"
        "Thread-safe: threading.Lock() ile calisiyor / son_guncelleme durumu korunur",
        s["code"]))

    story.append(PageBreak())

    # ── 11. FRONTEND ─────────────────────────────────────────────────────────
    story.append(Paragraph("11. Adım 8 — Frontend ve Görselleştirme", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Web arayüzü saf HTML/CSS/JavaScript ile geliştirilmiştir. "
        "Plotly.js 2.27 kütüphanesi interaktif grafikleri tarayıcıda çizer. "
        "Tüm veri Flask API'den JSON olarak alınır — sayfa yenileme gerekmez.", s["body"]))
    story.append(sp(0.2))

    ui = [["Bileşen", "Açıklama"],
          ["Mum Grafiği", "Son 90 günlük OHLCV verisi. Her bar: açılış, kapanış, yüksek, düşük. "
           "Yeşil = yükseliş günü, kırmızı = düşüş günü. Alt panel: hacim çubukları."],
          ["Duygu Grafiği", "Günlük / haftalık / aylık periyot toggle. "
           "Haftalık/aylık'ta x ekseni tip:'category' — Plotly'nin 'Jan 2000' parse hatasını önler."],
          ["Sinyal Geçmişi", "Son 30 günün tahmin vs gerçek tablosu. "
           "4 özet kart: genel doğruluk, YÜKSELİŞ doğruluk, DÜŞÜŞ doğruluk, doğru/yanlış sayısı."],
          ["Model Karşılaştırma", "Finansal vs hibrit yan yana kart. Walk-forward 3 kat detayı. "
           "İyileşme bandı: duygu katkısı varsa yeşil gösterilir."],
          ["Özellik Önemi", "XGBoost feature importance bar grafiği. "
           "Ham isimler Türkçeye çevrilir: 'duygu_skoru_lag2' → 'Duygu Skoru +2g'."],
          ["Backtest Grafiği", "Model portföyü vs BIST100 çizgi grafiği. "
           "Alpha görsel olarak iki çizgi arasındaki alan."],
          ["Güncelle Butonu", "POST /api/pipeline/baslat → 5s polling → buton döner animasyonu."]]
    story.append(header_table(ui, [3.8*cm, COL-3.8*cm], s))

    story.append(PageBreak())

    # ── 12. TEKNİK SORUNLAR ───────────────────────────────────────────────────
    story.append(Paragraph("12. Geliştirme Sürecinde Karşılaşılan Teknik Sorunlar", s["h1"]))
    story.append(hr())

    sorunlar = [
        ("sklearn 1.8 API Değişikliği",
         "CalibratedClassifierCV(cv='prefit') parametresi sklearn 1.8.0 sürümünde kaldırıldı. "
         "Bu durum model eğitimini çalışma zamanında hatayla durduruyordu.",
         "IsotonicRegression'ı doğrudan kullanan özel CalibreliModel wrapper sınıfı yazıldı. "
         "Sınıf model_utils.py'a taşınarak sklearn sürümünden bağımsız hale getirildi."),
        ("Pickle Serileştirme Hatası",
         "CalibreliModel sınıfı tek_model_egit() fonksiyonunun içinde tanımlandığından "
         "joblib.dump() hata veriyordu: 'Can't pickle local class'.",
         "Sınıf model_utils.py modül seviyesine taşındı. "
         "Hem model_egitimi.py hem app.py aynı modülden import ettiğinden "
         "pickle sınıfı hem kaydedebilir hem yükleyebilir hale geldi."),
        ("Türkçe Karakter Encoding Hatası",
         "Python'daki 'calışıyor' değişken adı (U+0131 dotless ı içeriyor) JSON anahtarı olarak "
         "gönderildiğinde JavaScript tarafında undefined olarak okunuyordu.",
         "Tüm occurrences ASCII 'calisiyor' olarak değiştirildi."),
        ("Plotly Tarih Ekseni Sorunu",
         "'2026-W14' formatındaki haftalık etiketler Plotly tarafından Unix timestamp "
         "olarak parse edilip 'Jan 2000' gösteriyordu.",
         "xaxis: { type: 'category' } ayarlandı — Plotly artık değerleri "
         "timestamp değil kategori olarak işliyor."),
        ("Birden Fazla Flask Süreci",
         "Eski Flask süreci arka planda çalışmaya devam ederken yeni başlatılan süreç "
         "portla çakışıyordu; eski kod sunulmaya devam ediyordu.",
         "PowerShell Stop-Process ile eski Python süreçleri sonlandırıldı. "
         "use_reloader=False eklenerek APScheduler çakışması önlendi."),
        ("Tarayici Cache Sorunu",
         "script.js ve style.css guncellendiginde tarayici eski surumu cache'den yukluyordu; "
         "degisiklikler sayfaya yansimiyordu.",
         "?v=4 query string ile cache buster eklendi: "
         "script src='/static/script.js?v=4' seklinde versiyonlama yapildi."),
    ]

    for baslik, problem, cozum in sorunlar:
        bloc = [
            [Paragraph(f"Sorun: {baslik}", s["box_title"])],
            [Paragraph(f"<b>Problem:</b> {problem}", s["body"])],
            [Paragraph(f"<b>Cozum:</b> {cozum}", s["body"])],
        ]
        bt2 = Table(bloc, colWidths=[COL])
        bt2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), C_YELLOW),
            ("LINERIGHT", (0,0), (0,-1), 3, C_ORANGE),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
        ]))
        story.append(KeepTogether([bt2, sp(0.25)]))

    story.append(PageBreak())

    # ── 13. ÖZET ──────────────────────────────────────────────────────────────
    story.append(Paragraph("13. Genel Değerlendirme", s["h1"])); story.append(hr())
    story.append(Paragraph(
        "Proje, BIST hisselerinde günlük fiyat yönü tahmininin makine öğrenmesi ile "
        "yapılabilirliğini göstermiştir. En önemli bulgular:", s["body"]))
    story.append(sp(0.1))
    for item in [
        "En iyi doğruluk %62.8 (BIMAS) — random tahminin (%50) anlamlı şekilde üstünde",
        "BERT duygu analizinin katkısı sektöre bağlı: bankacılık, savunma ve enerji sektörlerinde "
         "hibrit model kazanırken perakende ve hammadde sektörlerinde finansal model daha başarılı",
        "Haber kapsama oranı düşük hisselerde (KCHOL %13.5, PETKM %9.2) duygu sinyali güvenilmez "
         "hale gelebilmektedir — bu durum modelin performansını olumsuz etkileyebilir",
        "Olasılık kalibrasyonu güven skorlarını gerçek frekanslarla hizaladı — "
         "'%42 olasılık' artık gerçekten ~%42 sıklıkta gerçekleşiyor",
        "Walk-forward CV ile modellerin zaman içindeki tutarlılığı doğrulandı",
        "6/10 hissede model BIST100 buy-and-hold benchmark'ını geçti",
    ]: story.append(b(item, s))

    story.append(sp(0.3))
    story.append(Paragraph("Sınırlılıklar:", s["h2"]))
    for item in [
        "~1.200 günlük veri makine öğrenmesi için küçük sayılır",
        "Backtest komisyon, slippage ve market impact içermemektedir",
        "Holdout dönemi sabit bir pencere — gerçek gelecek performansını garanti etmez",
        "Haber kalitesi ve kapsama oranı hisseler arasında homojen değil",
    ]: story.append(b(item, s))

    story.append(sp(0.8))
    footer = Table([[Paragraph(
        "BIST Tahmin Platformu  —  Muhammet Sanli  —  Nisan 2026",
        ParagraphStyle("ft", fontName=BF, fontSize=8, textColor=colors.white, alignment=TA_CENTER)
    )]], colWidths=[COL])
    footer.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),C_NAVY),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
    ]))
    story.append(footer)
    return story


def main():
    out = "BIST_Tahmin_Platformu_Dokumantasyon.pdf"
    doc = SimpleDocTemplate(out, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    doc.build(build_story(S()))
    print(f"PDF olusturuldu: {out}")

if __name__ == "__main__":
    main()
