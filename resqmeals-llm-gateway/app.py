import os
import json
import re
import requests
from flask import Flask, request, jsonify
import time
from datetime import datetime, timezone

app = Flask(__name__)

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
