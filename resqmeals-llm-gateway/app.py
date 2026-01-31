import os
import json
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

def call_groq(system: str, user: str) -> str:
    api_key = _env("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"

    body = {
        "model": os.environ.get("GROQ_MODEL", "llama3-70b-8192"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "600")),
    }

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_llm(system: str, user: str) -> str:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower().strip()
    if provider == "groq":
        return call_groq(system, user)
    raise RuntimeError("Only groq provider is enabled in this build")

def _force_json(text: str) -> str:
    """
    Best-effort. If model returns extra text, try extracting the first JSON object.
    """
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0).strip() if m else text

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/llm/extract_donation")
def extract_donation():
    payload = request.get_json(force=True)
    msg = payload.get("text", "")

    system = "You extract structured food donation details. Return ONLY valid JSON."
    user = f"""
Extract JSON with keys:
food_items: array of objects {{name, quantity, unit}}
pickup_deadline: string
pickup_address: string
notes: string
missing_fields: array of strings

Message:
{msg}
""".strip()

    out = call_llm(system, user)
    return jsonify({"json": _force_json(out)})

@app.post("/llm/rank_charities")
def rank_charities():
    payload = request.get_json(force=True)
    donation = payload.get("donation", {})
    candidates = payload.get("candidates", [])

    system = "You rank candidate charities for a food donation. Return ONLY valid JSON."
    user = f"""
Donation JSON:
{json.dumps(donation, ensure_ascii=False)}

Candidates JSON array:
{json.dumps(candidates, ensure_ascii=False)}

Return JSON:
ranked_charities: array of objects
  {{charity_id: string, score_0_100: number, reasons: [string], concerns: [string]}}
""".strip()

    out = call_llm(system, user)
    return jsonify({"json": _force_json(out)})

@app.post("/llm/draft_driver_message")
def draft_driver_message():
    payload = request.get_json(force=True)

    system = "Write a short WhatsApp-style volunteer pickup request. Keep it under 60 words."
    user = f"""
Write a concise message with:
pickup address, pickup deadline, items summary, and include this accept link: {payload.get("accept_link","")}

Data:
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    out = call_llm(system, user)
    return jsonify({"text": out.strip()})

@app.post("/llm/generate_receipt")
def generate_receipt():
    payload = request.get_json(force=True)

    system = "Generate a donation receipt. Return ONLY valid JSON."
    user = f"""
Create JSON with keys:
donor_label, receiving_org, timestamp, item_summary, disclaimer, receipt_text

Data:
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    out = call_llm(system, user)
    return jsonify({"json": _force_json(out)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
