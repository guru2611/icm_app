from dotenv import load_dotenv
load_dotenv()

import hashlib
import hmac
import json
import os
import threading
import time

import requests
from flask import Flask, Response, g, jsonify, render_template_string, request, stream_with_context

from agents.intake import parse_query
from agents.planner import plan_investigation
from agents.investigation import investigate
from dispute_predictor import get_dispute_predictions
from db.audit import log_event

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN      = os.getenv("SLACK_BOT_TOKEN", "")

app = Flask(__name__)


# ── SOX Audit Hooks ────────────────────────────────────────────────────────────

@app.before_request
def _audit_before():
    g.audit_start = time.time()
    g.actor       = request.headers.get("X-Actor", "anonymous")
    g.ip          = request.remote_addr or ""


@app.after_request
def _audit_after(response):
    # Skip the root HTML page — no compensation data is accessed.
    if request.path == "/":
        return response
    # Skip the /investigate route — it logs its own detailed event inside generate().
    if request.path == "/investigate":
        return response
    duration_ms = int((time.time() - getattr(g, "audit_start", time.time())) * 1000)
    log_event(
        actor          = getattr(g, "actor", "anonymous"),
        action         = request.endpoint or request.path.lstrip("/"),
        source         = "slack" if request.path == "/slack" else "web",
        endpoint       = request.path,
        result_status  = "success" if response.status_code < 400 else "error",
        ip_address     = getattr(g, "ip", ""),
        duration_ms    = duration_ms,
    )
    return response


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/employee/<int:employee_number>", methods=["GET"])
def employee_lookup(employee_number):
    from tools.icm_tools import get_employee_profile
    profile = get_employee_profile(employee_number)
    if profile is None:
        log_event(
            actor=g.actor, action="employee_lookup", endpoint=request.path,
            target_employee_number=employee_number, result_status="error",
            error_message="not found", ip_address=g.ip,
        )
        return jsonify({"error": "not found"}), 404
    log_event(
        actor=g.actor, action="employee_lookup", endpoint=request.path,
        target_employee_number=employee_number, result_status="success",
        ip_address=g.ip,
    )
    return jsonify({
        "name":          f"{profile['First_Name']} {profile['Last_Name']}",
        "job_code":      profile.get("Job_Code"),
        "location_name": profile.get("Location_Name"),
        "store_name":    profile.get("Store_Name"),
        "district":      profile.get("District"),
        "market":        profile.get("Market"),
        "territory":     profile.get("Territory"),
        "supervisor":    profile.get("Supervisor_Name"),
    })


@app.route("/dispute-predictor", methods=["GET"])
def dispute_predictor_route():
    try:
        result = get_dispute_predictions()
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/investigate", methods=["POST"])
def investigate_route():
    data           = request.get_json()
    employee_number = data.get("employee_number")
    query_text      = data.get("query_text", "").strip()

    if not employee_number or not query_text:
        return jsonify({"error": "employee_number and query_text are required."}), 400

    def generate():
        actor = getattr(g, "actor", "anonymous")
        ip    = getattr(g, "ip", "")
        start = time.time()
        try:
            intake = parse_query(int(employee_number), query_text)
            yield _sse({"stage": "intake", "result": intake.model_dump()})

            plan = plan_investigation(intake)
            yield _sse({"stage": "planner", "result": plan.model_dump()})

            report = investigate(plan)
            yield _sse({"stage": "investigation", "result": report.model_dump()})

            yield _sse({"stage": "done"})

            log_event(
                actor=actor, action="investigate", source="web",
                endpoint="/investigate",
                target_employee_number=int(employee_number),
                query_text=query_text,
                result_status="success",
                ip_address=ip,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as exc:
            log_event(
                actor=actor, action="investigate", source="web",
                endpoint="/investigate",
                target_employee_number=int(employee_number),
                query_text=query_text,
                result_status="error",
                error_message=str(exc),
                ip_address=ip,
                duration_ms=int((time.time() - start) * 1000),
            )
            yield _sse({"stage": "error", "error": str(exc)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Slack ──────────────────────────────────────────────────────────────────────

def _verify_slack_signature(req) -> bool:
    """Verify the request actually came from Slack."""
    if not SLACK_SIGNING_SECRET:
        return True
    ts  = req.headers.get("X-Slack-Request-Timestamp", "")
    sig = req.headers.get("X-Slack-Signature", "")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - float(ts)) > 300:
            return False
    except ValueError:
        return False
    # Use get_data(cache=True) so the body remains available for form parsing
    raw_body = req.get_data(cache=True).decode("utf-8")
    base     = f"v0:{ts}:{raw_body}"
    digest   = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(digest, sig)


def _slack_post(url: str, blocks: list, text: str):
    requests.post(url, json={"text": text, "blocks": blocks}, timeout=10)


def _confidence_emoji(conf: str) -> str:
    return {"high": ":large_green_circle:", "medium": ":large_yellow_circle:", "low": ":red_circle:"}.get(
        conf.lower(), ":white_circle:"
    )


def _format_slack_result(intake, plan, report) -> tuple[list, str]:
    """Build Slack Block Kit blocks from pipeline results."""
    qt_labels = {
        "commission_not_received":       "Commission Not Received",
        "incorrect_commission_received": "Incorrect Commission Received",
        "how_much_commission":           "How Much Commission",
        "other":                         "Other",
    }

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "ICM Investigation Complete"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Employee:*\n{intake['employee_number']}"},
            {"type": "mrkdwn", "text": f"*Query Type:*\n{qt_labels.get(intake['query_type'], intake['query_type'])}"},
            {"type": "mrkdwn", "text": f"*Sale Date:*\n{intake['sale_date'] or 'Not specified'}"},
            {"type": "mrkdwn", "text": f"*Period:*\nFY{plan['fiscal_year']} Q{plan['quarter_number']}"},
        ]},
        {"type": "divider"},
    ]

    if report["query_type"] == "other":
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": ":envelope: *Forwarded to Compensation Admin*\nThis query could not be automatically classified and has been sent for manual review."}})
        return blocks, "ICM: Forwarded to Compensation Admin"

    s    = report["summary"]
    conf = s["confidence"].lower()
    blocks += [
        {"type": "section", "text": {"type": "mrkdwn", "text": f":blue_book: *Expected*\n{s['expected']}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f":ledger: *Actual*\n{s['actual']}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f":mag: *Root Cause*\n{s['root_cause']}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: *Recommendation*\n{s['recommendation']}"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"{_confidence_emoji(conf)} Confidence: *{s['confidence'].title()}*  ·  {len(report['evidence'])} tool calls executed"}]},
    ]
    return blocks, f"ICM Investigation: {s['root_cause'][:80]}"


def _run_pipeline_and_notify(employee_number: int, query_text: str, response_url: str, actor: str, ip: str):
    start = time.time()
    try:
        intake  = parse_query(employee_number, query_text)
        plan    = plan_investigation(intake)
        report  = investigate(plan)
        blocks, text = _format_slack_result(intake.model_dump(), plan.model_dump(), report.model_dump())
        log_event(
            actor=actor, action="slack_investigate", source="slack",
            endpoint="/slack",
            target_employee_number=employee_number,
            query_text=query_text,
            result_status="success",
            ip_address=ip,
            duration_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        blocks = [{"type": "section", "text": {"type": "mrkdwn",
            "text": f":x: *Pipeline error:* {exc}"}}]
        text = f"ICM Error: {exc}"
        log_event(
            actor=actor, action="slack_investigate", source="slack",
            endpoint="/slack",
            target_employee_number=employee_number,
            query_text=query_text,
            result_status="error",
            error_message=str(exc),
            ip_address=ip,
            duration_ms=int((time.time() - start) * 1000),
        )

    _slack_post(response_url, blocks, text)


@app.route("/slack", methods=["POST"])
def slack_command():
    if not _verify_slack_signature(request):
        return jsonify({"error": "invalid signature"}), 403

    text = request.form.get("text", "").strip()
    response_url = request.form.get("response_url", "")

    # Expected format: /icm <employee_number> <query text>
    parts = text.split(None, 1)
    if len(parts) < 2 or not parts[0].isdigit():
        return jsonify({
            "response_type": "ephemeral",
            "text": "Usage: `/icm <employee_number> <query>`\nExample: `/icm 145 I never got my November commission`",
        })

    employee_number = int(parts[0])
    query_text      = parts[1]
    slack_actor     = request.form.get("user_id", "slack:unknown")

    threading.Thread(
        target=_run_pipeline_and_notify,
        args=(employee_number, query_text, response_url, slack_actor, g.ip),
        daemon=True,
    ).start()

    return jsonify({
        "response_type": "in_channel",
        "text": f":hourglass_flowing_sand: Investigating employee *{employee_number}*… results will appear here shortly.",
    })


# ── HTML ───────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ICM Investigation Pipeline</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f0f2f5;
      min-height: 100vh;
      padding: 32px 24px 64px;
      color: #111;
    }

    .page { max-width: 980px; margin: 0 auto; }

    /* ── page header ── */
    .page-header { margin-bottom: 28px; }
    .page-header h1 { font-size: 22px; font-weight: 700; }
    .page-header p  { font-size: 14px; color: #666; margin-top: 4px; }

    /* ── cards ── */
    .card {
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.07);
      padding: 28px 32px;
      margin-bottom: 20px;
    }

    /* ── input form ── */
    .form-top { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 14px; }
    .form-top .field-emp { width: 180px; flex-shrink: 0; }
    @media (max-width: 500px) { .form-top { flex-direction: column; } .form-top .field-emp { width: 100%; } }

    label { display: block; font-size: 12px; font-weight: 600; color: #555;
            text-transform: uppercase; letter-spacing: .04em; margin-bottom: 5px; }

    input[type="number"], input[type="text"], textarea {
      width: 100%; border: 1.5px solid #ddd; border-radius: 8px;
      padding: 9px 11px; font-size: 14px; color: #111; outline: none;
      transition: border-color .15s; font-family: inherit;
    }
    input[type="number"]:focus, input[type="text"]:focus, textarea:focus {
      border-color: #4f6ef7; box-shadow: 0 0 0 3px rgba(79,110,247,.12);
    }
    input[type="number"] { -moz-appearance: textfield; }
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button { -webkit-appearance: none; }
    textarea { resize: vertical; }

    .form-bottom { display: flex; gap: 12px; align-items: flex-end; }
    .form-bottom textarea { flex: 1; }

    .btn {
      padding: 10px 22px; background: #4f6ef7; color: #fff; border: none;
      border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
      transition: background .15s, opacity .15s; white-space: nowrap;
      height: 42px; flex-shrink: 0;
    }
    .btn:hover    { background: #3a58e0; }
    .btn:active   { background: #2f4bc7; }
    .btn:disabled { opacity: .5; cursor: not-allowed; }

    /* ── agent cards ── */
    .agent-card { margin-bottom: 16px; }

    .agent-header {
      display: flex; align-items: center; gap: 12px; margin-bottom: 18px;
    }
    .agent-num {
      width: 30px; height: 30px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 700; color: #fff; flex-shrink: 0;
    }
    .num-intake       { background: #7c3aed; }
    .num-planner      { background: #2563eb; }
    .num-investigation{ background: #059669; }

    .agent-meta { flex: 1; }
    .agent-name { font-size: 15px; font-weight: 600; }
    .agent-desc { font-size: 12px; color: #888; margin-top: 1px; }

    /* status badge */
    .status {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .05em; padding: 3px 10px; border-radius: 99px;
    }
    .status-pending { background: #f1f3f5; color: #aaa; }
    .status-running { background: #eff6ff; color: #2563eb; }
    .status-done    { background: #ecfdf5; color: #059669; }
    .status-error   { background: #fff1f2; color: #e11d48; }

    /* ── io grid ── */
    .io-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
    }
    @media (max-width: 640px) { .io-grid { grid-template-columns: 1fr; } }

    .io-col {}
    .io-label {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .05em; color: #888; margin-bottom: 7px;
    }

    /* generic code box */
    .io-box {
      background: #f8f9fb; border: 1px solid #e5e7eb; border-radius: 8px;
      padding: 13px 14px; min-height: 120px;
      font-family: "SF Mono", "Fira Code", Consolas, monospace;
      font-size: 12px; line-height: 1.65; white-space: pre-wrap;
      word-break: break-word; overflow-y: auto; max-height: 380px;
    }
    .io-box.placeholder { color: #bbb; font-family: inherit; font-size: 13px; }
    .io-box.error       { background: #fff5f5; border-color: #fca5a5; color: #b91c1c; }

    /* spinner inside box */
    .box-spinner {
      display: flex; align-items: center; gap: 10px;
      color: #666; font-family: inherit; font-size: 13px; padding: 8px 0;
    }
    .spin {
      width: 16px; height: 16px; border: 2px solid #d1d5db;
      border-top-color: #4f6ef7; border-radius: 50%;
      animation: spin .7s linear infinite; flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── intake output ── */
    .intake-out {}
    .intake-field { margin-bottom: 10px; }
    .intake-field:last-child { margin-bottom: 0; }
    .field-key {
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .05em; color: #888; margin-bottom: 2px;
    }
    .field-val {
      font-size: 13px; color: #111; line-height: 1.5;
    }
    .field-val code {
      background: #f0f0f5; border-radius: 4px; padding: 1px 5px;
      font-family: "SF Mono", Consolas, monospace; font-size: 12px;
      color: #4f46e5;
    }

    /* ── planner steps ── */
    .steps-list { list-style: none; }
    .step-item {
      display: grid; grid-template-columns: 22px 1fr; gap: 8px;
      margin-bottom: 10px; align-items: start;
    }
    .step-item:last-child { margin-bottom: 0; }
    .step-num {
      width: 20px; height: 20px; border-radius: 50%; background: #e0e7ff;
      color: #3730a3; font-size: 10px; font-weight: 700;
      display: flex; align-items: center; justify-content: center; flex-shrink: 0;
      margin-top: 1px;
    }
    .step-body {}
    .step-tool {
      font-family: "SF Mono", Consolas, monospace; font-size: 11px;
      font-weight: 600; color: #2563eb; background: #eff6ff;
      border-radius: 4px; padding: 1px 6px; display: inline-block; margin-bottom: 3px;
    }
    .step-desc { font-size: 12px; color: #555; line-height: 1.45; }
    .step-args {
      font-family: "SF Mono", Consolas, monospace; font-size: 11px;
      color: #888; margin-top: 2px; white-space: pre-wrap;
    }

    /* ── evidence list ── */
    .evidence-list { list-style: none; }
    .evidence-item {
      display: flex; align-items: baseline; gap: 8px;
      padding: 4px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px;
    }
    .evidence-item:last-child { border-bottom: none; }
    .ev-step {
      font-size: 10px; color: #aaa; font-weight: 600; width: 18px; flex-shrink: 0;
    }
    .ev-tool {
      font-family: "SF Mono", Consolas, monospace; font-size: 11px; color: #374151; flex: 1;
    }
    .ev-ok    { color: #059669; font-size: 11px; font-weight: 600; }
    .ev-error { color: #dc2626; font-size: 11px; font-weight: 600; }

    /* ── forensic summary ── */
    .forensic { font-family: inherit; }
    .fs-field { margin-bottom: 14px; }
    .fs-field:last-of-type { margin-bottom: 10px; }
    .fs-key {
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .06em; margin-bottom: 3px;
    }
    .fs-key.key-expected   { color: #2563eb; }
    .fs-key.key-actual     { color: #d97706; }
    .fs-key.key-root-cause { color: #dc2626; }
    .fs-key.key-recommend  { color: #059669; }
    .fs-val { font-size: 13px; color: #222; line-height: 1.55; }
    .fs-confidence {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .05em; padding: 3px 10px; border-radius: 99px;
      margin-top: 4px;
    }
    .conf-high   { background: #ecfdf5; color: #065f46; }
    .conf-medium { background: #fffbeb; color: #92400e; }
    .conf-low    { background: #fff1f2; color: #9f1239; }

    /* intake input box sizes to content, no forced min-height */
    #intake-in { min-height: 0; }

    /* ── "other" forwarding notice ── */
    .other-notice {
      background: #fffbeb; border: 1.5px solid #fbbf24; border-radius: 8px;
      padding: 18px 20px;
    }
    .other-notice-title {
      font-size: 14px; font-weight: 700; color: #92400e; margin-bottom: 6px;
    }
    .other-notice-text {
      font-size: 13px; color: #78350f; line-height: 1.55;
    }

    /* ── arrow connector ── */
    .connector {
      display: flex; align-items: center; justify-content: center;
      height: 20px; margin: -8px 0;
    }
    .connector svg { color: #d1d5db; }
  </style>
</head>
<body>
<div class="page">

  <div class="page-header">
    <h1>ICM Investigation Pipeline</h1>
    <p>Enter an employee number and their compensation query to run the full three-stage investigation.</p>
  </div>

  <!-- Input form -->
  <div class="card">
    <div class="form-top">
      <div class="field-emp">
        <label for="emp">Employee Number</label>
        <input type="number" id="emp" placeholder="e.g. 145" min="1" />
      </div>
    </div>
    <div class="form-bottom">
      <div style="flex:1;">
        <label for="query">Query</label>
        <textarea id="query" rows="3"
          placeholder="e.g. I made a sale in November 2024 but never received my commission."></textarea>
      </div>
      <button class="btn" id="run-btn" onclick="runPipeline()">Investigate &rarr;</button>
    </div>
  </div>

  <!-- Pipeline -->
  <div id="pipeline" style="display:none;">

    <!-- 1. Intake Agent -->
    <div class="card agent-card" id="card-intake">
      <div class="agent-header">
        <div class="agent-num num-intake">1</div>
        <div class="agent-meta">
          <div class="agent-name">Intake Agent</div>
          <div class="agent-desc">Parses free-text query into a structured IntakeResult</div>
        </div>
        <span class="status status-pending" id="status-intake">Waiting</span>
      </div>
      <div class="io-grid">
        <div class="io-col">
          <div class="io-label">Input</div>
          <div class="io-box" id="intake-in"></div>
        </div>
        <div class="io-col">
          <div class="io-label">Output &mdash; IntakeResult</div>
          <div class="io-box placeholder" id="intake-out">Waiting for agent&hellip;</div>
        </div>
      </div>
    </div>

    <div class="connector">
      <svg width="16" height="20" viewBox="0 0 16 20" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="8" y1="0" x2="8" y2="14"/><polyline points="4,10 8,16 12,10"/>
      </svg>
    </div>

    <!-- 2. Planner Agent -->
    <div class="card agent-card" id="card-planner">
      <div class="agent-header">
        <div class="agent-num num-planner">2</div>
        <div class="agent-meta">
          <div class="agent-name">Planner Agent</div>
          <div class="agent-desc">Routes by query type and produces an ordered list of tool calls</div>
        </div>
        <span class="status status-pending" id="status-planner">Waiting</span>
      </div>
      <div class="io-grid">
        <div class="io-col">
          <div class="io-label">Input &mdash; IntakeResult</div>
          <div class="io-box placeholder" id="planner-in">Waiting for intake agent&hellip;</div>
        </div>
        <div class="io-col">
          <div class="io-label">Output &mdash; Investigation Plan</div>
          <div class="io-box placeholder" id="planner-out">Waiting for agent&hellip;</div>
        </div>
      </div>
    </div>

    <div class="connector">
      <svg width="16" height="20" viewBox="0 0 16 20" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="8" y1="0" x2="8" y2="14"/><polyline points="4,10 8,16 12,10"/>
      </svg>
    </div>

    <!-- 3. Investigation Agent -->
    <div class="card agent-card" id="card-investigation">
      <div class="agent-header">
        <div class="agent-num num-investigation">3</div>
        <div class="agent-meta">
          <div class="agent-name">Investigation Agent</div>
          <div class="agent-desc">Executes each tool call against BigQuery and synthesises a forensic report</div>
        </div>
        <span class="status status-pending" id="status-investigation">Waiting</span>
      </div>
      <div class="io-grid">
        <div class="io-col">
          <div class="io-label">Input &mdash; Plan Steps Executed</div>
          <div class="io-box placeholder" id="investigation-in">Waiting for planner agent&hellip;</div>
        </div>
        <div class="io-col">
          <div class="io-label">Output &mdash; Forensic Summary</div>
          <div class="io-box placeholder" id="investigation-out">Waiting for agent&hellip;</div>
        </div>
      </div>
    </div>

  </div><!-- /pipeline -->
</div><!-- /page -->

<script>
  // ── Helpers ────────────────────────────────────────────────────────────────

  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function setStatus(agent, state) {
    const el = document.getElementById("status-" + agent);
    const map = {
      pending: ["status-pending", "Waiting"],
      running: ["status-running", "Running"],
      done:    ["status-done",    "Done"],
      error:   ["status-error",   "Error"],
    };
    el.className = "status " + map[state][0];
    el.textContent = map[state][1];
    if (state === "running") {
      el.innerHTML = '<span class="spin" style="display:inline-block;width:10px;height:10px;border-width:1.5px;margin-right:5px;vertical-align:middle;"></span>' + map[state][1];
    }
  }

  function spinner(msg) {
    return `<div class="box-spinner"><div class="spin"></div>${esc(msg)}</div>`;
  }

  // ── Renderers ──────────────────────────────────────────────────────────────

  function renderIntakeInput(emp, query) {
    const box = document.getElementById("intake-in");
    box.className = "io-box intake-out";
    box.innerHTML = `
      <div class="intake-field">
        <div class="field-key">Employee Number</div>
        <div class="field-val"><code>${esc(emp)}</code></div>
      </div>
      <div class="intake-field">
        <div class="field-key">Query Text</div>
        <div class="field-val">${esc(query)}</div>
      </div>`;
  }

  function renderIntakeOutput(result) {
    const box = document.getElementById("intake-out");
    box.className = "io-box intake-out";

    const qtLabels = {
      commission_not_received:      "Commission Not Received",
      incorrect_commission_received:"Incorrect Commission Received",
      how_much_commission:          "How Much Commission",
      other:                        "Other",
    };

    box.innerHTML = `
      <div class="intake-field">
        <div class="field-key">Query Type</div>
        <div class="field-val"><code>${esc(qtLabels[result.query_type] || result.query_type)}</code></div>
      </div>
      <div class="intake-field">
        <div class="field-key">Sale Date</div>
        <div class="field-val"><code>${esc(result.sale_date || "not specified")}</code></div>
      </div>
      <div class="intake-field">
        <div class="field-key">Summary</div>
        <div class="field-val">${esc(result.summary)}</div>
      </div>`;
  }

  function renderPlannerInput(intakeResult) {
    const box = document.getElementById("planner-in");
    box.className = "io-box intake-out";
    box.innerHTML = `
      <div class="intake-field">
        <div class="field-key">Employee Number</div>
        <div class="field-val"><code>${esc(intakeResult.employee_number)}</code></div>
      </div>
      <div class="intake-field">
        <div class="field-key">Query Type</div>
        <div class="field-val"><code>${esc(intakeResult.query_type)}</code></div>
      </div>
      <div class="intake-field">
        <div class="field-key">Sale Date</div>
        <div class="field-val"><code>${esc(intakeResult.sale_date || "not specified")}</code></div>
      </div>
      <div class="intake-field">
        <div class="field-key">Summary</div>
        <div class="field-val">${esc(intakeResult.summary)}</div>
      </div>`;
  }

  function renderPlannerOutput(plan) {
    const box = document.getElementById("planner-out");
    box.className = "io-box";
    box.style.fontFamily = "inherit";

    const header = `<div style="font-size:12px;color:#666;margin-bottom:12px;">
      FY${esc(plan.fiscal_year)} Q${esc(plan.quarter_number)} &nbsp;&middot;&nbsp; ${plan.steps.length} steps
    </div>`;

    const items = plan.steps.map(s => `
      <li class="step-item">
        <div class="step-num">${esc(s.step)}</div>
        <div class="step-body">
          <span class="step-tool">${esc(s.tool)}</span>
          <div class="step-desc">${esc(s.description)}</div>
          <div class="step-args">${esc(JSON.stringify(s.args))}</div>
        </div>
      </li>`).join("");

    box.innerHTML = header + `<ul class="steps-list">${items}</ul>`;
  }

  function renderInvestigationInput(report) {
    const box = document.getElementById("investigation-in");
    box.className = "io-box";
    box.style.fontFamily = "inherit";

    const items = report.evidence.map(ev => {
      const ok = ev.error == null;
      return `<li class="evidence-item">
        <span class="ev-step">${esc(ev.step)}</span>
        <span class="ev-tool">${esc(ev.tool)}</span>
        <span class="${ok ? "ev-ok" : "ev-error"}">${ok ? "OK" : "ERR"}</span>
      </li>`;
    }).join("");

    box.innerHTML = `<ul class="evidence-list">${items}</ul>`;
  }

  function renderInvestigationOutput(report) {
    const box = document.getElementById("investigation-out");
    box.className = "io-box";
    box.style.fontFamily = "inherit";

    if (report.query_type === "other") {
      box.className = "other-notice";
      box.innerHTML = `
        <div class="other-notice-title">Forwarded to Compensation Admin</div>
        <div class="other-notice-text">
          This query could not be automatically classified into a known investigation type.
          It has been forwarded to the Compensation Administration team for manual review and analysis.
        </div>`;
      return;
    }

    const s    = report.summary;
    const conf = s.confidence.toLowerCase();
    const confLabel = { high: "High", medium: "Medium", low: "Low" }[conf] || s.confidence;

    box.innerHTML = `
      <div class="forensic">
        <div class="fs-field">
          <div class="fs-key key-expected">Expected</div>
          <div class="fs-val">${esc(s.expected)}</div>
        </div>
        <div class="fs-field">
          <div class="fs-key key-actual">Actual</div>
          <div class="fs-val">${esc(s.actual)}</div>
        </div>
        <div class="fs-field">
          <div class="fs-key key-root-cause">Root Cause</div>
          <div class="fs-val">${esc(s.root_cause)}</div>
        </div>
        <div class="fs-field">
          <div class="fs-key key-recommend">Recommendation</div>
          <div class="fs-val">${esc(s.recommendation)}</div>
        </div>
        <span class="fs-confidence conf-${conf}">Confidence: ${esc(confLabel)}</span>
      </div>`;
  }

  // ── Pipeline runner ────────────────────────────────────────────────────────

  async function runPipeline() {
    const emp   = document.getElementById("emp").value.trim();
    const query = document.getElementById("query").value.trim();
    const btn   = document.getElementById("run-btn");

    if (!emp || !query) {
      alert("Please fill in both fields.");
      return;
    }

    // Reset UI
    document.getElementById("pipeline").style.display = "block";
    btn.disabled = true;
    btn.textContent = "Running…";

    ["intake", "planner", "investigation"].forEach(a => setStatus(a, "pending"));

    renderIntakeInput(emp, query);

    document.getElementById("intake-out").className = "io-box placeholder";
    document.getElementById("intake-out").innerHTML = spinner("Calling intake agent…");

    document.getElementById("planner-in").className  = "io-box placeholder";
    document.getElementById("planner-in").textContent = "Waiting for intake agent…";
    document.getElementById("planner-out").className  = "io-box placeholder";
    document.getElementById("planner-out").textContent = "Waiting for agent…";

    document.getElementById("investigation-in").className  = "io-box placeholder";
    document.getElementById("investigation-in").textContent = "Waiting for planner agent…";
    document.getElementById("investigation-out").className  = "io-box placeholder";
    document.getElementById("investigation-out").textContent = "Waiting for agent…";

    setStatus("intake", "running");

    let intakeResult = null;

    try {
      const response = await fetch("/investigate", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ employee_number: parseInt(emp), query_text: query }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || "Server error");
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE lines
        const lines = buffer.split("\\n");
        buffer = lines.pop();          // keep the incomplete trailing chunk

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.stage === "intake") {
            intakeResult = event.result;
            renderIntakeOutput(event.result);
            setStatus("intake", "done");
            setStatus("planner", "running");
            document.getElementById("planner-in").innerHTML  = spinner("Calling planner agent…");
            document.getElementById("planner-out").innerHTML = spinner("Building investigation plan…");
          }

          else if (event.stage === "planner") {
            renderPlannerInput(intakeResult);
            renderPlannerOutput(event.result);
            setStatus("planner", "done");
            setStatus("investigation", "running");
            document.getElementById("investigation-in").innerHTML  = spinner("Executing tool calls…");
            document.getElementById("investigation-out").innerHTML = spinner("Synthesising forensic report…");
          }

          else if (event.stage === "investigation") {
            renderInvestigationInput(event.result);
            renderInvestigationOutput(event.result);
            setStatus("investigation", "done");
          }

          else if (event.stage === "error") {
            throw new Error(event.error);
          }
        }
      }
    } catch (err) {
      ["intake","planner","investigation"].forEach(a => {
        const s = document.getElementById("status-" + a);
        if (s.classList.contains("status-running")) setStatus(a, "error");
      });
      const errBoxes = ["intake-out","planner-out","investigation-out"];
      errBoxes.forEach(id => {
        const box = document.getElementById(id);
        if (box.classList.contains("placeholder") || box.innerHTML.includes("spin")) {
          box.className = "io-box error";
          box.textContent = "Error: " + err.message;
        }
      });
    } finally {
      btn.disabled    = false;
      btn.textContent = "Investigate →";
    }
  }

  // Ctrl+Enter from query field
  document.getElementById("query").addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runPipeline();
  });
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
