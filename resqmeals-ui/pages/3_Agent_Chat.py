import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Agent Chat", page_icon="💬", layout="wide")

st.title("ResQMeals Agent Chat")
st.caption("watsonx Orchestrate embedded chat (Dispatcher)")

ORCHESTRATION_ID = "8a1160d261f44d73ab836f8ff290d252_54ae9870-0f92-4bf1-b73e-3e5a94d78672"
HOST_URL = "https://au-syd.watson-orchestrate.cloud.ibm.com"
CRN = "crn:v1:bluemix:public:watsonx-orchestrate:au-syd:a/8a1160d261f44d73ab836f8ff290d252:54ae9870-0f92-4bf1-b73e-3e5a94d78672::"

# choose ONE agent to embed (recommended: Dispatcher)
DISPATCHER_AGENT_ID = "4d1fefd4-ce4c-4ca9-8958-2c2ed9c69b0c"

html = f"""
<div id="root"></div>

<script>
  window.wxOConfiguration = {{
    orchestrationID: "{ORCHESTRATION_ID}",
    hostURL: "{HOST_URL}",
    rootElementID: "root",
    deploymentPlatform: "ibmcloud",
    crn: "{CRN}",
    chatOptions: {{
      agentId: "{DISPATCHER_AGENT_ID}"
    }}
  }};

  (function () {{
    const script = document.createElement("script");
    script.src = `${{window.wxOConfiguration.hostURL}}/wxochat/wxoLoader.js?embed=true`;
    script.onload = function () {{
      wxoLoader.init();
    }};
    document.head.appendChild(script);
  }})();
</script>

<style>
  #root {{
    min-height: 720px;
  }}
</style>
"""

components.html(html, height=780, scrolling=True)
