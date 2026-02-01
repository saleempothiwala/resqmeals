import streamlit as st
from mock_store import init_state, list_open_jobs, accept_job

st.set_page_config(page_title="Driver Console", page_icon="🚗", layout="wide")

init_state(st)

st.title("Driver Console (mock)")
st.caption("Accept open pickup jobs. This simulates SMS replies.")

drivers = st.session_state.drivers_mock
driver_name = st.selectbox("Driver identity", [d["name"] for d in drivers], index=0)
driver = next(d for d in drivers if d["name"] == driver_name)

open_jobs = list_open_jobs(st)

col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("Open jobs")
    if not open_jobs:
        st.info("No open jobs right now. Create one from the Dispatch Center page.")
    else:
        for job in open_jobs:
            with st.container(border=True):
                st.write(f"Job id: {job['job_id']}")
                st.write(f"Pickup: {job['pickup_address']}")
                st.write(f"Items: {job['items']}")
                st.write(f"Deadline: {job['deadline']}")
                st.write(f"Charity: {job['charity']}")

                if st.button(f"Accept {job['job_id']}", key=f"accept_{job['job_id']}"):
                    ok, msg = accept_job(st, job["job_id"], driver["id"], driver["name"])
                    if ok:
                        st.success(f"{msg} Assigned to {driver['name']}.")
                        st.rerun()
                    else:
                        st.warning(msg)

with col2:
    st.subheader("Accepted / history")
    accepted = [j for j in st.session_state.jobs if j["status"] == "accepted"]
    if not accepted:
        st.write("None yet.")
    else:
        for j in accepted[:10]:
            with st.container(border=True):
                st.write(f"{j['job_id']} accepted by {j['accepted_by']['name']}")
                st.write(f"Accepted at: {j['accepted_at']}")
                st.write(f"Pickup: {j['pickup_address']}")
