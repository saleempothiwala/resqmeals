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


def create_job(
    st,
    pickup_address: str,
    items_text: str,
    deadline_text: str,
    charity_name: str = "demo charity",
):
    init_state(st)

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pickup_address": pickup_address,
        "items": items_text,
        "deadline": deadline_text,
        "charity": charity_name,
        "status": "open",           # open → accepted → completed
        "accepted_by": None,
        "accepted_at": None,
        "completed_at": None,
        "mode": "simulation",       # explicit demo marker
    }

    st.session_state.jobs.insert(0, job)
    return job


def list_open_jobs(st):
    init_state(st)
    return [j for j in st.session_state.jobs if j["status"] == "open"]


def get_job_by_id(st, job_id: str):
    init_state(st)
    for j in st.session_state.jobs:
        if j["job_id"] == job_id:
            return j
    return None


def accept_job(st, job_id: str, driver_id: str, driver_name: str):
    init_state(st)

    job = get_job_by_id(st, job_id)
    if not job:
        return False, "Job not found."

    if job["status"] != "open":
        return False, f"Job is already {job['status']}."

    job["status"] = "accepted"
    job["accepted_by"] = {"id": driver_id, "name": driver_name}
    job["accepted_at"] = datetime.now(timezone.utc).isoformat()
    return True, "Accepted."


def complete_job(st, job_id: str):
    init_state(st)

    job = get_job_by_id(st, job_id)
    if not job:
        return False, "Job not found."

    if job["status"] != "accepted":
        return False, f"Job cannot be completed from state '{job['status']}'."

    job["status"] = "completed"
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    return True, "Completed."
