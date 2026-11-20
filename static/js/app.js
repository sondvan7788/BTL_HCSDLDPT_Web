// app.js - Frontend Logic for Voice Retrieval Web Application

let selectedFile = null;
let comparisonChartInstance = null;
let f0ChartInstance = null;
let durationChartInstance = null;
let currentDbPage = 1;

document.addEventListener("DOMContentLoaded", () => {
    initDropZone();
    loadDatabaseStats();
    loadDatabasePage(1);
});

// ====================================================================
// TAB SWITCHING
// ====================================================================
function switchTab(tabId) {
    const tabs = ['search', 'explorer', 'analytics'];
    tabs.forEach(t => {
        document.getElementById(`tab-${t}`).classList.add('hidden');
        const btn = document.getElementById(`tab-btn-${t}`);
        btn.classList.remove('border-indigo-500', 'text-indigo-400');
        btn.classList.add('border-transparent', 'text-slate-400');
    });

    document.getElementById(`tab-${tabId}`).classList.remove('hidden');
    const activeBtn = document.getElementById(`tab-btn-${tabId}`);
    activeBtn.classList.remove('border-transparent', 'text-slate-400');
    activeBtn.classList.add('border-indigo-500', 'text-indigo-400');

    if (tabId === 'analytics') {
        loadAnalyticsCharts();
    }
}

// ====================================================================
// DRAG & DROP AND FILE SELECTION
// ====================================================================
function initDropZone() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("audio-input-file");

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleSelectedFile(e.target.files[0]);
        }
    });

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("border-indigo-500", "bg-indigo-950/20");
    });

    dropZone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        dropZone.classList.remove("border-indigo-500", "bg-indigo-950/20");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("border-indigo-500", "bg-indigo-950/20");
        if (e.dataTransfer.files.length > 0) {
            handleSelectedFile(e.dataTransfer.files[0]);
        }
    });
}

function handleSelectedFile(file) {
    selectedFile = file;
    document.getElementById("selected-file-name").textContent = file.name;
    document.getElementById("selected-file-preview").classList.remove("hidden");
}

function clearSelectedFile() {
    selectedFile = null;
    document.getElementById("audio-input-file").value = "";
    document.getElementById("selected-file-preview").classList.add("hidden");
}

// ====================================================================
// EXECUTE SEARCH (API CALL)
// ====================================================================
async function executeSearch() {
    if (!selectedFile) {
        alert("Vui lòng kéo thả hoặc tải lên một file âm thanh để tìm kiếm!");
        return;
    }

    const loadingEl = document.getElementById("search-loading");
    const emptyEl = document.getElementById("search-empty-state");
    const resultsWrapper = document.getElementById("search-results-wrapper");
    const submitBtn = document.getElementById("btn-submit-search");

    emptyEl.classList.add("hidden");
    resultsWrapper.classList.add("hidden");
    loadingEl.classList.remove("hidden");
    submitBtn.disabled = true;

    const formData = new FormData();
    formData.append("file", selectedFile);

    const topK = document.getElementById("param-top-k").value;
    formData.append("top_k", topK);

    const f0Min = document.getElementById("param-f0-min").value;
    const f0Max = document.getElementById("param-f0-max").value;
    if (f0Min) formData.append("f0_min", f0Min);
    if (f0Max) formData.append("f0_max", f0Max);

    try {
        const res = await fetch("/api/search", {
            method: "POST",
            body: formData
        });
        const resData = await res.json();

        loadingEl.classList.add("hidden");
        submitBtn.disabled = false;

        if (resData.success) {
            renderSearchResults(resData.data);
            resultsWrapper.classList.remove("hidden");
        } else {
            alert("Lỗi tìm kiếm: " + resData.error);
            emptyEl.classList.remove("hidden");
        }
    } catch (err) {
        loadingEl.classList.add("hidden");
        submitBtn.disabled = false;
        emptyEl.classList.remove("hidden");
        alert("Lỗi kết nối tới máy chủ: " + err.message);
    }
}

// ====================================================================
// RENDER SEARCH RESULTS
// ====================================================================
function renderSearchResults(data) {
    const q = data.query_info;
    const lat = data.latency;
    const results = data.top_results;

    // 1. Render Query Info
    document.getElementById("res-query-name").textContent = q.file_name;
    document.getElementById("res-query-duration").textContent = `${q.duration_s} s`;
    document.getElementById("res-query-f0").textContent = `${q.pitch_f0_mean} Hz`;
    document.getElementById("res-query-voiced").textContent = `${q.voiced_pct}%`;
    document.getElementById("res-query-centroid").textContent = `${q.spectral_centroid_mean} Hz`;
    document.getElementById("res-latency-badge").textContent = `Tổng: ${lat.total_ms}ms (Postgres: ${lat.postgres_query_ms}ms)`;

    const queryAudioPlayer = document.getElementById("query-audio-player");
    queryAudioPlayer.src = q.audio_url;

    // 2. Render Top Results Cards
    const container = document.getElementById("top-results-container");
    container.innerHTML = "";

    results.forEach((r, idx) => {
        let badgeClass = "badge-normal";
        let rankIcon = `<span class="text-xs font-mono font-bold">#${r.rank}</span>`;
        if (r.rank === 1) {
            badgeClass = "badge-gold";
            rankIcon = `<i class="fa-solid fa-crown text-xs"></i> <span class="font-bold">#1</span>`;
        } else if (r.rank === 2) {
            badgeClass = "badge-silver";
            rankIcon = `<span class="font-bold">#2</span>`;
        } else if (r.rank === 3) {
            badgeClass = "badge-bronze";
            rankIcon = `<span class="font-bold">#3</span>`;
        }

        const simPercent = Math.min(100, Math.max(0, r.cosine_similarity * 100)).toFixed(1);
        let barColor = "from-emerald-500 to-teal-400";
        if (r.cosine_similarity < 0.6) barColor = "from-amber-500 to-yellow-400";

        const card = document.createElement("div");
        card.className = "glass-card glass-card-hover rounded-xl p-4 border border-slate-800 space-y-3";
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="px-2.5 py-1 rounded-lg text-xs flex items-center space-x-1 ${badgeClass}">
                        ${rankIcon}
                    </span>
                    <div>
                        <h4 class="font-bold text-sm text-slate-100">${r.file_name}</h4>
                        <p class="text-xs text-slate-400 font-mono">
                            ${r.duration_s}s • F0: ${r.pitch_f0_mean} Hz (Δ ${r.delta_f0_hz > 0 ? '+' : ''}${r.delta_f0_hz}Hz) • Centroid: ${r.spectral_centroid_mean} Hz
                        </p>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-sm font-extrabold text-emerald-400 font-mono">${(r.cosine_similarity * 100).toFixed(2)}%</div>
                    <div class="text-[10px] text-slate-400">Cosine Sim: ${r.cosine_similarity}</div>
                </div>
            </div>

            <!-- Progress Bar -->
            <div class="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                <div class="bg-gradient-to-r ${barColor} h-1.5 rounded-full" style="width: ${simPercent}%"></div>
            </div>

            <!-- Audio Player and Explanation -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-slate-800/60">
                <p class="text-xs text-slate-300 italic flex items-center space-x-1.5">
                    <i class="fa-solid fa-circle-info text-indigo-400 text-[10px]"></i>
                    <span>${r.explanation}</span>
                </p>
                <div class="flex-shrink-0">
                    <audio controls src="${r.audio_url}" class="w-full sm:w-48 h-7"></audio>
                </div>
            </div>
        `;
        container.appendChild(card);
    });

    // 3. Render Comparison Chart
    renderComparisonChart(q, results);
}

// ====================================================================
// COMPARISON CHART (CHART.JS)
// ====================================================================
function renderComparisonChart(query, results) {
    const ctx = document.getElementById("comparisonChart").getContext("2d");
    if (comparisonChartInstance) {
        comparisonChartInstance.destroy();
    }

    const labels = ["Query File", ...results.map(r => `Top ${r.rank}`)];
    const f0Data = [query.pitch_f0_mean, ...results.map(r => r.pitch_f0_mean)];
    const centroidData = [query.spectral_centroid_mean, ...results.map(r => r.spectral_centroid_mean)];

    comparisonChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Cao độ F0 (Hz)",
                    data: f0Data,
                    backgroundColor: "rgba(16, 185, 129, 0.7)",
                    borderColor: "#10b981",
                    borderWidth: 1,
                    yAxisID: "y"
                },
                {
                    label: "Trọng tâm phổ (Hz)",
                    data: centroidData,
                    backgroundColor: "rgba(99, 102, 241, 0.5)",
                    borderColor: "#6366f1",
                    borderWidth: 1,
                    yAxisID: "y1"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: "#cbd5e1", font: { size: 11 } }
                }
            },
            scales: {
                x: {
                    ticks: { color: "#94a3b8", font: { size: 10 } },
                    grid: { color: "rgba(255, 255, 255, 0.05)" }
                },
                y: {
                    type: "linear",
                    position: "left",
                    title: { display: true, text: "F0 (Hz)", color: "#10b981" },
                    ticks: { color: "#10b981" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" }
                },
                y1: {
                    type: "linear",
                    position: "right",
                    title: { display: true, text: "Centroid (Hz)", color: "#6366f1" },
                    ticks: { color: "#6366f1" },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

// ====================================================================
// DATABASE EXPLORER
// ====================================================================
async function loadDatabasePage(page) {
    currentDbPage = page;
    const searchVal = document.getElementById("db-search-input").value;
    try {
        const res = await fetch(`/api/database/list?page=${page}&limit=15&search=${encodeURIComponent(searchVal)}`);
        const data = await res.json();
        if (data.success) {
            renderDatabaseTable(data);
        }
    } catch (err) {
        console.error("Lỗi load CSDL:", err);
    }
}

function handleDbSearch(e) {
    if (e.key === "Enter") {
        loadDatabasePage(1);
    }
}

function changeDbPage(delta) {
    loadDatabasePage(Math.max(1, currentDbPage + delta));
}

function renderDatabaseTable(data) {
    const tbody = document.getElementById("db-table-body");
    tbody.innerHTML = "";

    data.items.forEach(item => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-900/60 transition-colors";
        tr.innerHTML = `
            <td class="py-2.5 px-3 font-mono text-slate-400">#${item.file_id}</td>
            <td class="py-2.5 px-3 font-semibold text-slate-200">${item.file_name}</td>
            <td class="py-2.5 px-3 font-mono">${item.duration_s} s</td>
            <td class="py-2.5 px-3 font-mono text-emerald-400">${item.pitch_f0_mean} Hz</td>
            <td class="py-2.5 px-3 font-mono">${item.voiced_pct}%</td>
            <td class="py-2.5 px-3 font-mono text-indigo-400">${item.spectral_centroid_mean} Hz</td>
            <td class="py-2.5 px-3 text-center">
                <audio controls src="${item.audio_url}" class="h-6 w-36 mx-auto"></audio>
            </td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById("db-current-page").textContent = data.page;
    document.getElementById("db-pagination-info").textContent = 
        `Hiển thị ${(data.page - 1) * data.limit + 1} - ${Math.min(data.page * data.limit, data.total)} trong tổng số ${data.total} files`;
    document.getElementById("db-btn-prev").disabled = (data.page <= 1);
    document.getElementById("db-btn-next").disabled = (data.page * data.limit >= data.total);
}

// ====================================================================
// ANALYTICS CHARTS & STATS
// ====================================================================
async function loadDatabaseStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        if (data.success) {
            const s = data.data;
            document.getElementById("analytics-avg-dur").textContent = `${s.duration.avg} s`;
            document.getElementById("analytics-avg-f0").textContent = `${s.pitch_f0.avg} Hz`;
            document.getElementById("analytics-db-size").textContent = s.database_size;
        }
    } catch (err) {
        console.error("Lỗi stats:", err);
    }
}

async function loadAnalyticsCharts() {
    try {
        const res = await fetch("/api/database/chart_data");
        const data = await res.json();
        if (!data.success) return;

        // F0 Distribution Chart
        const f0Ctx = document.getElementById("f0DistributionChart").getContext("2d");
        if (f0ChartInstance) f0ChartInstance.destroy();
        f0ChartInstance = new Chart(f0Ctx, {
            type: "bar",
            data: {
                labels: data.f0_distribution.bins,
                datasets: [{
                    label: "Số lượng file giọng nữ",
                    data: data.f0_distribution.counts,
                    backgroundColor: "rgba(168, 85, 247, 0.7)",
                    borderColor: "#a855f7",
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
                }
            }
        });

        // Duration Distribution Chart
        const durCtx = document.getElementById("durationDistributionChart").getContext("2d");
        if (durationChartInstance) durationChartInstance.destroy();
        durationChartInstance = new Chart(durCtx, {
            type: "bar",
            data: {
                labels: data.duration_distribution.bins,
                datasets: [{
                    label: "Số lượng file",
                    data: data.duration_distribution.counts,
                    backgroundColor: "rgba(59, 130, 246, 0.7)",
                    borderColor: "#3b82f6",
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
                }
            }
        });

    } catch (err) {
        console.error("Lỗi chart data:", err);
    }
}
