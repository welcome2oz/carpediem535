const state = {
  countries: [],
  cargoProfiles: [],
  rates: {},
};

const SEQ_RAMP = [
  "--seq-100", "--seq-150", "--seq-200", "--seq-250", "--seq-300", "--seq-350",
  "--seq-400", "--seq-450", "--seq-500", "--seq-550", "--seq-600", "--seq-650", "--seq-700",
];

const $ = (id) => document.getElementById(id);

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `요청 실패 (${res.status})`);
  return body;
}

function countryByCode(code) {
  return state.countries.find((c) => c.code === code);
}

function cargoById(id) {
  return state.cargoProfiles.find((c) => c.id === id);
}

function searchQueryFor(country) {
  const match = country.port.match(/\(([^)]+)\)/);
  const city = match ? match[1] : country.port;
  return `${city}, ${country.name}`;
}

const formatUSD = (num) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(num || 0);

function showToast(msg) {
  const toast = $("toast");
  toast.textContent = msg;
  toast.classList.add("is-visible");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove("is-visible"), 3200);
}

// ---------------------------------------------------------------------------
// Cost model (mirrors the server-side data, calculated client-side for speed)
// ---------------------------------------------------------------------------

function routeKey(originCode, destCode) {
  return `${originCode}-${destCode}`;
}

function getOceanBase(originCode, destCode) {
  const entry = state.rates[routeKey(originCode, destCode)];
  return entry ? entry.rate : 0;
}

function calcRoute(originCode, destCode, cargoId, oceanBaseOverride) {
  const origin = countryByCode(originCode);
  const dest = countryByCode(destCode);
  const cargo = cargoById(cargoId);
  const oceanBase = oceanBaseOverride ?? getOceanBase(originCode, destCode);

  const expTrucking = origin.inlandTrucking * (cargo.isHeavy ? origin.heavyMultiplier : 1);
  const expHeavySurcharge = expTrucking - origin.inlandTrucking;
  const exportTotalContainer = expTrucking + origin.portHandling;

  const oceanHws = cargo.isHeavy ? 300 : 0;
  const insurance = 50;
  const oceanTotalContainer = oceanBase + oceanHws + insurance;

  const impTrucking = dest.inlandTrucking * (cargo.isHeavy ? dest.heavyMultiplier : 1);
  const impHeavySurcharge = impTrucking - dest.inlandTrucking;
  const importTotalContainer = impTrucking + dest.portHandling + dest.customsClearance;

  const exportMT = exportTotalContainer / cargo.weightMT;
  const oceanMT = oceanTotalContainer / cargo.weightMT;
  const importMT = importTotalContainer / cargo.weightMT;

  return {
    origin, dest, cargo, oceanBase,
    expTrucking, expHeavySurcharge, exportTotalContainer,
    oceanHws, insurance, oceanTotalContainer,
    impTrucking, impHeavySurcharge, importTotalContainer,
    exportMT, oceanMT, importMT,
    totalMT: exportMT + oceanMT + importMT,
  };
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

const VIEW_TITLES = {
  matrix: "Total Logistics Cost Matrix",
  simulator: "Detailed Route Simulator",
  rates: "해상운임 관리",
};

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });
}

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("is-active", v.id === `view-${view}`));
  $("viewTitle").textContent = VIEW_TITLES[view];
  if (view === "rates") renderScheduleBanner();
}

// ---------------------------------------------------------------------------
// Selects
// ---------------------------------------------------------------------------

function populateSelects() {
  const cargoOptionsHtml = state.cargoProfiles
    .map((c) => `<option value="${c.id}">${c.name} (${c.weightMT} MT)</option>`)
    .join("");
  $("matrixCargoSelect").innerHTML = cargoOptionsHtml;
  $("cargoSelect").innerHTML = cargoOptionsHtml;

  const countryOptionsHtml = state.countries
    .map((c) => `<option value="${c.code}">${c.name} (${c.port})</option>`)
    .join("");
  $("exportSelect").innerHTML = countryOptionsHtml;
  $("importSelect").innerHTML = countryOptionsHtml;
  $("importSelect").selectedIndex = Math.min(7, state.countries.length - 1);
}

// ---------------------------------------------------------------------------
// Matrix view
// ---------------------------------------------------------------------------

function buildLegend() {
  const el = $("legendRamp");
  el.innerHTML = SEQ_RAMP.map((v) => `<span style="background:var(${v})"></span>`).join("");
}

function buildMatrix() {
  const cargoId = $("matrixCargoSelect").value;
  const headRow = $("matrixHeadRow");
  const body = $("matrixBody");

  headRow.innerHTML =
    '<th>Export \\ Import</th>' + state.countries.map((c) => `<th>${c.code}</th>`).join("");

  const cells = [];
  state.countries.forEach((origin) => {
    state.countries.forEach((dest) => {
      if (origin.code === dest.code) return;
      const r = calcRoute(origin.code, dest.code, cargoId);
      cells.push({ origin: origin.code, dest: dest.code, value: r.totalMT });
    });
  });
  const values = cells.map((c) => c.value);
  const min = Math.min(...values);
  const max = Math.max(...values);

  function colorFor(value) {
    if (max === min) return SEQ_RAMP[0];
    const idx = Math.round(((value - min) / (max - min)) * (SEQ_RAMP.length - 1));
    return SEQ_RAMP[idx];
  }

  const isDark = (document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";

  body.innerHTML = "";
  state.countries.forEach((origin) => {
    const tr = document.createElement("tr");
    const head = document.createElement("td");
    head.textContent = origin.code;
    tr.appendChild(head);

    state.countries.forEach((dest) => {
      const td = document.createElement("td");
      if (origin.code === dest.code) {
        td.className = "matrix-cell is-diagonal";
        td.textContent = "–";
      } else {
        const r = calcRoute(origin.code, dest.code, cargoId);
        const varName = colorFor(r.totalMT);
        const idx = SEQ_RAMP.indexOf(varName);
        const isHighEmphasis = idx >= 7;
        const useDarkText = isDark ? isHighEmphasis : !isHighEmphasis;
        td.className = "matrix-cell";
        td.style.background = `var(${varName})`;
        td.style.color = useDarkText ? "#0b0b0b" : "#ffffff";
        td.textContent = formatUSD(r.totalMT);
        td.title = `${origin.name} → ${dest.name}: ${formatUSD(r.totalMT)}/MT`;
        td.addEventListener("click", () => {
          $("exportSelect").value = origin.code;
          $("importSelect").value = dest.code;
          $("cargoSelect").value = cargoId;
          switchView("simulator");
          updateFreightInput();
        });
      }
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

// ---------------------------------------------------------------------------
// Simulator view
// ---------------------------------------------------------------------------

function updateFreightInput() {
  const expCode = $("exportSelect").value;
  const impCode = $("importSelect").value;
  if (expCode === impCode) {
    $("freightInput").value = 0;
    $("freightMeta").textContent = "";
    return;
  }
  const entry = state.rates[routeKey(expCode, impCode)];
  $("freightInput").value = entry ? entry.rate : 0;
  $("freightMeta").textContent = entry ? freshnessLabel(entry) : "저장된 값 없음";
  calculateCost();
}

function freshnessInfo(entry) {
  if (!entry) return { level: "neutral", label: "데이터 없음" };
  if (entry.source === "seed") return { level: "neutral", label: "샘플 값" };
  const ageDays = (Date.now() - new Date(entry.updatedAt).getTime()) / 86400000;
  if (ageDays <= 3) return { level: "good", label: `${Math.floor(ageDays)}일 전 갱신` };
  if (ageDays <= 14) return { level: "warning", label: `${Math.floor(ageDays)}일 전 갱신` };
  return { level: "critical", label: `${Math.floor(ageDays)}일 전 갱신 (오래됨)` };
}

function freshnessLabel(entry) {
  const info = freshnessInfo(entry);
  const sourceLabel = { seed: "샘플", manual: "수동", scraped: "자동(RPA)" }[entry.source] || entry.source;
  return `${sourceLabel} · ${info.label}`;
}

function calculateCost() {
  const exwVal = parseFloat($("exwInput").value) || 0;
  const cargoId = $("cargoSelect").value;
  const expCode = $("exportSelect").value;
  const impCode = $("importSelect").value;

  if (expCode === impCode) {
    showToast("출발지와 도착지가 같을 수 없습니다.");
    return;
  }

  const oceanBase = parseFloat($("freightInput").value) || 0;
  const r = calcRoute(expCode, impCode, cargoId, oceanBase);

  const fobMT = exwVal + r.exportMT;
  const cifMT = fobMT + r.oceanMT;
  const dapMT = cifMT + r.importMT;

  $("resultsArea").classList.remove("hidden");
  $("resExw").textContent = formatUSD(exwVal);
  $("resFobAdd").textContent = `+${formatUSD(r.exportMT)}`;
  $("resFob").textContent = formatUSD(fobMT);
  $("resCifAdd").textContent = `+${formatUSD(r.oceanMT)}`;
  $("resCif").textContent = formatUSD(cifMT);
  $("resDapAdd").textContent = `+${formatUSD(r.importMT)}`;
  $("resDap").textContent = formatUSD(dapMT);

  $("detailExport").innerHTML = `
    <li><span>내륙운송비</span><span>$${r.origin.inlandTrucking.toFixed(0)}</span></li>
    <li><span>항만 부대비용</span><span>$${r.origin.portHandling.toFixed(0)}</span></li>
    ${r.expHeavySurcharge > 0 ? `<li class="wf-highlight"><span>중량화물 할증</span><span>+$${r.expHeavySurcharge.toFixed(0)}</span></li>` : ""}
    <li class="wf-total"><span>Total (Container)</span><span>$${r.exportTotalContainer.toFixed(0)}</span></li>
  `;

  $("detailOcean").innerHTML = `
    <li><span>Ocean Freight</span><span>$${r.oceanBase.toFixed(0)}</span></li>
    ${r.oceanHws > 0 ? `<li class="wf-highlight"><span>중량화물 할증</span><span>+$${r.oceanHws.toFixed(0)}</span></li>` : ""}
    <li><span>Insurance</span><span>$${r.insurance.toFixed(0)}</span></li>
    <li class="wf-total"><span>Total (Container)</span><span>$${r.oceanTotalContainer.toFixed(0)}</span></li>
  `;

  $("detailImport").innerHTML = `
    <li><span>항만 부대비용</span><span>$${r.dest.portHandling.toFixed(0)}</span></li>
    <li><span>통관비</span><span>$${r.dest.customsClearance.toFixed(0)}</span></li>
    <li><span>내륙운송비</span><span>$${r.dest.inlandTrucking.toFixed(0)}</span></li>
    ${r.impHeavySurcharge > 0 ? `<li class="wf-highlight"><span>중량화물 할증</span><span>+$${r.impHeavySurcharge.toFixed(0)}</span></li>` : ""}
    <li class="wf-total"><span>Total (Container)</span><span>$${r.importTotalContainer.toFixed(0)}</span></li>
  `;

  buildMatrix();
}

async function refreshOneRoute() {
  const expCode = $("exportSelect").value;
  const impCode = $("importSelect").value;
  if (expCode === impCode) return;
  const origin = countryByCode(expCode);
  const dest = countryByCode(impCode);

  const btn = $("refreshOneBtn");
  btn.disabled = true;
  btn.textContent = "조회 중...";
  try {
    const result = await fetchJSON("/api/rates/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin: expCode, dest: impCode,
        origin_query: searchQueryFor(origin), dest_query: searchQueryFor(dest),
      }),
    });
    state.rates[routeKey(expCode, impCode)] = result;
    updateFreightInput();
    showToast(`Cogoport 조회 완료: ${formatUSD(result.rate)}`);
  } catch (e) {
    showToast(`조회 실패: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Cogoport에서 재조회";
  }
}

// ---------------------------------------------------------------------------
// Rates management view
// ---------------------------------------------------------------------------

function allRouteKeys() {
  const keys = [];
  state.countries.forEach((o) => state.countries.forEach((d) => {
    if (o.code !== d.code) keys.push(routeKey(o.code, d.code));
  }));
  return keys;
}

function renderRatesTable(filter = "") {
  const body = $("ratesBody");
  const term = filter.trim().toUpperCase();
  const keys = allRouteKeys().filter((k) => !term || k.includes(term));

  body.innerHTML = keys.map((key) => {
    const entry = state.rates[key];
    const info = freshnessInfo(entry);
    const badgeClass = { good: "badge-good", warning: "badge-warning", critical: "badge-critical", neutral: "badge-neutral" }[info.level];
    const sourceLabel = entry ? ({ seed: "샘플", manual: "수동", scraped: "자동(RPA)" }[entry.source] || entry.source) : "-";
    const updatedAt = entry ? new Date(entry.updatedAt).toLocaleString("ko-KR") : "-";
    return `
      <tr data-key="${key}">
        <td class="route-key">${key}</td>
        <td><input type="number" class="rate-input" value="${entry ? entry.rate : ""}" min="0"></td>
        <td>${sourceLabel}</td>
        <td class="muted">${updatedAt}</td>
        <td><span class="badge ${badgeClass}">${info.label}</span></td>
        <td>
          <button class="btn btn-ghost btn-sm row-save">저장</button>
          <button class="btn btn-ghost btn-sm row-refresh">재조회</button>
        </td>
      </tr>
    `;
  }).join("");

  body.querySelectorAll("tr").forEach((tr) => {
    const key = tr.dataset.key;
    const [oCode, dCode] = key.split("-");
    tr.querySelector(".row-save").addEventListener("click", async () => {
      const val = parseFloat(tr.querySelector(".rate-input").value);
      if (!(val > 0)) return showToast("유효한 운임 값을 입력하세요.");
      const entry = await fetchJSON(`/api/rates/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rate: val, note: "수동 수정" }),
      });
      state.rates[key] = entry;
      renderRatesTable($("rateSearch").value);
      showToast(`${key} 수동 갱신 완료`);
    });
    tr.querySelector(".row-refresh").addEventListener("click", async (ev) => {
      const btn = ev.currentTarget;
      btn.disabled = true;
      btn.textContent = "조회중";
      try {
        const origin = countryByCode(oCode);
        const dest = countryByCode(dCode);
        const result = await fetchJSON("/api/rates/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            origin: oCode, dest: dCode,
            origin_query: searchQueryFor(origin), dest_query: searchQueryFor(dest),
          }),
        });
        state.rates[key] = result;
        renderRatesTable($("rateSearch").value);
        showToast(`${key} 자동 조회 완료: ${formatUSD(result.rate)}`);
      } catch (e) {
        showToast(`${key} 조회 실패: ${e.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "재조회";
      }
    });
  });
}

async function renderScheduleBanner() {
  const el = $("scheduleBanner");
  try {
    const s = await fetchJSON("/api/scheduler/status");
    const parts = [];

    if (s.enabled === false) {
      parts.push("자동 갱신 비활성화됨 (서버 환경변수 DAILY_REFRESH_ENABLED=false)");
    } else if (s.hour !== undefined) {
      const hhmm = `${String(s.hour).padStart(2, "0")}:${String(s.minute).padStart(2, "0")}`;
      parts.push(`<strong>매일 ${hhmm} (${s.timezone || "UTC"})</strong> Cogoport 자동 갱신`);
      if (s.nextRunAt) parts.push(`다음 실행: ${new Date(s.nextRunAt).toLocaleString("ko-KR")}`);
    }

    if (s.status === "running") {
      parts.push(`<span class="badge badge-warning">지금 실행 중</span>`);
    } else if (s.status === "done") {
      parts.push(`<span class="badge badge-good">최근 성공</span> ${s.updated}/${s.totalRoutes}개 갱신 · ${new Date(s.finishedAt).toLocaleString("ko-KR")}`);
    } else if (s.status === "error") {
      parts.push(`<span class="badge badge-critical">최근 실패</span> ${s.error} · ${new Date(s.finishedAt).toLocaleString("ko-KR")}`);
    } else if (s.enabled !== false) {
      parts.push("아직 자동 실행 이력이 없습니다");
    }

    el.innerHTML = parts.join(" · ");
  } catch (e) {
    el.innerHTML = "";
  }
}

async function refreshAllRoutes() {
  const btn = $("refreshAllBtn");
  const statusEl = $("refreshAllStatus");
  btn.disabled = true;
  statusEl.classList.remove("hidden");
  statusEl.textContent = "전체 구간 자동 재조회를 시작합니다 (수 분 소요될 수 있습니다)...";
  try {
    const { jobId } = await fetchJSON("/api/rates/refresh-all", { method: "POST" });
    const poll = async () => {
      const job = await fetchJSON(`/api/jobs/${jobId}`);
      if (job.status === "done") {
        statusEl.textContent = `완료: ${job.updated}개 구간 갱신됨 (${new Date(job.finishedAt).toLocaleString("ko-KR")})`;
        state.rates = await fetchJSON("/api/rates");
        renderRatesTable($("rateSearch").value);
        buildMatrix();
        btn.disabled = false;
        return;
      }
      if (job.status === "error") {
        statusEl.textContent = `오류 발생: ${job.error}`;
        btn.disabled = false;
        return;
      }
      statusEl.textContent = `진행 중... (${job.status})`;
      setTimeout(poll, 4000);
    };
    setTimeout(poll, 2000);
  } catch (e) {
    statusEl.textContent = `시작 실패: ${e.message}`;
    btn.disabled = false;
  }
}

async function bulkSync() {
  const raw = $("bulkJsonInput").value.trim();
  if (!raw) return;
  try {
    const routes = JSON.parse(raw);
    const result = await fetchJSON("/api/rates/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ routes }),
    });
    state.rates = await fetchJSON("/api/rates");
    renderRatesTable($("rateSearch").value);
    buildMatrix();
    $("bulkJsonInput").value = "";
    showToast(`${result.updated}개 구간 일괄 갱신 완료`);
  } catch (e) {
    showToast(`JSON 처리 오류: ${e.message}`);
  }
}

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

function setupTheme() {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  updateThemeLabel();
  $("themeToggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    updateThemeLabel();
    if (state.countries.length) buildMatrix();
  });
}

function updateThemeLabel() {
  const current = document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  $("themeLabel").textContent = current === "dark" ? "Light mode" : "Dark mode";
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
  setupNav();
  setupTheme();
  buildLegend();

  const [config, rates] = await Promise.all([
    fetchJSON("/api/config"),
    fetchJSON("/api/rates"),
  ]);
  state.countries = config.countries;
  state.cargoProfiles = config.cargoProfiles;
  state.rates = rates;

  populateSelects();
  buildMatrix();
  updateFreightInput();
  renderRatesTable();
  renderScheduleBanner();

  $("matrixCargoSelect").addEventListener("change", buildMatrix);
  $("cargoSelect").addEventListener("change", calculateCost);
  $("exportSelect").addEventListener("change", updateFreightInput);
  $("importSelect").addEventListener("change", updateFreightInput);
  $("calcBtn").addEventListener("click", calculateCost);
  $("refreshOneBtn").addEventListener("click", refreshOneRoute);
  $("refreshAllBtn").addEventListener("click", refreshAllRoutes);
  $("bulkSyncBtn").addEventListener("click", bulkSync);
  $("rateSearch").addEventListener("input", (e) => renderRatesTable(e.target.value));

  setInterval(() => {
    if ($("view-rates").classList.contains("is-active")) renderScheduleBanner();
  }, 60000);
}

init().catch((e) => showToast(`초기화 실패: ${e.message}`));
