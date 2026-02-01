import streamlit as st
import requests

GATEWAY_URL = "https://resqmeals-llm-gateway.25rqfbmcob70.br-sao.codeengine.appdomain.cloud"

st.set_page_config(
    page_title="ResQMeals Control Panel",
    layout="centered"
)

st.title("🍽️ ResQMeals Dispatch Center")

st.markdown("Connect surplus food with nearby charities and drivers.")

# Input
message = st.text_area(
    "Restaurant Message",
    placeholder="I have 20 trays of pasta left. Pickup by 10 PM at 45 Park Street."
)

if st.button("🚀 Dispatch Donation"):

    if not message.strip():
        st.warning("Please enter a message.")
        st.stop()

    with st.spinner("Processing donation..."):

        # 1. Extract
        r1 = requests.post(
            f"{GATEWAY_URL}/llm/extract_donation",
            json={"text": message},
            timeout=60
        )
        r1.raise_for_status()
        donation = r1.json()["json"]

        # 2. Get charities
        r2 = requests.get(
            f"{GATEWAY_URL}/data/charities",
            params={"accepts": "hot_prepared_food"},
            timeout=30
        )
        charities = r2.json()["docs"]

        # 3. Rank
        r3 = requests.post(
            f"{GATEWAY_URL}/llm/rank_charities",
            json={
                "donation": donation,
                "candidates": charities
            },
            timeout=60
        )
        ranked = r3.json()

        selected_charity = ranked["ranked"][0]

        # 4. Get drivers
        r4 = requests.get(
            f"{GATEWAY_URL}/data/drivers",
            params={"status": "available"},
            timeout=30
        )
        drivers = r4.json()["docs"]

        selected_driver = max(drivers, key=lambda d: d["rating"])

        # 5. Draft message
        r5 = requests.post(
            f"{GATEWAY_URL}/llm/draft_driver_message",
            json={
                "pickup": selected_charity["address"],
                "time": "10 PM",
                "items": donation,
                "accept_link": "https://resqmeals.app/accept/demo"
            }
        )

        driver_msg = r5.json()["text"]

        # 6. Receipt
        r6 = requests.post(
            f"{GATEWAY_URL}/llm/generate_receipt",
            json={
                "restaurant_id": "restaurant:pasta-palace",
                "charity": selected_charity,
                "items": donation,
                "pickup_address": selected_charity["address"],
                "pickup_deadline": "10 PM"
            }
        )

        receipt = r6.json()["json"]

        # 7. Audit
        r7 = requests.post(
            f"{GATEWAY_URL}/audit/log",
            json={
                "restaurant_id": "restaurant:pasta-palace",
                "restaurant_message": message,
                "extracted": donation,
                "selected_charity": selected_charity,
                "selected_driver": selected_driver,
                "driver_message": driver_msg,
                "receipt": receipt,
                "status": "dispatched"
            }
        )

        audit_id = r7.json()["id"]

    st.success("Donation Dispatched!")

    st.subheader("📦 Donation")
    st.json(donation)

    st.subheader("🏥 Selected Charity")
    st.json(selected_charity)

    st.subheader("🚗 Assigned Driver")
    st.json(selected_driver)

    st.subheader("💬 Driver Message")
    st.code(driver_msg)

    st.subheader("🧾 Receipt")
    st.json(receipt)

    st.subheader("🗂️ Audit ID")
    st.code(audit_id)
