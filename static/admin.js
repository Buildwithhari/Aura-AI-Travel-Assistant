const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

function metric(label, value, hint) {
    return `<article class="metric"><div class="label">${label}</div><div class="value">${value}</div><div class="hint">${hint}</div></article>`;
}

function renderBars(target, items) {
    const max = Math.max(...items.map((item) => item.count), 1);
    $(target).innerHTML = items.length ? items.map((item) => `
        <div class="bar-row">
            <span title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${item.count / max * 100}%"></div></div>
            <span class="bar-value">${item.count}</span>
        </div>`).join("") : `<p>No interaction data yet. Use the chatbot first.</p>`;
}

async function loadMetrics() {
    const data = await fetch("/api/admin/metrics").then((response) => response.json());
    const summary = data.summary;
    $("#summary").innerHTML = [
        metric("Interactions", summary.total_interactions, `${summary.unique_sessions} unique sessions`),
        metric("Average confidence", `${Math.round(summary.average_confidence * 100)}%`, `${summary.fallback_rate}% fallback rate`),
        metric("Average latency", `${summary.average_response_ms} ms`, `p95 ${summary.p95_response_ms} ms`),
        metric("RAG usage", `${summary.rag_usage_rate}%`, `${summary.positive_feedback_rate}% positive feedback`),
    ].join("");
    renderBars("#intent-chart", data.intents);
    renderBars("#source-chart", data.sources);
    renderBars("#language-chart", data.languages);
}

async function loadRecent() {
    const data = await fetch("/api/admin/recent?limit=50").then((response) => response.json());
    $("#recent-body").innerHTML = data.items.length ? data.items.map((item) => `
        <tr>
            <td>${new Date(item.created_at).toLocaleString()}</td>
            <td class="message" title="${escapeHtml(item.message)}">${escapeHtml(item.message)}</td>
            <td><span class="pill">${escapeHtml(item.intent)}</span></td>
            <td>${escapeHtml(item.source)}</td>
            <td>${Math.round((item.confidence || 0) * 100)}%</td>
            <td>${item.response_ms} ms</td>
            <td class="${item.rag_used ? "good" : "muted"}">${item.rag_used ? `Yes (${Math.round(item.rag_score * 100)}%)` : "No"}</td>
            <td>${item.feedback === 1 ? "👍" : item.feedback === -1 ? "👎" : "—"}</td>
        </tr>`).join("") : `<tr><td colspan="8" class="muted">No interactions recorded yet.</td></tr>`;
}

async function runEvaluation() {
    const button = $("#evaluate-btn");
    button.disabled = true;
    button.textContent = "Evaluating…";
    try {
        const result = await fetch("/api/admin/evaluate", { method: "POST" }).then((response) => response.json());
        $("#evaluation-panel").classList.remove("hidden");
        $("#evaluation-time").textContent = `Completed ${new Date().toLocaleTimeString()}`;
        $("#evaluation-summary").innerHTML = `
            <div class="evaluation-card"><span>Intent classification accuracy</span><strong>${Math.round(result.intent.accuracy * 100)}%</strong><small>${result.intent.passed}/${result.intent.total} cases passed</small></div>
            <div class="evaluation-card"><span>RAG top-1 retrieval accuracy</span><strong>${Math.round(result.rag.top_1_accuracy * 100)}%</strong><small>MRR ${result.rag.mean_reciprocal_rank} · ${result.rag.passed}/${result.rag.total} passed</small></div>`;
        const failures = [
            ...result.intent.details.filter((item) => !item.passed).map((item) => `Intent: “${escapeHtml(item.text)}” expected ${escapeHtml(item.expected)}, got ${escapeHtml(item.predicted)}`),
            ...result.rag.details.filter((item) => !item.passed).map((item) => `RAG: “${escapeHtml(item.text)}” expected ${escapeHtml(item.expected_id)}, got ${escapeHtml(item.retrieved[0])}`),
        ];
        $("#evaluation-details").innerHTML = failures.length ? `<div class="fail-list"><b>Failed cases</b><br>${failures.join("<br>")}</div>` : `<p class="good">All evaluation cases passed.</p>`;
    } catch (error) {
        $("#evaluation-panel").classList.remove("hidden");
        $("#evaluation-details").innerHTML = `<p class="bad">Evaluation failed. Check the server console.</p>`;
    } finally {
        button.disabled = false;
        button.textContent = "Run Evaluation";
    }
}

$("#evaluate-btn").addEventListener("click", runEvaluation);
$("#refresh-btn").addEventListener("click", () => Promise.all([loadMetrics(), loadRecent()]));
Promise.all([loadMetrics(), loadRecent()]).catch(() => { $("#live-status").textContent = "Dashboard unavailable"; });
setInterval(() => { loadMetrics(); loadRecent(); }, 15000);
