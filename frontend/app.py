import os
from pathlib import Path
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv

from api_client import BackendClient, BackendClientError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

st.set_page_config(
    page_title="AI Assistance",
    page_icon="✨",
    layout="centered",
)


def create_conversation() -> str:
    conversation_id = uuid4().hex
    st.session_state.conversations[conversation_id] = {
        "title": "New conversation",
        "messages": [],
    }
    st.session_state.active_conversation_id = conversation_id
    return conversation_id


if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "active_conversation_id" not in st.session_state:
    create_conversation()

st.title("AI Assistance")
st.caption("A private AI assistant powered by your local Ollama model.")

with st.sidebar:
    st.header("Conversations")
    if st.button("＋ New conversation", use_container_width=True):
        create_conversation()

    conversation_ids = list(st.session_state.conversations)
    active_id = st.session_state.active_conversation_id
    if active_id not in st.session_state.conversations:
        active_id = conversation_ids[0]
        st.session_state.active_conversation_id = active_id
    selected_id = st.selectbox(
        "Your chats",
        options=conversation_ids,
        index=conversation_ids.index(active_id),
        format_func=lambda conversation_id: st.session_state.conversations[
            conversation_id
        ]["title"],
        label_visibility="collapsed",
    )
    st.session_state.active_conversation_id = selected_id

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.conversations[selected_id] = {
            "title": "New conversation",
            "messages": [],
        }

    st.divider()
    st.subheader("Connection")
    backend_url = st.text_input(
        "Backend URL",
        value=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"),
        help="Set BACKEND_URL in .env to save this default.",
    )
    api_token = os.getenv("API_AUTH_TOKEN", "")
    try:
        chat_timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")) + 15
        client = BackendClient(
            backend_url,
            api_token,
            timeout=5,
            chat_timeout=chat_timeout,
        )
        client.health()
        if not api_token:
            st.warning("Backend is online, but API_AUTH_TOKEN is not configured.")
            model_name = "Unavailable"
        else:
            model_name = client.model()
            st.success("Backend connected")
    except (BackendClientError, ValueError) as error:
        client = None
        model_name = "Unavailable"
        st.error(f"Backend unavailable: {error}")

    st.caption(f"Model: `{model_name}`")
    st.caption("Chat history is kept only in this browser session.")

conversation = st.session_state.conversations[selected_id]
for message in conversation["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask a question...")
if prompt:
    user_message = {"role": "user", "content": prompt}
    conversation["messages"].append(user_message)
    if conversation["title"] == "New conversation":
        title = prompt.strip().replace("\n", " ")
        conversation["title"] = title[:40] + ("..." if len(title) > 40 else "")

    with st.chat_message("user"):
        st.markdown(prompt)

    if client is None:
        conversation["messages"].pop()
        st.error("Please check the backend URL and connection status, then try again.")
    else:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = client.chat(conversation["messages"])
                    answer = result["response"]
                except (BackendClientError, KeyError) as error:
                    conversation["messages"].pop()
                    st.error(f"Sorry, I couldn't get a response. {error}")
                else:
                    conversation["messages"].append(
                        {"role": "assistant", "content": answer}
                    )
                    st.markdown(answer)
