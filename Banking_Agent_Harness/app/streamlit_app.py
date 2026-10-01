"""Simple Streamlit chat UI for the banking agent."""

import asyncio
import uuid

import streamlit as st
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent, AGENT_NAME

st.title("Banking Assistant")

# --- One-time setup: session service, runner, and a fixed user/session id ---
if "session_service" not in st.session_state:
    st.session_state.session_service = InMemorySessionService()
    st.session_state.user_id = "demo_user"
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.runner = Runner(
        agent=root_agent,
        app_name=AGENT_NAME,
        session_service=st.session_state.session_service,
    )
    st.session_state.messages = []

    # ADK sessions are created async — set it up once at startup
    asyncio.run(
        st.session_state.session_service.create_session(
            app_name=AGENT_NAME,
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id,
        )
    )


async def _run_agent_async(user_input: str) -> str:
    """Send one message to the agent and return its final text response."""
    content = types.Content(role="user", parts=[types.Part(text=user_input)])

    final_response = ""
    async for event in st.session_state.runner.run_async(
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    return final_response


def run_agent(user_input: str) -> str:
    """Sync wrapper, since Streamlit's script execution isn't async."""
    return asyncio.run(_run_agent_async(user_input))


# --- Chat UI ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Ask about your account..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write("its promt...."+prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = run_agent(prompt)
        st.write("hey man..............."+response)

    st.session_state.messages.append({"role": "assistant", "content": response})