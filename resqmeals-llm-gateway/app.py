from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def health():
    return jsonify({"status": "resqmeals llm gateway running"})

@app.route("/ping")
def ping():
    return jsonify({"pong": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

def call_groq(system, user):

    api_key = os.environ["GROQ_API_KEY"]

    url = "https://api.groq.com/openai/v1/chat/completions"

    body = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.2,
        "max_tokens": 500
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=body, headers=headers, timeout=60)
    r.raise_for_status()

    return r.json()["choices"][0]["message"]["content"]

def call_llm(system, user):

    provider = os.environ.get("LLM_PROVIDER", "groq")

    if provider == "groq":
        return call_groq(system, user)

    if provider == "watsonx":
        return call_granite(system, user)

    raise RuntimeError("Unknown LLM provider")