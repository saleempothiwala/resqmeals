# ResQMeals
**Tagline:** Rescuing surplus meals with agentic AI.

## Solution Overview
Our solution reduces food waste by efficiently connecting restaurants with excess food to charities in need. The system utilizes a multi-agent architecture and leverages **Granite** (IBM watsonx.ai) to enable seamless data extraction, matching, and dispatching from raw natural language inputs.

---

## Agent Architecture
Our architecture consists of four specialized agents that collaborate to complete a food rescue:

| Agent | Responsibility |
| :--- | :--- |
| **Dispatcher Agent** | The lead coordinator. Owns the state machine and manages the end-to-end lifecycle. |
| **Intake Agent** | Data specialist. Parses raw text into structured JSON and validates required fields. |
| **Matching Agent** | Analyst. Performs geo-radius filtering and ranks charities with explainable reasoning. |
| **Dispatch Agent** | Logistician. Creates driver jobs, monitors acceptance, and generates legal receipts. |

---

## Tools & Technology Stack
Each agent is powered by specific tools hosted on **IBM Code Engine** and backed by **IBM Cloudant**:

### 1. Dispatcher Agent
* **audit_log**: Records every state transition in Cloudant for full auditability and demo replay.

### 2. Intake Agent
* **extract_donation**: Uses **watsonx.ai (Granite)** to parse raw text into structured JSON.
* **Follow-up Logic**: Automatically detects missing fields and requests clarification from the user.

### 3. Matching Agent
* **find_candidates**: Performs a deterministic geo-radius filter against the charity directory.
* **rank_charities**: Uses LLM reasoning to select the top 3 matches based on charity-specific intake rules.

### 4. Dispatch Agent
* **create_job**: Interface with the Driver Console to alert the volunteer pool.
* **job_status**: Monitors driver acceptance via polling or webhooks.
* **generate_receipt**: Uses LLM to draft final receipts including mandatory legal disclaimers.

---

## The "Listen, Reason, Act" Flow
1. **Listen:** Restaurant enters a message (e.g., "20 trays of pasta at 123 Main St").
2. **Reason:** Granite extracts data, classifies food, and ranks charities with reasons.
3. **Act:** Orchestrate tools query Cloudant, alert drivers, and generate the final documentation.
