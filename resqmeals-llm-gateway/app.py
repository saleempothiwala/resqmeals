import os
import json
import re
import requests
from flask import Flask, request, jsonify
import time
from datetime import datetime, timezone

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.get("/__routes")
def __routes():
    return jsonify(sorted([rule.rule for rule in app.url_map.iter_rules()]))


def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v



IAM_URL = "https://iam.cloud.ibm.com/identity/token"
_cloudant_token = {"value": None, "exp": 0}

def cloudant_token() -> str:
    now = int(time.time())
    if _cloudant_token["value"] and now < _cloudant_token["exp"] - 60:
        return _cloudant_token["value"]

    r = requests.post(
        IAM_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": _env("CLOUDANT_APIKEY"),
        },
        timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    _cloudant_token["value"] = j["access_token"]
    _cloudant_token["exp"] = j["expiration"]
    return _cloudant_token["value"]

def cloudant_request(method: str, path: str, json_body=None, params=None):
    base = _env("CLOUDANT_URL").rstrip("/")
    token = cloudant_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{base}/{path.lstrip('/')}"
    resp = requests.request(method, url, headers=headers, json=json_body, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json() if resp.text else {}

def cloudant_find(db: str, selector: dict, limit: int = 20, fields=None):
    body = {"selector": selector, "limit": limit}
    if fields:
        body["fields"] = fields
    return cloudant_request("POST", f"{db}/_find", json_body=body)

def cloudant_get(db: str, doc_id: str):
    return cloudant_request("GET", f"{db}/{doc_id}")

def cloudant_put(db: str, doc: dict):
    if "_id" not in doc:
        raise RuntimeError("document missing _id")
    return cloudant_request("PUT", f"{db}/{doc['_id']}", json_body=doc)


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

@app.route("/llm/rank_charities", methods=["POST"])
def rank_charities():
    data = request.get_json(force=True)
    donation = data.get("donation")
    candidates = data.get("candidates", [])

    system = "You are a dispatch assistant that ranks charities for food rescue."
    user = f"""
Rank these candidate charities for the donation below.

Donation (JSON):
{json.dumps(donation, ensure_ascii=False)}

Candidates (JSON list):
{json.dumps(candidates, ensure_ascii=False)}

Return JSON only with this schema:

{{
  "ranked": [
    {{"id":"<candidate _id>","name":"<candidate name>","score":0.0,"reason":"short reason"}}
  ]
}}

Rules:
- Prefer charities that accept the food type.
- Prefer larger max_radius_miles.
- Prefer charities whose hours are open at pickup_deadline if hours exist.
- Keep reason under 20 words.
"""

    raw = call_llm(system, user)

    # Normalize output. Always return {"ranked":[...]} even if model misbehaves.
    def _coerce(obj):
        if isinstance(obj, str):
            obj = obj.strip()
            obj = json.loads(obj)

        if isinstance(obj, dict) and "ranked" not in obj:
            if "json" in obj:
                return _coerce(obj["json"])
            if "text" in obj:
                return _coerce(obj["text"])

        if isinstance(obj, dict) and "ranked" in obj and isinstance(obj["ranked"], list):
            return obj

        raise ValueError("rank_charities: bad format")

    def _fallback():
        ranked = []
        for c in candidates:
            ranked.append({
                "id": c.get("_id"),
                "name": c.get("name"),
                "score": 1.0,
                "reason": "Fallback ranking"
            })
        return {"ranked": ranked}

    try:
        out = _coerce(raw)
        if not out.get("ranked"):
            out = _fallback()
        return jsonify(out)
    except Exception:
        return jsonify(_fallback())


@app.post("/llm/draft_driver_message")
def draft_driver_message():
    payload = request.get_json(force=True)

    system = "Write a short WhatsApp-style volunteer pickup message. Do not preface with meta text like 'this is your pickup message'. Keep it under 40 words."
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
receipt_id, donor_label, receiving_org, timestamp, item_summary, pickup_address, pickup_deadline, disclaimer, receipt_text

Data:
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    out = call_llm(system, user)
    obj, txt = _safe_parse_json(out)

    return jsonify({
        "data": obj,
        "json_text": txt
    })





def _safe_parse_json(text: str):
    t = _force_json(text)
    try:
        return json.loads(t), t
    except Exception:
        return None, t

@app.get("/audit/recent")
def audit_recent():
    db = os.environ.get("CLOUDANT_DB_AUDIT", "resqmeals_audit")
    limit = int(request.args.get("limit", "20"))

    # Find all audit docs. For small demo dataset this is fine.
    # If you want sorting by created_at later, add an index and sort fields.
    out = cloudant_find(
        db,
        {"type": "audit"},
        limit=limit,
        fields=["_id","created_at","restaurant_id","status","restaurant_message","selected_charity","selected_driver"]
    )
    return jsonify(out)


@app.get("/data/charities")
def charities():
    db = os.environ.get("CLOUDANT_DB_CHARITIES", "resqmeals_charities")
    accepts = request.args.get("accepts")  # comma separated
    sel = {"type": "charity"}

    if accepts:
        vals = [v.strip() for v in accepts.split(",") if v.strip()]
        sel["accepts"] = {"$in": vals}

    out = cloudant_find(
        db,
        sel,
        limit=50,
        fields=["_id","name","accepts","max_radius_miles","address","hours","capacity_notes","geo"]
    )
    return jsonify(out)


@app.get("/data/drivers")
def drivers():
    db = os.environ.get("CLOUDANT_DB_DRIVERS", "resqmeals_drivers")
    status = request.args.get("status", "available")
    sel = {"type": "driver", "status": status}
    out = cloudant_find(db, sel, limit=50, fields=["_id","name","status","max_radius_miles","vehicle","channels","rating","geo"])
    return jsonify(out)

@app.get("/data/restaurants")
def restaurants():
    db = os.environ.get("CLOUDANT_DB_RESTAURANTS", "resqmeals_restaurants")
    out = cloudant_find(db, {"type": "restaurant"}, limit=50, fields=["_id","name","address","geo","contact"])
    return jsonify(out)

@app.get("/data/doc")
def get_doc():
    db = request.args.get("db")
    doc_id = request.args.get("id")
    if not db or not doc_id:
        return jsonify({"error":"missing db or id"}), 400
    return jsonify(cloudant_get(db, doc_id))

@app.post("/audit/log")
def audit_log():
    payload = request.get_json(force=True)
    db = os.environ.get("CLOUDANT_DB_AUDIT", "resqmeals_audit")

    ts = datetime.now(timezone.utc).isoformat()
    restaurant_id = payload.get("restaurant_id", "unknown")

    doc = {
        "_id": f"audit:{ts}:{restaurant_id}",
        "type": "audit",
        "created_at": ts,
        **payload
    }

    out = cloudant_put(db, doc)
    return jsonify(out)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
