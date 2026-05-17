/* script.js — BIST Borsa Tahmin Platformu (Plotly.js) */

// ── Sayfa yüklenince ────────────────────────────────────────────────────────
let aktifPeriyot = "gunluk";
let aktifHisse   = null;

document.addEventListener("DOMContentLoaded", async () => {
  await hisseleriYukle();
  await tumHisselerOzetYukle();
  await backtestOzetYukle();
  await pipelineDurumGuncelle();
  document.getElementById("analizBtn").addEventListener("click", analizEt);

  // Periyot toggle
  document.getElementById("periyotToggle").addEventListener("click", async (e) => {
    const btn = e.target.closest(".toggle-btn");
    if (!btn) return;
    document.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("toggle-btn--aktif"));
    btn.classList.add("toggle-btn--aktif");
    aktifPeriyot = btn.dataset.periyot;
    if (aktifHisse) await duyguGuncellePeriyot(aktifHisse, aktifPeriyot);
  });
});

async function hisseleriYukle() {
  const select = document.getElementById("hisseSelect");
  try {
    const res  = await fetch("/api/hisseler");
    const data = await res.json();
    data.forEach(h => {
      const opt = document.createElement("option");
      opt.value       = h.hisse_kodu;
      opt.textContent = `${h.hisse_kodu} — ${h.sirket_adi}`;
      select.appendChild(opt);
    });
  } catch (e) {
    console.error("Hisse listesi yuklenemedi:", e);
  }
}

// ── Analiz Et ───────────────────────────────────────────────────────────────
async function analizEt() {
  const hisse = document.getElementById("hisseSelect").value;
  if (!hisse) return;
  aktifHisse = hisse;

  const btn = document.getElementById("analizBtn");
  btn.textContent = "Yükleniyor...";
  btn.disabled = true;

  try {
    const [fiyatData, duyguData, tahminData, karsilastirmaData, onemData, sinyalData] =
      await Promise.all([
        fetch(`/api/fiyat/${hisse}`).then(r => r.json()),
        fetch(`/api/duygu/${hisse}`).then(r => r.json()),
        fetch(`/api/tahmin/${hisse}`).then(r => r.json()),
        fetch(`/api/karsilastirma/${hisse}`).then(r => r.json()),
        fetch(`/api/onem/${hisse}`).then(r => r.json()),
        fetch(`/api/sinyal_gecmisi/${hisse}`).then(r => r.json()),
      ]);

    candlestickGrafikiCiz(fiyatData);
    await duyguGuncellePeriyot(hisse, aktifPeriyot, duyguData);
    tahminKutusunuGuncelle(tahminData);
    karsilastirmaGuncelle(karsilastirmaData);
    onemGrafikiCiz(onemData);
    sinyalGecmisiGuncelle(sinyalData);

    // Backtest (arka planda yükle — yavaş olabilir)
    fetch(`/api/backtest/${hisse}`).then(r => r.json()).then(backtestGuncelle);

  } catch (e) {
    console.error("Analiz hatasi:", e);
  } finally {
    btn.textContent = "Analiz Et";
    btn.disabled = false;
  }
}

async function duyguGuncellePeriyot(hisse, periyot, gunlukData = null) {
  if (periyot === "gunluk") {
    const data = gunlukData || await fetch(`/api/duygu/${hisse}`).then(r => r.json());
    duyguGrafikiCiz(data);
  } else {
    const data = await fetch(`/api/duygu_trend/${hisse}?periyot=${periyot}`).then(r => r.json());
    duyguTrendGrafikiCiz(data, periyot);
  }
}

// ── Plotly Renk Teması ───────────────────────────────────────────────────────
const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor:  "rgba(0,0,0,0)",
  font:          { color: "#8b949e", family: "Segoe UI, sans-serif" },
  xaxis: { gridcolor: "#21262d", zerolinecolor: "#30363d", color: "#8b949e" },
  yaxis: { gridcolor: "#21262d", zerolinecolor: "#30363d", color: "#8b949e" },
  margin: { t: 20, r: 20, b: 40, l: 60 },
  legend: { font: { color: "#8b949e" } },
};

const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ["lasso2d", "select2d"],
  displaylogo: false,
};

// ── Candlestick Fiyat + Hacim Grafiği ────────────────────────────────────────
function candlestickGrafikiCiz(data) {
  if (!data.length) return;

  const tarihler = data.map(d => d.tarih);

  const mumTrace = {
    type:        "candlestick",
    x:           tarihler,
    open:        data.map(d => d.acilis),
    high:        data.map(d => d.yuksek),
    low:         data.map(d => d.dusuk),
    close:       data.map(d => d.kapanis),
    increasing:  { line: { color: "#3fb950" }, fillcolor: "#1a3a1f" },
    decreasing:  { line: { color: "#f85149" }, fillcolor: "#3a1a1a" },
    name:        "Fiyat",
    xaxis:       "x",
    yaxis:       "y",
  };

  const hacimRenkler = data.map((d, i) =>
    i === 0 ? "#58a6ff" : (d.kapanis >= data[i - 1].kapanis ? "#3fb950" : "#f85149")
  );

  const hacimTrace = {
    type:    "bar",
    x:       tarihler,
    y:       data.map(d => d.hacim),
    marker:  { color: hacimRenkler, opacity: 0.6 },
    name:    "Hacim",
    xaxis:   "x",
    yaxis:   "y2",
  };

  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: {
      ...PLOTLY_LAYOUT_BASE.xaxis,
      rangeslider: { visible: false },
      type: "date",
      domain: [0, 1],
    },
    yaxis: {
      ...PLOTLY_LAYOUT_BASE.yaxis,
      title:  "Fiyat (TL)",
      domain: [0.3, 1],
    },
    yaxis2: {
      ...PLOTLY_LAYOUT_BASE.yaxis,
      title:  "Hacim",
      domain: [0, 0.25],
      showticklabels: true,
    },
    showlegend: false,
    margin: { t: 20, r: 20, b: 40, l: 70 },
  };

  Plotly.newPlot("fiyatGrafik", [mumTrace, hacimTrace], layout, PLOTLY_CONFIG);
}

// ── Duygu Skoru Bar Grafiği ──────────────────────────────────────────────────
function duyguGrafikiCiz(data) {
  if (!data.length) return;

  const tarihler = data.map(d => d.tarih);
  const skorlar  = data.map(d => d.ortalama_skor);

  const trace = {
    type:   "bar",
    x:      tarihler,
    y:      skorlar,
    marker: {
      color:   skorlar.map(s => s >= 0 ? "#3fb950" : "#f85149"),
      opacity: 0.85,
    },
    name: "Duygu Skoru",
  };

  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    yaxis: {
      ...PLOTLY_LAYOUT_BASE.yaxis,
      title:         "Skor [-1, +1]",
      range:         [-1, 1],
      zeroline:      true,
      zerolinecolor: "#58a6ff",
      zerolinewidth: 1,
    },
  };

  Plotly.newPlot("duyguGrafik", [trace], layout, PLOTLY_CONFIG);
}

// ── Tahmin Kutusu ────────────────────────────────────────────────────────────
function tahminKutusunuGuncelle(data) {
  const kutu = document.getElementById("tahminKutu");
  kutu.classList.remove("gizli");

  if (data.hata) {
    const el = document.getElementById("tahminYon");
    el.textContent = "Model Yok";
    el.className   = "tahmin-yon";
    document.getElementById("tahminGuven").innerHTML   = `<strong>${data.hata}</strong>`;
    document.getElementById("tahminKapanis").innerHTML = "";
    document.getElementById("tahminDuygu").innerHTML   = "";
    document.getElementById("tahminTarih").innerHTML   = "";
    return;
  }

  const yon    = data.tahmin_yon;
  const yukOlas = data.yukselis_olasiligi;
  const esik    = (data.optimal_esik || 0.5) * 100;

  // Belirsiz sinyal: yükseliş olasılığı >50 ama eşiğin altında
  const belirsiz = yon === "DÜŞÜŞ" && yukOlas > 50;

  const cls = belirsiz ? "belirsiz" : (yon === "YÜKSELİŞ" ? "yukselis" : "dusus");
  const ok  = yon === "YÜKSELİŞ" ? "▲" : (belirsiz ? "—" : "▼");
  const yonMetin = belirsiz ? "BELİRSİZ" : yon;

  document.getElementById("tahminYon").textContent = `${ok} ${yonMetin}`;
  document.getElementById("tahminYon").className   = `tahmin-yon ${cls}`;

  // Yükseliş olasılığı + eşik bilgisi
  const olasRenk = yukOlas >= 55 ? "#3fb950" : yukOlas <= 45 ? "#f85149" : "#e3b341";
  const esikNot  = belirsiz
    ? ` <span style="color:#484f58;font-size:0.85em">(eşik %${esik.toFixed(0)} — sinyal yok)</span>`
    : "";
  document.getElementById("tahminGuven").innerHTML =
    `Yükseliş Olasılığı: <strong style="color:${olasRenk}">%${yukOlas}</strong>${esikNot}`;

  document.getElementById("tahminKapanis").innerHTML =
    `Son Kapanış: <strong>${data.son_kapanis.toFixed(2)} TL</strong>`;

  if (data.duygu_skoru != null) {
    const dSign = data.duygu_skoru >= 0 ? "+" : "";
    document.getElementById("tahminDuygu").innerHTML =
      `Duygu Skoru: <strong>${dSign}${data.duygu_skoru.toFixed(4)}</strong>`;
  } else {
    document.getElementById("tahminDuygu").innerHTML =
      `Duygu Skoru: <strong style="color:#484f58">— veri yok</strong>`;
  }

  document.getElementById("tahminTarih").innerHTML =
    `Tahmin Tarihi: <strong>${data.son_tarih}</strong>`;

  // Model bilgisi badge'leri
  const badgeEl = document.getElementById("tahminBadges");
  if (data.model_tipi && data.algoritma) {
    const modelEtiket = data.model_tipi === "hibrit" ? "🧠 Hibrit" : "📊 Finansal";
    const algoRenk    = data.algoritma === "LGBM" ? "badge--lgbm" : "badge--xgb";
    const modelRenk   = data.model_tipi === "hibrit" ? "badge--hibrit" : "badge--finansal";
    badgeEl.innerHTML = `
      <span class="badge ${modelRenk}">${modelEtiket}</span>
      <span class="badge ${algoRenk}">${data.algoritma}</span>
      <span class="badge badge--esik">${data.esik_filtre}</span>
    `;
  } else {
    badgeEl.innerHTML = "";
  }
}

// ── Model Karşılaştırma Paneli ───────────────────────────────────────────────
function karsilastirmaGuncelle(data) {
  const panel = document.getElementById("karsilastirmaPanel");

  if (data.hata) {
    panel.classList.add("gizli");
    return;
  }

  panel.classList.remove("gizli");

  const fin = data.sadece_finansal;
  const hib = data.hibrit;
  const secilenTip = data.en_iyi_tip || "finansal";

  document.getElementById("finAcc").textContent = `%${(fin.accuracy * 100).toFixed(1)}`;
  document.getElementById("finF1").textContent  = (fin.f1_macro ?? fin.f1 ?? 0).toFixed(3);
  document.getElementById("hibAcc").textContent = `%${(hib.accuracy * 100).toFixed(1)}`;
  document.getElementById("hibF1").textContent  = (hib.f1_macro ?? hib.f1 ?? 0).toFixed(3);

  // Seçilen modeli vurgula
  const finKart = document.querySelector(".model-kart--finansal");
  const hibKart = document.querySelector(".model-kart--hibrit");
  finKart.classList.toggle("model-kart--secilen", secilenTip === "finansal");
  hibKart.classList.toggle("model-kart--secilen", secilenTip === "hibrit");

  // Walk-forward doğruluk
  const finWf = fin.wf || {};
  const hibWf = hib.wf || {};
  document.getElementById("finWfAcc").textContent =
    finWf.wf_acc_ort != null
      ? `%${(finWf.wf_acc_ort * 100).toFixed(1)} ±${(finWf.wf_acc_std * 100).toFixed(1)}`
      : "—";
  document.getElementById("hibWfAcc").textContent =
    hibWf.wf_acc_ort != null
      ? `%${(hibWf.wf_acc_ort * 100).toFixed(1)} ±${(hibWf.wf_acc_std * 100).toFixed(1)}`
      : "—";

  // İyileşme bandı — model seçimi WF'ye göre yapıldığı için karşılaştırma da WF kullanır
  const band = document.getElementById("iyilesmeBand");
  const secilenAd = secilenTip === "hibrit" ? "Hibrit" : "Finansal";

  if (finWf.wf_acc_ort != null && hibWf.wf_acc_ort != null) {
    const wfIyilesme = ((hibWf.wf_acc_ort - finWf.wf_acc_ort) * 100).toFixed(1);
    if (hibWf.wf_acc_ort > finWf.wf_acc_ort) {
      band.innerHTML = `Duygu analizi WF doğruluğunu <strong>+%${wfIyilesme}</strong> artırdı — ${secilenAd} model seçildi`;
      band.style.background  = "#1a3a1f";
      band.style.borderColor = "#3fb950";
      band.style.color       = "#3fb950";
      band.classList.remove("gizli");
    } else if (finWf.wf_acc_ort > hibWf.wf_acc_ort) {
      band.innerHTML = `Duygu analizi WF doğruluğunu <strong>${wfIyilesme}%</strong> düşürdü — ${secilenAd} model seçildi`;
      band.style.background  = "#2d1a1a";
      band.style.borderColor = "#f85149";
      band.style.color       = "#f85149";
      band.classList.remove("gizli");
    } else {
      band.classList.add("gizli");
    }
  } else {
    band.classList.add("gizli");
  }

  // Walk-forward kat detayları (seçilen modelden al)
  const wfPanel  = document.getElementById("wfDetayPanel");
  const wfKatlar = document.getElementById("wfKatlar");
  const katDetay = ((secilenTip === "hibrit" ? hibWf : finWf).wf_detay || []);

  if (katDetay.length > 0) {
    wfPanel.classList.remove("gizli");
    const katLabels = [
      "Kat 1: 2021-2023 → 2023H2",
      "Kat 2: 2021-2024 → 2024H2",
      "Kat 3: 2021-2025 → 2025H2+",
    ];
    wfKatlar.innerHTML = katDetay.map((k, i) => `
      <div class="wf-kat">
        <span class="wf-kat__etiket">${katLabels[i] || `Kat ${i + 1}`}</span>
        <span class="wf-kat__deger">Acc <strong>%${(k.acc * 100).toFixed(1)}</strong></span>
        <span class="wf-kat__deger">F1 <strong>${k.f1.toFixed(3)}</strong></span>
      </div>
    `).join("");
  } else {
    wfPanel.classList.add("gizli");
  }
}

// ── Duygu Trend (Haftalık/Aylık) Grafiği ─────────────────────────────────────
function duyguTrendGrafikiCiz(data, periyot) {
  if (data.hata || !data.veriler || !data.veriler.length) return;

  const veriler  = data.veriler;
  const etiketler = veriler.map(d => d.donem);
  const skorlar   = veriler.map(d => d.ort_skor);
  const kayitlar  = veriler.map(d => d.kayit_sayisi);

  const barTrace = {
    type:   "bar",
    x:      etiketler,
    y:      skorlar,
    marker: {
      color:   skorlar.map(s => s >= 0 ? "#3fb950" : "#f85149"),
      opacity: 0.85,
    },
    name: "Ortalama Skor",
    hovertemplate: "%{x}<br>Skor: %{y:.4f}<br>Kayıt: %{customdata}<extra></extra>",
    customdata: kayitlar,
  };

  // Değişim çizgisi
  const degisimler = veriler.map(d => d.degisim);
  const cizgiTrace = {
    type: "scatter",
    mode: "lines+markers",
    x:    etiketler,
    y:    skorlar,
    line: { color: "#58a6ff", width: 2 },
    marker: { size: 5, color: "#58a6ff" },
    name: "Trend",
    yaxis: "y",
  };

  const periyotEtiket = periyot === "haftalik" ? "Haftalık" : "Aylık";
  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: {
      ...PLOTLY_LAYOUT_BASE.xaxis,
      type: "category",
      tickangle: -40,
      nticks: periyot === "haftalik" ? 16 : 12,  // label yoğunluğunu azalt
    },
    yaxis: {
      ...PLOTLY_LAYOUT_BASE.yaxis,
      title:         "Ort. Skor [-1, +1]",
      range:         [-1, 1],
      zeroline:      true,
      zerolinecolor: "#58a6ff",
      zerolinewidth: 1,
    },
    barmode: "overlay",
  };

  Plotly.newPlot("duyguGrafik", [barTrace, cizgiTrace], layout, PLOTLY_CONFIG);
}

// ── Sinyal Geçmişi Tablosu ───────────────────────────────────────────────────
function sinyalGecmisiGuncelle(data) {
  const panel = document.getElementById("sinyalPanel");
  if (data.hata || !data.gecmis || !data.gecmis.length) {
    panel.classList.add("gizli");
    return;
  }
  panel.classList.remove("gizli");

  const acc  = data.dogruluk;
  const renk = acc >= 55 ? "sinyal-ozet__deger--yesil" : acc >= 50 ? "" : "sinyal-ozet__deger--kirmizi";

  const yukAcc = data.yukselis_acc != null
    ? `<span class="sinyal-ozet__deger sinyal-ozet__deger--yesil">%${data.yukselis_acc}</span>`
    : `<span class="sinyal-ozet__deger" style="color:#484f58">—</span>`;
  const dusAcc = data.dusus_acc != null
    ? `<span class="sinyal-ozet__deger sinyal-ozet__deger--kirmizi">%${data.dusus_acc}</span>`
    : `<span class="sinyal-ozet__deger" style="color:#484f58">—</span>`;

  document.getElementById("sinyalOzet").innerHTML = `
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Genel Doğruluk</span>
      <span class="sinyal-ozet__deger ${renk}">%${acc}</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">▲ Yükseliş Acc</span>
      ${yukAcc}
      <span class="sinyal-ozet__etiket">${data.yukselis_dogru}/${data.yukselis_toplam} tahmin</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">▼ Düşüş Acc</span>
      ${dusAcc}
      <span class="sinyal-ozet__etiket">${data.dusus_dogru}/${data.dusus_toplam} tahmin</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Doğru / Yanlış</span>
      <span class="sinyal-ozet__deger" style="font-size:1rem">
        <span style="color:#3fb950">${data.dogru_sayisi}</span>
        <span style="color:#484f58"> / </span>
        <span style="color:#f85149">${data.toplam - data.dogru_sayisi}</span>
      </span>
    </div>
  `;

  const satirlar = data.gecmis.map(g => {
    const tChip = g.tahmin_yon === "YÜKSELİŞ"
      ? `<span class="yon-chip yon-chip--yukselis">▲ YÜKSELİŞ</span>`
      : `<span class="yon-chip yon-chip--dusus">▼ DÜŞÜŞ</span>`;
    const gChip = g.gercek_yon === "YÜKSELİŞ"
      ? `<span class="yon-chip yon-chip--yukselis">▲ YÜKSELİŞ</span>`
      : `<span class="yon-chip yon-chip--dusus">▼ DÜŞÜŞ</span>`;
    const dogruChip = g.dogru_mu
      ? `<span class="dogru-chip dogru-chip--evet">✓ Doğru</span>`
      : `<span class="dogru-chip dogru-chip--hayir">✗ Yanlış</span>`;
    return `
      <tr>
        <td>${g.tarih}</td>
        <td>${g.kapanis.toFixed(2)} TL</td>
        <td>${tChip}</td>
        <td>%${g.guven}</td>
        <td>${gChip}</td>
        <td>${dogruChip}</td>
      </tr>`;
  }).join("");

  document.getElementById("sinyalTablo").innerHTML = `
    <table class="veri-tablo">
      <thead>
        <tr>
          <th>Tarih</th>
          <th>Kapanış</th>
          <th>Tahmin</th>
          <th>Güven</th>
          <th>Gerçek</th>
          <th>Sonuç</th>
        </tr>
      </thead>
      <tbody>${satirlar}</tbody>
    </table>`;
}

// ── Pipeline / Güncelleme ─────────────────────────────────────────────────────
let _pipelineInterval = null;

function _tumButonlarDevre(durum) {
  ["veriGuncelleBtn", "modelEgitBtn"].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.disabled = durum;
  });
}

// ── Login Modal ───────────────────────────────────────────────────────────────
let _loginSonraAction = null;

function loginGoster(aciklama, action) {
  _loginSonraAction = action;
  const modal = document.getElementById("loginModal");
  const input = document.getElementById("loginSifre");
  const hata  = document.getElementById("loginHata");
  const acik  = document.getElementById("loginAciklama");
  if (acik)   acik.textContent  = aciklama || "Bu işlem için şifre gerekli.";
  if (hata)   { hata.textContent = ""; hata.classList.add("gizli"); }
  if (input)  input.value = "";
  modal.classList.remove("gizli");
  setTimeout(() => input && input.focus(), 100);
}

function loginIptal() {
  document.getElementById("loginModal").classList.add("gizli");
  _loginSonraAction = null;
  _tumButonlarDevre(false);
}

async function loginGonder() {
  const sifre = document.getElementById("loginSifre").value;
  const hata  = document.getElementById("loginHata");
  try {
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sifre })
    });
    if (r.ok) {
      document.getElementById("loginModal").classList.add("gizli");
      if (_loginSonraAction) { const fn = _loginSonraAction; _loginSonraAction = null; fn(); }
    } else {
      const d = await r.json();
      hata.textContent = d.hata || "Hatalı şifre.";
      hata.classList.remove("gizli");
      document.getElementById("loginSifre").value = "";
      document.getElementById("loginSifre").focus();
    }
  } catch (e) {
    hata.textContent = "Bağlantı hatası.";
    hata.classList.remove("gizli");
  }
}

document.addEventListener("keydown", e => {
  const modal = document.getElementById("loginModal");
  if (!modal || modal.classList.contains("gizli")) return;
  if (e.key === "Enter")  loginGonder();
  if (e.key === "Escape") loginIptal();
});

async function pipelineDurumGuncelle() {
  try {
    const data = await fetch("/api/pipeline/durum").then(r => r.json());
    const vBtn = document.getElementById("veriGuncelleBtn");
    const mBtn = document.getElementById("modelEgitBtn");
    const lbl  = document.getElementById("sonGuncellemeLabel");

    if (data["calisiyor"]) {
      const mod = data.mod || "tam";
      if (vBtn) { vBtn.textContent = mod === "model" ? "↓ Veri Güncelle" : "↓ Çalışıyor..."; vBtn.disabled = true; vBtn.classList.toggle("guncelle-btn--calisiyor", mod !== "model"); }
      if (mBtn) { mBtn.textContent = mod === "veri"  ? "⚙ Modeli Eğit"   : "⚙ Çalışıyor..."; mBtn.disabled = true; mBtn.classList.toggle("guncelle-btn--calisiyor", mod !== "veri"); }
      if (!_pipelineInterval)
        _pipelineInterval = setInterval(pipelineDurumGuncelle, 5000);
    } else {
      if (vBtn) { vBtn.textContent = "↓ Veri Güncelle"; vBtn.disabled = false; vBtn.classList.remove("guncelle-btn--calisiyor"); }
      if (mBtn) { mBtn.textContent = "⚙ Modeli Eğit";   mBtn.disabled = false; mBtn.classList.remove("guncelle-btn--calisiyor"); }
      if (_pipelineInterval) { clearInterval(_pipelineInterval); _pipelineInterval = null; }

      if (data.son_calisma) {
        const sonucRenk = data.son_sonuc === "basarili" ? "#3fb950" : "#f85149";
        lbl.innerHTML = `Son güncelleme: <span style="color:${sonucRenk}">${data.son_calisma}</span>`;
        if (data.son_sonuc === "basarili") {
          await tumHisselerOzetYukle();
        }
      }
    }
  } catch (e) { console.error("Pipeline durum hatasi:", e); }
}

async function veriGuncelle() {
  _tumButonlarDevre(true);
  try {
    const r = await fetch("/api/pipeline/veri_guncelle", { method: "POST" });
    if (r.ok) {
      const vBtn = document.getElementById("veriGuncelleBtn");
      if (vBtn) { vBtn.textContent = "↓ Çalışıyor..."; vBtn.classList.add("guncelle-btn--calisiyor"); }
      _pipelineInterval = setInterval(pipelineDurumGuncelle, 5000);
    } else if (r.status === 401) {
      _tumButonlarDevre(false);
      loginGoster("Veri güncelleme için şifre gerekli.", veriGuncelle);
    } else {
      const d = await r.json();
      alert(d.hata || "Veri güncelleme başlatılamadı.");
      _tumButonlarDevre(false);
    }
  } catch (e) { console.error("Veri guncelle hatasi:", e); _tumButonlarDevre(false); }
}

async function modelEgit() {
  _tumButonlarDevre(true);
  try {
    const r = await fetch("/api/pipeline/model_egit", { method: "POST" });
    if (r.ok) {
      const mBtn = document.getElementById("modelEgitBtn");
      if (mBtn) { mBtn.textContent = "⚙ Çalışıyor..."; mBtn.classList.add("guncelle-btn--calisiyor"); }
      _pipelineInterval = setInterval(pipelineDurumGuncelle, 5000);
    } else if (r.status === 401) {
      _tumButonlarDevre(false);
      loginGoster("Model eğitimi için şifre gerekli.", modelEgit);
    } else {
      const d = await r.json();
      alert(d.hata || "Model eğitimi başlatılamadı.");
      _tumButonlarDevre(false);
    }
  } catch (e) { console.error("Model egit hatasi:", e); _tumButonlarDevre(false); }
}

// ── Backtest Paneli ───────────────────────────────────────────────────────────
function backtestGuncelle(data) {
  const panel = document.getElementById("backtestPanel");
  if (!data || data.hata) { panel.classList.add("gizli"); return; }
  panel.classList.remove("gizli");

  const mFark   = data.model_getiri - data.benchmark_getiri;
  const farkRenk = mFark >= 0 ? "sinyal-ozet__deger--yesil" : "sinyal-ozet__deger--kirmizi";
  const farkIsa = mFark >= 0 ? "+" : "";
  const ddRenk  = data.max_drawdown > -10 ? "" : "sinyal-ozet__deger--kirmizi";
  const sharpeRenk = data.sharpe >= 1 ? "sinyal-ozet__deger--yesil" : data.sharpe >= 0 ? "" : "sinyal-ozet__deger--kirmizi";

  document.getElementById("backtestMetrikler").innerHTML = `
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Model Getiri</span>
      <span class="sinyal-ozet__deger ${data.model_getiri >= 0 ? 'sinyal-ozet__deger--yesil' : 'sinyal-ozet__deger--kirmizi'}">%${data.model_getiri >= 0 ? '+' : ''}${data.model_getiri}</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">BIST100 (BM)</span>
      <span class="sinyal-ozet__deger">${data.benchmark_getiri >= 0 ? '+' : ''}%${data.benchmark_getiri}</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Fark (α)</span>
      <span class="sinyal-ozet__deger ${farkRenk}">${farkIsa}%${mFark.toFixed(2)}</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Sharpe</span>
      <span class="sinyal-ozet__deger ${sharpeRenk}">${data.sharpe}</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Max Drawdown</span>
      <span class="sinyal-ozet__deger ${ddRenk}">${data.max_drawdown}%</span>
    </div>
    <div class="sinyal-ozet__kart">
      <span class="sinyal-ozet__etiket">Kazanma</span>
      <span class="sinyal-ozet__deger">%${data.kazanma_orani}</span>
    </div>
  `;

  // Portföy vs Benchmark çizgi grafiği
  const tarihler  = data.gunluk.map(g => g.tarih);
  const portfoyS  = data.gunluk.map(g => g.portfoy);
  const benchmarkS = data.gunluk.map(g => g.benchmark);

  Plotly.newPlot("backtestGrafik", [
    { type: "scatter", mode: "lines", x: tarihler, y: portfoyS,
      name: "Model Stratejisi", line: { color: "#58a6ff", width: 2 } },
    { type: "scatter", mode: "lines", x: tarihler, y: benchmarkS,
      name: "BIST100 B&H", line: { color: "#8b949e", width: 1.5, dash: "dot" } },
  ], {
    ...PLOTLY_LAYOUT_BASE,
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: "Portföy Değeri (başlangıç=100)" },
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, type: "date" },
    legend: { font: { color: "#8b949e" }, orientation: "h", y: -0.2 },
    shapes: [{ type: "line", x0: tarihler[0], x1: tarihler.at(-1),
               y0: 100, y1: 100, line: { color: "#30363d", width: 1, dash: "dash" } }],
  }, PLOTLY_CONFIG);
}

async function backtestOzetYukle() {
  try {
    const data = await fetch("/api/backtest/ozet").then(r => r.json());
    if (!data || !data.length) return;

    const satirlar = data.map(h => {
      const fark = h.fark;
      const fRenk = fark >= 0 ? "#3fb950" : "#f85149";
      const sRenk = h.sharpe >= 1 ? "#3fb950" : h.sharpe >= 0 ? "#c9d1d9" : "#f85149";
      return `
        <tr>
          <td><strong>${h.hisse_kodu}</strong></td>
          <td style="color:${h.model_getiri >= 0 ? '#3fb950' : '#f85149'};font-weight:600">
            ${h.model_getiri >= 0 ? '+' : ''}%${h.model_getiri}
          </td>
          <td style="color:#8b949e">${h.benchmark_getiri >= 0 ? '+' : ''}%${h.benchmark_getiri}</td>
          <td style="color:${fRenk};font-weight:600">${fark >= 0 ? '+' : ''}%${fark.toFixed(2)}</td>
          <td style="color:${sRenk}">${h.sharpe}</td>
          <td style="color:#8b949e">${h.max_drawdown}%</td>
          <td>%${h.kazanma_orani}</td>
        </tr>`;
    }).join("");

    document.getElementById("backtestOzetTablo").innerHTML = `
      <table class="veri-tablo">
        <thead>
          <tr>
            <th>Hisse</th>
            <th>Model Getiri</th>
            <th>BIST100</th>
            <th>Fark (α)</th>
            <th>Sharpe</th>
            <th>Max DD</th>
            <th>Kazanma</th>
          </tr>
        </thead>
        <tbody>${satirlar}</tbody>
      </table>`;
  } catch (e) { console.error("Backtest ozet hatasi:", e); }
}

// ── Tüm Hisseler Özet Tablosu ─────────────────────────────────────────────────
async function tumHisselerOzetYukle() {
  try {
    const data = await fetch("/api/tum_hisseler_ozet").then(r => r.json());
    if (!data || !data.length) return;

    const satirlar = data.map(h => {
      const modelRenk = h.model_tipi === "hibrit" ? "badge--hibrit" : "badge--finansal";
      const algoRenk  = h.algoritma === "LGBM" ? "badge--lgbm" : "badge--xgb";
      const accRenk   = h.accuracy >= 58 ? "sinyal-ozet__deger--yesil" :
                        h.accuracy >= 53 ? "" : "sinyal-ozet__deger--kirmizi";
      return `
        <tr>
          <td><strong>${h.hisse_kodu}</strong></td>
          <td style="color:#8b949e">${h.sirket_adi}</td>
          <td><span class="badge ${modelRenk}">${h.model_tipi}</span></td>
          <td><span class="badge ${algoRenk}">${h.algoritma}</span></td>
          <td><span class="badge badge--esik">${h.esik}</span></td>
          <td style="font-weight:700" class="${accRenk}">%${h.accuracy}</td>
          <td style="color:#8b949e">${h.f1_macro}</td>
        </tr>`;
    }).join("");

    document.getElementById("tumHisselerTablo").innerHTML = `
      <table class="veri-tablo">
        <thead>
          <tr>
            <th>Hisse</th>
            <th>Şirket</th>
            <th>Model</th>
            <th>Algoritma</th>
            <th>Eşik</th>
            <th>Doğruluk</th>
            <th>F1 Macro</th>
          </tr>
        </thead>
        <tbody>${satirlar}</tbody>
      </table>`;
  } catch (e) {
    console.error("Tum hisseler ozet yuklenemedi:", e);
  }
}

// ── Özellik İsim Haritası ─────────────────────────────────────────────────────
const OZELLIK_ISIMLER = {
  // Fiyat
  kapanis: "Kapanış", acilis: "Açılış", hacim: "Hacim",
  hacim_oran: "Hacim Oranı", hl_spread: "Yüksek-Düşük Farkı",
  // Teknik
  RSI: "RSI", MACD: "MACD", MACD_signal: "MACD Sinyal",
  SMA_20: "SMA 20", SMA_50: "SMA 50", ATR: "ATR",
  BB_upper: "Bollinger Üst", BB_lower: "Bollinger Alt", BB_width: "Bollinger Genişliği",
  STOCH_k: "Stokastik %K", ROC: "ROC",
  // Duygu
  duygu_skoru: "Duygu Skoru", duygu_momentum: "Duygu Momentumu",
  duygu_std7: "Duygu Std (7g)", duygu_hacim: "Duygu × Hacim",
  duygu_abs_mom: "Duygu Abs. Mom.",
  // Haber
  haber_duygu: "Haber Skoru", haber_momentum: "Haber Momentumu",
  haber_hacim: "Haber × Hacim",
  // Makro
  usdtry_getiri: "USD/TRY", bist100_getiri: "BIST100",
  petrol_getiri: "Petrol", altin_getiri: "Altın",
};

function ozellikEtiket(ad) {
  // "duygu_skoru_lag3" → "Duygu Skoru +3g"
  const lagEsle = ad.match(/^(.+)_lag(\d+)$/);
  if (lagEsle) {
    const temel = OZELLIK_ISIMLER[lagEsle[1]] || lagEsle[1];
    return `${temel} +${lagEsle[2]}g`;
  }
  return OZELLIK_ISIMLER[ad] || ad;
}

// ── Feature Importance Grafiği ───────────────────────────────────────────────
function onemGrafikiCiz(data) {
  const panel = document.getElementById("onemPanel");

  if (!data || data.hata || !data.length) {
    panel.classList.add("gizli");
    return;
  }

  panel.classList.remove("gizli");

  // API büyükten küçüğe sıralı geliyor; grafikte aşağıdan yukarı için ters çevir
  const hammadde = data.slice().reverse();
  const isimler  = hammadde.map(d => ozellikEtiket(d.ozellik));
  const degerler = hammadde.map(d => d.onem);

  const DUYGU_ANAHTAR = ["duygu", "haber", "kaynak_sayisi", "konsensus", "std_kaynak"];
  const renkler = hammadde.map(d =>
    DUYGU_ANAHTAR.some(k => d.ozellik.includes(k)) ? "#f0883e" :
    d.ozellik.includes("lag") ? "#79c0ff" :
    "#58a6ff"
  );

  const trace = {
    type:        "bar",
    orientation: "h",
    x:           degerler,
    y:           isimler,
    marker:      { color: renkler, opacity: 0.85 },
    hovertemplate: "<b>%{y}</b>: %{x:.4f}<extra></extra>",
  };

  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: "Önem (Gain)", type: "linear" },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickfont: { size: 11 } },
    margin: { t: 10, r: 20, b: 50, l: 170 },
    annotations: [{
      x: 0.99, y: 0.02,
      xref: "paper", yref: "paper",
      text: "■ Duygu  ■ Lag özelliği  ■ Teknik/Makro",
      showarrow: false,
      font: { size: 10, color: "#8b949e" },
      align: "right",
    }],
  };

  Plotly.newPlot("onemGrafik", [trace], layout, PLOTLY_CONFIG);
}
