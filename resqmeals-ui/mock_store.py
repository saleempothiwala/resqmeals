import uuid
from datetime import datetime, timezone

def init_state(st):
    if "jobs" not in st.session_state:
        st.session_state.jobs = []
    if "drivers_mock" not in st.session_state:
        st.session_state.drivers_mock = [
            {"id": "driver_1", "name": "Ahmad"},
            {"id": "driver_2", "name": "Ali"},
            {"id": "driver_3", "name": "Ayesha"},
        ]

def create_job(st, pickup_address="123 Demo St", items_text="10 pizzas", deadline_text="21:00"):
    init_state(st)
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pickup_address": pickup_address,
        "items": items_text,
        "deadline": deadline_text,
        "charity": "demo charity",
        "status": "open",
        "accepted_by": None,
        "accepted_at": None,
    }
    st.session_state.jobs.insert(0, job)
    return job

def list_open_jobs(st):
    init_state(st)
    return [j for j in st.session_state.jobs if j["status"] == "open"]

def accept_job(st, job_id: str, driver_id: str, driver_name: str):
    init_state(st)
    for j in st.session_state.jobs:
        if j["job_id"] == job_id:
            if j["status"] != "open":
                return False, f"Job is already {j['status']}."
            j["status"] = "accepted"
            j["accepted_by"] = {"id": driver_id, "name": driver_name}
            j["accepted_at"] = datetime.now(timezone.utc).isoformat()
            return True, "Accepted."
    return False, "Job not found."
