import os
import json
import time
import requests
import streamlit as st

from mock_store import init_state, create_job

st.set_page_config(page_title="ResQMeals Dispatch Center", page_icon="🍽️", layout="wide")
init_state(st)

# Read gateway URL from env var (fallback to Saleem's deployed URL if set there, otherwise localhost)
DEFAULT_GATEWAY = "http://localhost:8080"
GATEWAY_URL = os.getenv("GATEWAY_URL", DEFAULT_GATEWAY)

st.title("🍽️ ResQMeals Dispatch Center")
st.caption("Connect surplus food with nearby charities and drivers.")

# -----------------------------
# Helpers
# -----------------------------
def post_json(url: str, payload: dict, timeout: int = 60):
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

def get_json(url: str, timeout: int = 60):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def safe_ranked_list(ranked_response: dict):
    # Handles different possible response shapes from the gateway
    # Expected by older UI: {"ranked": [...]}
    # Common contract: {"ranked_charities": [...]}
    candidates = (
        ranked_response.get("ranked")
        or ranked_response.get("ranked_charities")
        or ranked_response.get("ranked_charities_list")
        or ranked_response.get("results")
        or []
    )
    return candidates

def find_job_by_id(job_id: str):
    for j in st.session_state.jobs:
        if j["job_id"] == job_id:
            return j
    return None


# -----------------------------
# Layout
# -----------------------------
left, right = st.columns([2, 1], gap="large")

with left:
    st.subheader("Restaurant Message")
    restaurant_msg = st.text_area(
        "Paste a restaurant message",
        placeholder="e.g. I have 10 pizzas left to be picked up by 9pm. Address: 123 Demo St.",
        height=140,
    )

    # Main dispatch button (mock, no API keys)
    if st.button("🚀 Dispatch Donation", use_container_width=False):
        msg = (restaurant_msg or "").strip()
        if not msg:
            st.warning("Please enter a restaurant message first.")
        else:
            # Create a mock job locally
            job = create_job(
                st,
                pickup_address="123 Demo St",
                items_text=msg,
                deadline_text="21:00",
            )
            st.session_state["latest_job_id"] = job["job_id"]
            st.success(f"Dispatch job created: {job['job_id']}. Go to Driver Console page to accept it.")

    st.divider()

    # Optional: full workflow via gateway (can be enabled later)
    st.subheader("Optional: Full workflow via gateway")
    st.write("Enable this only when your gateway has valid keys and is running.")

    use_gateway = st.checkbox("Use gateway workflow (LLM + Cloudant)", value=False)
    st.write(f"Gateway URL: {GATEWAY_URL}")

    if use_gateway:
        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("Run gateway workflow now", use_container_width=True):
                msg = (restaurant_msg or "").strip()
                if not msg:
                    st.warning("Please enter a restaurant message first.")
                    st.stop()

                try:
                    # 1) Extract
                    extracted = post_json(f"{GATEWAY_URL}/llm/extract_donation", {"text": msg})

                    # 2) Fetch charities
                    charities = get_json(f"{GATEWAY_URL}/data/charities")

                    # 3) Rank charities
                    ranked = post_json(
                        f"{GATEWAY_URL}/llm/rank_charities",
                        {"donation": extracted, "charities": charities},
                    )

                    ranked_list = safe_ranked_list(ranked)
                    if not ranked_list:
                        st.error(f"No ranked charities returned. Gateway response keys: {list(ranked.keys())}")
                        st.stop()

                    selected_charity = ranked_list[0]

                    # 4) Fetch drivers
                    drivers = get_json(f"{GATEWAY_URL}/data/drivers")
                    if not drivers:
                        st.error("No drivers returned from /data/drivers")
                        st.stop()

                    # naive driver selection for now (replace later with real dispatch acceptance)
                    selected_driver = drivers[0]

                    # 5) Draft driver message
                    driver_msg = post_json(
                        f"{GATEWAY_URL}/llm/draft_driver_message",
                        {"donation": extracted, "charity": selected_charity, "driver": selected_driver},
                    )

                    # 6) Generate receipt
                    receipt = post_json(
                        f"{GATEWAY_URL}/llm/generate_receipt",
                        {"donation": extracted, "charity": selected_charity},
                    )

                    # 7) Audit log
                    audit = post_json(
                        f"{GATEWAY_URL}/audit/log",
                        {
                            "step_name": "ui_gateway_workflow",
                            "tool_called": "resqmeals-ui",
                            "output_summary": "Completed gateway workflow from UI",
                            "payload": {"donation": extracted.get("id", None)},
                        },
                    )

                    st.session_state["gateway_last"] = {
                        "extracted": extracted,
                        "selected_charity": selected_charity,
                        "selected_driver": selected_driver,
                        "driver_message": driver_msg,
                        "receipt": receipt,
                        "audit": audit,
                    }

                    st.success("Gateway workflow completed.")

                except requests.exceptions.RequestException as e:
                    st.error(f"Gateway call failed: {e}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

        with colB:
            if st.button("Clear gateway results", use_container_width=True):
                st.session_state.pop("gateway_last", None)
                st.success("Cleared.")

    # Show gateway results (if any)
    if use_gateway and st.session_state.get("gateway_last"):
        st.divider()
        st.subheader("Gateway results")
        data = st.session_state["gateway_last"]
        st.write("Extracted donation")
        st.json(data["extracted"])
        st.write("Selected charity")
        st.json(data["selected_charity"])
        st.write("Selected driver")
        st.json(data["selected_driver"])
        st.write("Driver message")
        st.json(data["driver_message"])
        st.write("Receipt")
        st.json(data["receipt"])
        st.write("Audit")
        st.json(data["audit"])


with right:
    st.subheader("Dispatch status")

    latest_id = st.session_state.get("latest_job_id")
    if not latest_id:
        st.info("No dispatch job created yet. Click Dispatch Donation to create a job.")
    else:
        job = find_job_by_id(latest_id)
        if not job:
            st.warning("Latest job id not found in local store.")
        else:
            st.write(f"Job id: {job['job_id']}")
            st.write(f"Status: {job['status']}")
            st.write(f"Pickup: {job['pickup_address']}")
            st.write(f"Items: {job['items']}")
            st.write(f"Deadline: {job['deadline']}")
            st.write(f"Charity: {job['charity']}")

            if job["status"] == "accepted":
                st.success(f"Accepted by: {job['accepted_by']['name']}")
                st.write(f"Accepted at: {job['accepted_at']}")
                st.write("Next: continue the workflow (generate receipt etc.) or mark completed.")
                if st.button("Mark completed (mock)", use_container_width=True):
                    job["status"] = "completed"
                    st.success("Marked completed.")
                    st.rerun()

            elif job["status"] == "completed":
                st.success("Completed.")
            else:
                st.info("Waiting for a driver to accept. Open the Driver Console page in the sidebar.")
                if st.button("Refresh status", use_container_width=True):
                    st.rerun()

    st.divider()
    st.subheader("Quick demo tips")
    st.write("1) Create a job here")
    st.write("2) Open Driver Console page and click Accept")
    st.write("3) Come back here to see status update")
