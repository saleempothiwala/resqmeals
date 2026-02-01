Food Waste Reduction Solution

Our solution utilizes a multi-agent architecture to reduce food waste by connecting restaurants with excess food to charities in need. The system leverages Granite, a natural language processing tool, to extract structured data from raw text inputs.

Agent Architecture

Our architecture consists of four agents:

Dispatcher Agent: The only agent that interacts with the restaurant, responsible for owning the state machine and calling other agents/tools.
Intake Agent: Calls the extract_donation tool to parse raw text into structured JSON, validates required fields, and asks follow-up questions if necessary.
Matching Agent: Calls the find_candidates tool to perform a deterministic geo-radius filter and the rank_charities tool to pick the top 3 matches using LLM reasoning.
Dispatch Agent: Creates jobs for drivers in the Driver Console, monitors acceptance, and generates receipts with legal disclaimers.
Tools Used

Each agent uses the following tools:

Dispatcher Agent: audit_log to record every state transition in Cloudant for auditability.
Intake Agent: extract_donation to parse raw text into structured JSON using watsonx.ai (Granite).
Matching Agent: find_candidates and rank_charities to perform deterministic filtering and LLM-based ranking.
Dispatch Agent: create_job, job_status, and generate_receipt to manage the Driver Console workflow, monitor acceptance, and draft receipts.
Solution Overview

Our solution reduces food waste by efficiently connecting restaurants with excess food to charities in need. The system's multi-agent architecture and use of Granite enable seamless data extraction, matching, and dispatching.
