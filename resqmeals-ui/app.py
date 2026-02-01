UI_VERSION = "2026-02-01-ui-v2"


import json
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

# Set this to your gateway URL.
GATEWAY_URL = os.environ.get(
    "GATEWAY_URL",
    "https://resqmeals-llm-gateway.25rqfbmcob70.br-sao.codeengine.appdomain.cloud",
).rstrip("/")

DEFAULT_ACCEPTS = os.environ.get("DEFAULT_ACCEPTS", "hot_prepared_food")
DEFAULT_RESTAURANT_ID = os.environ.get("DEFAULT_RESTAURANT_ID", "restaurant:pasta-palace")
DEFAULT_ACCEPT_LINK = os.environ.get("DEFAULT_ACCEPT_LINK", "https://resqmeals.app/accept/demo")


# ----------------------------
# Helpers
# ----------------------------
def _raise_for_status_with_body(r: requests.Response) -> None:
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        body = ""
        try:
            body = r.text
        except Exception:
            pass
        raise RuntimeError(f"HTTP {r.status_code} calling {r.url}. Body: {body}") from e


def _safe_json(r: requests.Response) -> Dict[str, Any]:
    _raise_for_status_with_body(r)
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Non-JSON response from {r.url}. Body: {r.text}") from e


def _parse_json_maybe(value: Any) -> Any:
    """
    If value is a JSON string, parse it. Otherwise return as-is.
    """
    if isinstance(value, str):
        s = value.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:
                return value
    return value


def _normalize_rank_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts several shapes and normalizes to: {"ranked":[...]}.
    """
    if "ranked" in resp and isinstance(resp["ranked"], list):
        return resp

    # Some endpoints return nested JSON strings under json/json_text/text/data
    for key in ["json", "json_text", "text", "data"]:
        if key in resp:
            candidate = _parse_json_maybe(resp[key])
            if isinstance(candidate, dict) and "ranked" in candidate:
                return candidate

    raise KeyError(f"rank_charities response missing ranked. Keys: {list(resp.keys())}")


def _lookup_full_doc_by_id(docs: List[Dict[str, Any]], doc_id: str) -> Optional[Dict[str, Any]]:
    for d in docs:
        if d.get("_id") == doc_id:
            return d
    return None


def _format_items_summary(donation_obj: Dict[str, Any]) -> str:
    items = donation_obj.get("food_items") or []
    if not items:
        return "Food donation"
    parts = []
    for it in items:
        qty = it.get("quantity")
        unit = it.get("unit") or ""
        name = it.get("name") or "item"
        if qty is None:
            parts.append(f"{name}")
        else:
            parts.append(f"{qty} {unit} {name}".strip())
    return ", ".join(parts)


# ----------------------------
# Gateway calls
# ----------------------------
def extract_donation(message: str) -> Dict[str, Any]:
    r = requests.post(f"{GATEWAY_URL}/llm/extract_donation", json={"text": message}, timeout=60)
    j = _safe_json(r)
    donation = _parse_json_maybe(j.get("json"))
    if not isinstance(donation, dict):
        raise RuntimeError(f"extract_donation returned unexpected payload: {j}")
    return donation


def get_charities(accepts: str) -> List[Dict[str, Any]]:
    r = requests.get(f"{GATEWAY_URL}/data/charities", params={"accepts": accepts}, timeout=30)
    j = _safe_json(r)
    docs = j.get("docs", [])
    if not isinstance(docs, list):
        raise RuntimeError(f"data/charities returned unexpected payload: {j}")
    return docs


def rank_charities(donation_obj: Dict[str, Any], charities: List[Dict[str, Any]]) -> Dict[str, Any]:
    r = requests.post(
        f"{GATEWAY_URL}/llm/rank_charities",
        json={"donation": donation_obj, "candidates": charities},
        timeout=60,
    )
    j = _safe_json(r)
    return _normalize_rank_response(j)


def get_available_drivers() -> List[Dict[str, Any]]:
    r = requests.get(f"{GATEWAY_URL}/data/drivers", params={"status": "available"}, timeout=30)
    j = _safe_json(r)
    docs = j.get("docs", [])
    if not isinstance(docs, list):
        raise RuntimeError(f"data/drivers returned unexpected payload: {j}")
    return docs


def draft_driver_message(pickup: str, time_str: str, items_summary: str, accept_link: str) -> str:
    r = requests.post(
        f"{GATEWAY_URL}/llm/draft_driver_message",
        json={
            "pickup": pickup,
            "time": time_str,
            "items_summary": items_summary,
            "accept_link": accept_link,
        },
        timeout=60,
    )
    j = _safe_json(r)
    text = j.get("text")
    if not isinstance(text, str):
        raise RuntimeError(f"draft_driver_message returned unexpected payload: {j}")
    return text.strip()


def generate_receipt(
    restaurant_id: str,
    charity_doc: Dict[str, Any],
    donation_obj: Dict[str, Any],
    pickup_address: str,
    pickup_deadline: str,
) -> Dict[str, Any]:
    r = requests.post(
        f"{GATEWAY_URL}/llm/generate_receipt",
        json={
            "restaurant_id": restaurant_id,
            "charity": {"id": charity_doc.get("_id"), "name": charity_doc.get("name")},
            "items": donation_obj,
            "pickup_address": pickup_address,
            "pickup_deadline": pickup_deadline,
        },
        timeout=60,
    )
    j = _safe_json(r)

    # Your gateway returns {"data": obj, "json_text": "..."}.
    if isinstance(j.get("data"), dict):
        return j["data"]

    parsed = _parse_json_maybe(j.get("json_text"))
    if isinstance(parsed, dict):
        return parsed

    # Fallback: return whatever we got
    return j

def get_audit_recent(limit: int = 20) -> List[Dict[str, Any]]:
    r = requests.get(f"{GATEWAY_URL}/audit/recent", params={"limit": limit}, timeout=30)
    j = _safe_json(r)
    docs = j.get("docs", [])
    if not isinstance(docs, list):
        raise RuntimeError(f"audit/recent returned unexpected payload: {j}")
    return docs


def _to_map_points(
    charities: List[Dict[str, Any]],
    drivers: List[Dict[str, Any]],
    selected_charity_id: Optional[str] = None,
    selected_driver_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    pts: List[Dict[str, Any]] = []

    for c in charities:
        geo = c.get("geo") or {}
        lat, lon = geo.get("lat"), geo.get("lon")
        if lat is None or lon is None:
            continue
        pts.append({
            "lat": float(lat),
            "lon": float(lon),
            "label": c.get("name", "Charity"),
            "type": "charity_selected" if c.get("_id") == selected_charity_id else "charity",
        })

    for d in drivers:
        geo = d.get("geo") or {}
        lat, lon = geo.get("lat"), geo.get("lon")
        if lat is None or lon is None:
            continue
        pts.append({
            "lat": float(lat),
            "lon": float(lon),
            "label": d.get("name", "Driver"),
            "type": "driver_selected" if d.get("_id") == selected_driver_id else "driver",
        })

    return pts

def write_audit(
    restaurant_id: str,
    restaurant_message: str,
    donation_obj: Dict[str, Any],
    selected_charity: Dict[str, Any],
    selected_driver: Dict[str, Any],
    driver_message: str,
    receipt_obj: Dict[str, Any],
) -> str:
    r = requests.post(
        f"{GATEWAY_URL}/audit/log",
        json={
            "restaurant_id": restaurant_id,
            "restaurant_message": restaurant_message,
            "extracted": donation_obj,
            "selected_charity": selected_charity,
            "selected_driver": selected_driver,
            "driver_message": driver_message,
            "receipt": receipt_obj,
            "status": "dispatched",
        },
        timeout=30,
    )
    j = _safe_json(r)
    audit_id = j.get("id")
    if not isinstance(audit_id, str):
        raise RuntimeError(f"audit/log returned unexpected payload: {j}")
    return audit_id


# ----------------------------
# Streamlit UI
# ----------------------------
st.sidebar.success(f"UI: {UI_VERSION}")

st.set_page_config(page_title="ResQMeals Control Panel", layout="centered")
st.title("🍽️ ResQMeals Dispatch Center")
st.caption("Connect surplus food with nearby charities and drivers")

status_cols = st.columns(3)
with status_cols[0]:
    st.sidebar.success(f"UI: {UI_VERSION}")
with status_cols[1]:
    st.link_button("Gateway health", f"{GATEWAY_URL}/health")
with status_cols[2]:
    st.link_button("Gateway routes", f"{GATEWAY_URL}/__routes")

with st.expander("Settings", expanded=False):
    st.text_input("Gateway URL", value=GATEWAY_URL, disabled=True)
    accepts = st.text_input("Food category filter (accepts)", value=DEFAULT_ACCEPTS)
    restaurant_id = st.text_input("Restaurant ID", value=DEFAULT_RESTAURANT_ID)
    accept_link = st.text_input("Driver accept link (demo)", value=DEFAULT_ACCEPT_LINK)

tab_dispatch, tab_history, tab_map = st.tabs(["Dispatch", "History", "Map"])

tab_dispatch, tab_history, tab_map = st.tabs(["Dispatch", "History", "Map"])

with tab_dispatch:
    message = st.text_area(
        "Restaurant Message",
        placeholder="I have 20 trays of pasta left. Pickup by 10 PM at 45 Park Street.",
        height=120,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        dispatch = st.button("🚀 Dispatch Donation", use_container_width=True)
    with col2:
        st.link_button("Open Gateway Health", f"{GATEWAY_URL}/health", use_container_width=True)

    if dispatch:
        if not message.strip():
            st.warning("Please enter a message.")
            st.stop()

        try:
            with st.spinner("Running dispatch flow..."):
                donation_obj = extract_donation(message)

                pickup_deadline = donation_obj.get("pickup_deadline") or "10 PM"
                pickup_address = donation_obj.get("pickup_address") or ""

                charities = get_charities(accepts=accepts)

                if not charities:
                    st.error("No charities found for the selected accepts filter.")
                    st.stop()

                ranked_obj = rank_charities(donation_obj, charities)
                top = ranked_obj["ranked"][0]
                chosen_id = top.get("id") or top.get("_id")
                if not chosen_id:
                    st.error("Ranking did not return a charity id.")
                    st.json(ranked_obj)
                    st.stop()

                selected_charity = _lookup_full_doc_by_id(charities, chosen_id)
                if not selected_charity:
                    st.error("Could not match ranked charity id to a full charity document.")
                    st.json({"ranked_top": top, "candidate_ids": [c.get('_id') for c in charities]})
                    st.stop()

                if not pickup_address:
                    pickup_address = selected_charity.get("address") or ""

                drivers = get_available_drivers()
                if not drivers:
                    st.error("No available drivers found.")
                    st.stop()

                selected_driver = max(drivers, key=lambda d: float(d.get("rating", 0.0)))

                # Save to session state for map
                st.session_state["last_selected_charity_id"] = selected_charity.get("_id")
                st.session_state["last_selected_driver_id"] = selected_driver.get("_id")
                st.session_state["last_charities"] = charities
                st.session_state["last_drivers"] = drivers

                items_summary = _format_items_summary(donation_obj)
                driver_message = draft_driver_message(
                    pickup=pickup_address,
                    time_str=pickup_deadline,
                    items_summary=items_summary,
                    accept_link=accept_link,
                )

                receipt_obj = generate_receipt(
                    restaurant_id=restaurant_id,
                    charity_doc=selected_charity,
                    donation_obj=donation_obj,
                    pickup_address=pickup_address,
                    pickup_deadline=pickup_deadline,
                )

                audit_id = write_audit(
                    restaurant_id=restaurant_id,
                    restaurant_message=message,
                    donation_obj=donation_obj,
                    selected_charity=selected_charity,
                    selected_driver=selected_driver,
                    driver_message=driver_message,
                    receipt_obj=receipt_obj,
                )

            st.success("Donation dispatched successfully.")

            st.subheader("📦 Donation (Extracted)")
            st.json(donation_obj)

            st.subheader("🏥 Selected Charity")
            st.json(selected_charity)

            st.subheader("🚗 Assigned Driver")
            st.json(selected_driver)

            st.subheader("💬 Driver Message")
            st.code(driver_message)

            st.subheader("🧾 Receipt")
            st.json(receipt_obj)

            st.subheader("🗂️ Audit ID")
            st.code(audit_id)

            with st.expander("Debug", expanded=False):
                st.subheader("Ranked Output")
                st.json(ranked_obj)
                st.subheader("Charity Candidates")
                st.json(charities)
                st.subheader("Drivers")
                st.json(drivers)

        except Exception as e:
            st.error(str(e))
            st.info("If this persists, open the Debug expander and confirm endpoint outputs.")