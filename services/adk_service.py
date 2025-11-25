import streamlit as st
import asyncio
import time
import os
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types as genai_types

from rag_agent.agent import root_agent

from config.settings import APP_NAME_FOR_ADK, USER_ID, INITIAL_STATE, ADK_SESSION_KEY

# Import nest_asyncio at the top of the file
import nest_asyncio
nest_asyncio.apply()  # Apply nest_asyncio to allow nested event loops

@st.cache_resource
def initialize_adk():
    """
    Initializes the Google ADK Runner and manages the ADK session.
    Uses Streamlit's cache_resource to ensure this runs only once per app load.
    """
    print("DEBUG: Initializing ADK runner and session service")
    agent = root_agent # Create our ADK agent defined earlier.
    session_service = InMemorySessionService() # ADK's default in-memory session service for storing session data.
    runner = Runner( # The ADK Runner orchestrates the agent's execution.
        agent=agent,
        app_name=APP_NAME_FOR_ADK,
        session_service=session_service
    )
    
    print(f"DEBUG: Checking for existing session ID in st.session_state[{ADK_SESSION_KEY}]")
    # Check if an ADK session ID already exists in Streamlit's session state.
    if ADK_SESSION_KEY not in st.session_state:
        print("DEBUG: No existing session ID found, creating new session")
        # If not, create a new unique session ID and store it.
        session_id = f"streamlit_adk_session_{int(time.time())}_{os.urandom(4).hex()}"
        print(f"DEBUG: Generated new session ID: {session_id}")
        st.session_state[ADK_SESSION_KEY] = session_id
        
        # Create a new session in ADK's session service.
        print(f"DEBUG: Creating new session in ADK session service: {session_id}")
        # Since create_session is async, we need to run it in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            session_service.create_session(
                app_name=APP_NAME_FOR_ADK,
                user_id=USER_ID,
                session_id=session_id,
                state=INITIAL_STATE, # Initialize with predefined state.
            )
        )
        print(f"DEBUG: Session created successfully: {session_id}")
    else:
        # If an ADK session ID already exists (e.g., on a Streamlit rerun), retrieve it.
        session_id = st.session_state[ADK_SESSION_KEY]
        print(f"DEBUG: Found existing session ID: {session_id}")
        
        # Verify if the session still exists in the ADK session service.
        print(f"DEBUG: Checking if session exists in ADK session service: {session_id}")
        # get_session might also be async, so handle it properly
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        session_exists = loop.run_until_complete(
            session_service.get_session(app_name=APP_NAME_FOR_ADK, user_id=USER_ID, session_id=session_id)
        )
        
        if not session_exists:
            print(f"DEBUG: Session not found in ADK service, recreating: {session_id}")
            # If the session was lost (e.g., full app restart without clearing cache), recreate it.
            loop.run_until_complete(
                session_service.create_session(
                    app_name=APP_NAME_FOR_ADK,
                    user_id=USER_ID,
                    session_id=session_id,
                    state=INITIAL_STATE
                )
            )
            print(f"DEBUG: Session recreated successfully: {session_id}")
        else:
            print(f"DEBUG: Session exists in ADK service: {session_id}")
    return runner, session_id

async def run_adk_async(runner: Runner, session_id: str, user_message_text: str):
    """
    Asynchronously runs a single turn of the ADK agent conversation.
    """
    print(f"DEBUG: Attempting to get session with ID: {session_id}")
    print(f"DEBUG: App name: {APP_NAME_FOR_ADK}, User ID: {USER_ID}")
    
    # Check if session exists in the session service - properly await the async call
    session = await runner.session_service.get_session(app_name=APP_NAME_FOR_ADK, user_id=USER_ID, session_id=session_id)
    if not session:
        print(f"ERROR: Session not found in session service: {session_id}")
        # Try to recreate the session before failing - properly await the async call
        print(f"DEBUG: Attempting to recreate session: {session_id}")
        await runner.session_service.create_session(
            app_name=APP_NAME_FOR_ADK,
            user_id=USER_ID,
            session_id=session_id,
            state=INITIAL_STATE
        )
        # Try to get the session again - properly await the async call
        session = await runner.session_service.get_session(app_name=APP_NAME_FOR_ADK, user_id=USER_ID, session_id=session_id)
        if not session:
            return "Error: ADK session not found and could not be recreated."
        print(f"DEBUG: Session recreated successfully: {session_id}")
    # Prepare the user's message in the format expected by ADK/Gemini.
    content = genai_types.Content(role='user', parts=[genai_types.Part(text=user_message_text)])
    final_response_text = "[Agent encountered an issue]" # Default error message
    # Iterate through the asynchronous events generated by the ADK runner.
    # ADK can yield multiple events (e.g., tool calls, interim responses) before the final response.
    async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
        if event.is_final_response(): # We are only interested in the final response from the agent.
            if event.content and event.content.parts and hasattr(event.content.parts[0], 'text'):
                final_response_text = event.content.parts[0].text
            break # Exit the loop once the final response is received.
    return final_response_text

def run_adk_sync(runner: Runner, session_id: str, user_message_text: str) -> str:
    """
    Synchronous wrapper for running ADK, as Streamlit does not directly support async calls in the main thread.
    """
    print(f"DEBUG: Starting synchronous ADK run with session ID: {session_id}")
    
    # Check if we have an existing event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            print("DEBUG: Using existing running event loop")
            # Use nest_asyncio to run in existing loop
            return loop.run_until_complete(run_adk_async(runner, session_id, user_message_text))
        else:
            print("DEBUG: Using existing non-running event loop")
            return loop.run_until_complete(run_adk_async(runner, session_id, user_message_text))
    except RuntimeError:
        print("DEBUG: No event loop found, creating new one")
        # No event loop exists, create a new one
        return asyncio.run(run_adk_async(runner, session_id, user_message_text))