# 🍽️ ResQMeals – AI-Powered Food Rescue Dispatcher

ResQMeals is an agentic AI platform that connects surplus food from restaurants to nearby charities and volunteer drivers in real time. It uses IBM watsonx Orchestrate, AI-powered agents, and cloud-native services to automate food rescue workflows and reduce waste.

---

## 🌍 Problem

Restaurants and food retailers regularly dispose of large quantities of safe, edible food because redistributing it is slow, manual, and unreliable. Charities and volunteers often lack timely information about available donations, while coordination typically depends on phone calls, spreadsheets, and informal messaging.

This results in:
- Increased food waste
- Higher greenhouse gas emissions
- Missed opportunities to support vulnerable communities

---

## 💡 Solution

ResQMeals transforms unstructured donation messages into a fully automated dispatch workflow.

A restaurant sends a simple message such as:

> "I have 10 trays of biryani available after 3 PM."

ResQMeals then:

1. Extracts structured donation data using AI
2. Finds eligible nearby charities
3. Ranks candidates based on suitability
4. Assigns an available volunteer driver
5. Drafts a pickup message
6. Generates a digital receipt
7. Logs the full workflow for audit

The entire process completes in seconds.

---

## 🏗️ Architecture

Restaurant → Streamlit UI → LLM Gateway → Cloudant
↘ watsonx Orchestrate ↗


### Components

- **UI**: Streamlit app on IBM Code Engine
- **Gateway**: Flask API on IBM Code Engine
- **Database**: IBM Cloudant (charities, drivers, audit logs)
- **Orchestration**: IBM watsonx Orchestrate
- **LLM Provider**: Groq Cloud (LLama 3)

---

## 🤖 Agentic Architecture

ResQMeals uses multiple specialized agents coordinated by IBM watsonx Orchestrate:

| Agent Name            | Responsibility                                  |
|-----------------------|------------------------------------------------|
| Extract Donation      | Convert free text to structured JSON           |
| Rank Charities        | Select best charity for donation               |
| Draft Driver Message  | Generate pickup instructions                  |
| Generate Receipt      | Create digital receipt                         |
| Dispatcher            | Orchestrates full workflow                    |

watsonx Orchestrate manages sequencing, data flow, and validation between agents.

---

## 🚀 Live Demo

### UI
https://resqmeals-ui.25rqfbmcob70.br-sao.codeengine.appdomain.cloud/

### Gateway API
https://resqmeals-llm-gateway.25rqfbmcob70.br-sao.codeengine.appdomain.cloud/

### Health Check


GET /health


---

## 🧪 Demo Examples

Try pasting any of the following into the UI:



I have 7 portions of pizzas to be picked up at 9pm from LP Wettres vei

We have 12 cans of beans that expires in 3 days to be picked up from Tesco Sutton before 8pm

We have 10 portions of leftover biryani that can be picked up after 3pm from Hagalokkveien 13


---

## 📁 Repository Structure



resqmeals/
├── resqmeals-llm-gateway/ # Flask API + LLM integration
├── resqmeals-ui/ # Streamlit dashboard
└── README.md


---

## ⚙️ Environment Variables

### Gateway



CLOUDANT_URL
CLOUDANT_APIKEY
CLOUDANT_DB_CHARITIES
CLOUDANT_DB_DRIVERS
CLOUDANT_DB_RESTAURANTS
CLOUDANT_DB_AUDIT

GROQ_API_KEY
GROQ_MODEL
LLM_PROVIDER=groq


### UI



GATEWAY_URL
DEFAULT_ACCEPTS
DEFAULT_RESTAURANT_ID
DEFAULT_ACCEPT_LINK


Create `.env.example` files for local development. Never commit secrets.

---

## 🐳 Build & Deploy

### Build Gateway

```bash
cd resqmeals-llm-gateway

docker buildx build \
  --platform linux/amd64 \
  -t saleempothiwala/resqmeals-llm-gateway:latest \
  --push .

Build UI
cd resqmeals-ui

docker buildx build \
  --platform linux/amd64 \
  -t saleempothiwala/resqmeals-ui:latest \
  --push .


Deploy both images on IBM Code Engine.

🗂️ Data

All datasets used in this project are synthetic and created for demonstration purposes. No personal, proprietary, or third-party private data is used.

📊 Audit & Traceability

Every dispatch is logged in Cloudant with:

Original message

Extracted donation data

Selected charity

Selected driver

Generated receipt

Timestamp and status

This ensures transparency and compliance.

📈 Future Enhancements

Route optimization agent

Real SMS/WhatsApp integration

Demand forecasting

Carbon impact estimation

Multi-city deployment

👥 Team

Saleem Pothiwala – Architecture, Data Engineering, System Design

Rukhmah – Agent Design, Testing, Integration

Eman – UI, Data Modeling, Workflow Validation

🏆 Hackathon Context

Built for the IBM AI Demystified Hackathon using:

IBM watsonx Orchestrate

IBM Code Engine

IBM Cloudant

ResQMeals demonstrates how agentic AI can automate real-world sustainability workflows at scale.

📄 License

This project is for hackathon and educational purposes.
