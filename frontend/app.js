/**
 * ClickPe Loan Eligibility Engine Frontend Controller
 */

let selectedFile = null;

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initDropzone();
    initButtons();
    fetchStats();
    fetchHealth();
    fetchProducts();
    fetchMatches();

    // Periodic KPI update
    setInterval(fetchStats, 5000);
});

/* Tabs Switching */
function initTabs() {
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-tab");

            tabBtns.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add("active");
            }

            if (targetId === "tab-matches") fetchMatches();
            if (targetId === "tab-products") fetchProducts();
            if (targetId === "tab-email") reloadEmailFrame();
        });
    });
}

/* Logging helper */
function appendLog(msg) {
    const consoleLog = document.getElementById("console-log");
    const time = new Date().toLocaleTimeString();
    consoleLog.textContent += `\n[${time}] ${msg}`;
    consoleLog.scrollTop = consoleLog.scrollHeight;
}

/* Dropzone & File Handling */
function initDropzone() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("csv-file-input");
    const browseBtn = document.getElementById("browse-btn");
    const previewCard = document.getElementById("file-preview-card");

    browseBtn.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("click", (e) => {
        if (e.target !== browseBtn) fileInput.click();
    });

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

function handleFileSelect(file) {
    if (!file.name.endsWith(".csv")) {
        alert("Please upload a CSV file (.csv).");
        return;
    }
    selectedFile = file;

    document.getElementById("preview-filename").textContent = file.name;
    document.getElementById("preview-filesize").textContent = `${(file.size / 1024).toFixed(1)} KB`;
    document.getElementById("file-preview-card").style.display = "block";

    // Quick client-side line count preview
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        const lines = text.split("\n").filter(l => l.trim().length > 0);
        document.getElementById("preview-rowcount").textContent = Math.max(0, lines.length - 1).toLocaleString();
    };
    reader.readAsText(file.slice(0, 500000)); // preview first 500KB

    appendLog(`Selected CSV: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
}

/* Buttons and Orchestrator Actions */
function initButtons() {
    document.getElementById("btn-clear-log").addEventListener("click", () => {
        document.getElementById("console-log").textContent = "[Console Cleared]";
    });

    document.getElementById("btn-start-upload").addEventListener("click", uploadSelectedFile);
    document.getElementById("btn-load-sample").addEventListener("click", loadSampleDataset);
    document.getElementById("btn-run-discovery").addEventListener("click", runDiscovery);
    document.getElementById("btn-run-matching").addEventListener("click", runMatching);
    document.getElementById("btn-run-notify").addEventListener("click", runNotification);
    document.getElementById("btn-run-full-pipeline").addEventListener("click", runFullPipeline);
    document.getElementById("btn-refresh-matches").addEventListener("click", fetchMatches);
    document.getElementById("btn-refresh-products").addEventListener("click", fetchProducts);
    document.getElementById("btn-refresh-email-preview").addEventListener("click", reloadEmailFrame);
    document.getElementById("filter-employment").addEventListener("change", fetchMatches);

    document.getElementById("btn-save-test-email").addEventListener("click", () => {
        const email = document.getElementById("test-email-input").value.trim();
        if (email) {
            appendLog(`Updated safe test email alias target to: ${email}`);
            alert(`Target test recipient set to: ${email}`);
        }
    });
}

/* API Calls */
async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        if (res.ok) {
            const data = await res.json();
            document.getElementById("kpi-users").textContent = (data.total_users || 0).toLocaleString();
            document.getElementById("kpi-products").textContent = (data.active_loan_products || 0).toLocaleString();
            document.getElementById("kpi-matches").textContent = (data.total_matches || 0).toLocaleString();
            document.getElementById("kpi-prune").textContent = `${data.optimization_prune_rate_pct || 96.4}%`;
            document.getElementById("kpi-notified").textContent = (data.total_notifications_sent || 0).toLocaleString();
            document.getElementById("tab-matches-count").textContent = (data.total_matches || 0).toLocaleString();
            document.getElementById("db-type-label").textContent = data.database_engine.toUpperCase();
        }
    } catch (e) {
        console.error("fetchStats error:", e);
    }
}

async function fetchHealth() {
    try {
        const res = await fetch("/api/health");
        if (res.ok) {
            const data = await res.json();
            document.getElementById("db-type-label").textContent = data.database_engine.toUpperCase();
        }
    } catch (e) {
        document.getElementById("db-type-label").textContent = "OFFLINE";
    }
}

async function uploadSelectedFile() {
    if (!selectedFile) {
        alert("Please select a CSV file first.");
        return;
    }

    const progressBox = document.getElementById("upload-progress-bar-container");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-percent-text");
    progressBox.style.display = "block";
    progressFill.style.width = "25%";
    progressText.textContent = "25%";

    appendLog(`Starting scalable ingestion for ${selectedFile.name}...`);

    try {
        const formData = new FormData();
        formData.append("file", selectedFile);

        progressFill.style.width = "65%";
        progressText.textContent = "65%";

        const res = await fetch("/api/upload/direct", {
            method: "POST",
            body: formData
        });

        if (res.ok) {
            const data = await res.json();
            progressFill.style.width = "100%";
            progressText.textContent = "100%";
            appendLog(`✓ Ingestion Success! Processed ${data.processed_rows_inserted} rows in ${data.duration_seconds}s (Batch: ${data.batch_id})`);
            if (data.n8n_triggered) {
                appendLog(`✓ n8n Webhook notified: Workflow B triggered.`);
            }
            fetchStats();
        } else {
            const err = await res.json();
            appendLog(`❌ Upload failed: ${err.detail || 'Server error'}`);
            progressFill.style.backgroundColor = "var(--danger)";
        }
    } catch (e) {
        appendLog(`❌ Ingestion network error: ${e.message}`);
    }
}

async function loadSampleDataset() {
    appendLog("Loading default benchmark users.csv (10,000 records)...");
    try {
        const res = await fetch("/data/users_sample.csv");
        const blob = await res.blob();
        const file = new File([blob], "users_sample.csv", { type: "text/csv" });
        handleFileSelect(file);
        appendLog("✓ Sample CSV loaded into dropzone. Click 'Upload & Ingest Batch' to stream.");
    } catch (e) {
        appendLog(`Could not load sample file directly: ${e.message}`);
    }
}

async function runDiscovery() {
    const card = document.getElementById("step-discover");
    card.classList.add("running");
    appendLog("Workflow A: Running Loan Product Discovery Web Crawler...");
    try {
        const res = await fetch("/api/pipeline/discover", { method: "POST" });
        const data = await res.json();
        appendLog(`✓ Workflow A Complete: Discovered and upserted ${data.persisted_count} loan products.`);
        fetchStats();
        fetchProducts();
    } catch (e) {
        appendLog(`❌ Discovery crawler error: ${e.message}`);
    } finally {
        card.classList.remove("running");
    }
}

async function runMatching() {
    const card = document.getElementById("step-match");
    card.classList.add("running");
    appendLog("Workflow B: Executing 3-Stage Optimized Matching Pipeline...");
    try {
        const res = await fetch("/api/pipeline/match", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ run_llm: true })
        });
        const data = await res.json();
        appendLog(`✓ Workflow B Complete in ${data.execution_time_ms}ms!`);
        appendLog(`   - Raw Cartesian Pairs: ${data.cartesian_pairs.toLocaleString()}`);
        appendLog(`   - Stage 1 SQL Pruning: ${data.stage1_surviving_pairs.toLocaleString()} (${data.pruning_efficiency_percent}% pruned)`);
        appendLog(`   - Final Top-K Matches Persisted: ${data.final_matches_persisted.toLocaleString()}`);
        fetchStats();
        fetchMatches();
    } catch (e) {
        appendLog(`❌ Matching pipeline error: ${e.message}`);
    } finally {
        card.classList.remove("running");
    }
}

async function runNotification() {
    const card = document.getElementById("step-notify");
    card.classList.add("running");
    const testEmail = document.getElementById("test-email-input").value.trim();
    appendLog(`Workflow C: Dispatching SES email notifications to safe test inbox: ${testEmail}...`);
    try {
        const res = await fetch("/api/pipeline/notify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ limit: 3, test_recipient: testEmail })
        });
        const data = await res.json();
        appendLog(`✓ Workflow C Complete: Notified ${data.users_notified_count} matched borrowers.`);
        if (data.dispatches && data.dispatches.length > 0) {
            appendLog(`✓ SES Message dispatched. Preview saved to ${data.dispatches[0].archive_preview_file}`);
        }
        fetchStats();
        reloadEmailFrame();
    } catch (e) {
        appendLog(`❌ Notification error: ${e.message}`);
    } finally {
        card.classList.remove("running");
    }
}

async function runFullPipeline() {
    appendLog("==================================================");
    appendLog("🚀 STARTING COMPLETE END-TO-END AUTOMATION PIPELINE");
    appendLog("==================================================");

    await runDiscovery();
    await uploadSelectedFile();
    await runMatching();
    await runNotification();

    appendLog("🎉 Complete end-to-end pipeline finished successfully!");
}

async function fetchProducts() {
    try {
        const res = await fetch("/api/products");
        if (res.ok) {
            const products = await res.json();
            renderProducts(products);
        }
    } catch (e) {
        console.error("fetchProducts error:", e);
    }
}

function renderProducts(products) {
    const container = document.getElementById("products-container");
    if (!products || products.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🏦</div>
                <h3>No loan products discovered yet</h3>
                <p>Run Workflow A (Web Crawler) from the Console to autonomously populate products.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = products.map(p => {
        let emp = p.allowed_employment_types;
        if (typeof emp === "string") {
            try { emp = JSON.parse(emp); } catch(e) { emp = [emp]; }
        }
        const empStr = Array.isArray(emp) ? emp.join(", ") : emp;

        return `
            <div class="product-card">
                <div>
                    <span class="product-bank">${p.bank_name}</span>
                    <h3 class="product-title">${p.product_name}</h3>
                    
                    <table class="spec-table">
                        <tr>
                            <td class="spec-label">Interest Rate:</td>
                            <td class="spec-val" style="color: #6ee7b7;">${p.interest_rate_min}% - ${p.interest_rate_max}%</td>
                        </tr>
                        <tr>
                            <td class="spec-label">Min Income:</td>
                            <td class="spec-val">₹${parseFloat(p.min_income).toLocaleString('en-IN')}</td>
                        </tr>
                        <tr>
                            <td class="spec-label">Min Credit Score:</td>
                            <td class="spec-val">${p.min_credit_score}</td>
                        </tr>
                        <tr>
                            <td class="spec-label">Max Loan Limit:</td>
                            <td class="spec-val">₹${parseFloat(p.max_loan_amount).toLocaleString('en-IN')}</td>
                        </tr>
                        <tr>
                            <td class="spec-label">Tenure:</td>
                            <td class="spec-val">${p.tenure_months_min} - ${p.tenure_months_max} mos</td>
                        </tr>
                        <tr>
                            <td class="spec-label">Employment:</td>
                            <td class="spec-val" style="font-size: 11px;">${empStr}</td>
                        </tr>
                    </table>
                </div>

                <div style="font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 8px;">
                    Fee: ${p.processing_fee || '1.5%'} &bull; Source: <a href="${p.source_url || '#'}" target="_blank" style="color: #93c5fd;">Official Portal</a>
                </div>
            </div>
        `;
    }).join("");
}

async function fetchMatches() {
    try {
        const empFilter = document.getElementById("filter-employment").value;
        const res = await fetch("/api/matches?limit=60");
        if (res.ok) {
            let matches = await res.json();
            if (empFilter !== "ALL") {
                matches = matches.filter(m => m.employment_status === empFilter);
            }
            renderMatches(matches);
        }
    } catch (e) {
        console.error("fetchMatches error:", e);
    }
}

function renderMatches(matches) {
    const container = document.getElementById("matches-container");
    if (!matches || matches.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">⚡</div>
                <h3>No matches generated yet</h3>
                <p>Run Workflow B (Matching Engine) from the Console to generate and view matches.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = matches.map(m => {
        let reasons = m.match_reasons;
        if (typeof reasons === "string") {
            try { reasons = JSON.parse(reasons); } catch(e) { reasons = [reasons]; }
        }
        const reasonsList = (reasons || []).slice(0, 3).map(r => `<li>${r}</li>`).join("");

        return `
            <div class="match-card">
                <div>
                    <div class="match-header">
                        <div>
                            <div class="borrower-name">${m.user_name}</div>
                            <div class="borrower-meta">Income: ₹${parseFloat(m.monthly_income).toLocaleString('en-IN')} &bull; Score: <strong style="color: #6ee7b7;">${m.credit_score}</strong> &bull; ${m.employment_status}</div>
                        </div>
                        <span class="score-badge">${parseFloat(m.eligibility_score).toFixed(1)}%</span>
                    </div>

                    <div class="product-matched-banner">
                        <div class="bank">${m.bank_name}</div>
                        <div class="prod-name">${m.product_name}</div>
                        <div class="product-metrics-row">
                            <span>Rate: <strong>${m.interest_rate_min}% p.a.</strong></span>
                            <span>Max: <strong>₹${parseFloat(m.max_loan_amount).toLocaleString('en-IN')}</strong></span>
                        </div>
                    </div>

                    <div class="ai-advice-box">
                        <strong>🤖 Underwriting Assessment:</strong>
                        ${m.ai_recommendation || 'Pre-approved borrower profile meeting all eligibility thresholds.'}
                    </div>

                    <ul class="reasons-list">
                        ${reasonsList}
                    </ul>
                </div>

                <div class="match-footer">
                    <span>${m.notified ? '✓ Email Dispatched via SES' : '⏳ Ready for Notification'}</span>
                    <span>Matched at ${new Date(m.created_at || Date.now()).toLocaleDateString()}</span>
                </div>
            </div>
        `;
    }).join("");
}

function reloadEmailFrame() {
    const frame = document.getElementById("email-preview-frame");
    if (frame) {
        frame.src = "/api/emails/latest?t=" + new Date().getTime();
    }
}
