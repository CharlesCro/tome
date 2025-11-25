import streamlit as st

from services.adk_service import initialize_adk, run_adk_sync
from config.settings import MESSAGE_HISTORY_KEY, get_api_key


# <-- Initiate ADK -->
adk_runner, current_session_id = initialize_adk()


# <-- Streamlit Page -->
st.title('D&D Tome of Ancient Knowledge')

with st.sidebar:
    st.subheader("Select the Ambience")
    available_tones = [
        "serious", "happy", "romantic", "sexual", 
        "comical", "spooky", "dramatic", "mystical",
        "angry", "whimsical"
    ]

    # Multi-select for tone settings
    selected_tones = st.multiselect(
        "Choose encounter vibes / emotional tone:",
        options=available_tones,
        default=[],
        accept_new_options = True,
    )

# Ensure tone is stored in session state
st.session_state["selected_tones"] = selected_tones


# Initialize chat message history in Streamlit's session state if it doesn't exist.
if MESSAGE_HISTORY_KEY not in st.session_state:
    st.session_state[MESSAGE_HISTORY_KEY] = []
# Display existing chat messages from the session state.
for message in st.session_state[MESSAGE_HISTORY_KEY]:
    with st.chat_message(message['role']): # Use Streamlit's chat message container for styling.
        st.markdown(message['content'])
# Handle new user input.
if prompt := st.chat_input('Enter message'):
    # Build tone modifier string
    if selected_tones:
        tone_instruction = (
            "\n\n[DM Tone Preference: "
            + ", ".join(selected_tones)
            + "]\nThe response should reflect these emotional tones."
        )
    else:
        tone_instruction = ""

    final_prompt = prompt + tone_instruction
    # Append user's message to history and display it.
    st.session_state[MESSAGE_HISTORY_KEY].append({'role': 'user', 'content': prompt})
    with st.chat_message('user'):
        st.markdown(prompt)
    # Process the user's message with the ADK agent and display the response.
    with st.chat_message('assistant'):
        message_placeholder = st.empty() # Create an empty placeholder to update with the assistant's response.
        with st.spinner('Assistant is thinking...'): # Show a spinner while the agent processes the request.
            print(f"DEBUG UI: Sending message to ADK with session ID: {current_session_id}")
            agent_response = run_adk_sync(adk_runner, current_session_id, prompt) # Call the synchronous ADK runner.
            print(f"DEBUG UI: Received response from ADK: {agent_response[:50]}...")
            message_placeholder.markdown(agent_response) # Update the placeholder with the final response.
    
    # Append assistant's response to history.
    st.session_state[MESSAGE_HISTORY_KEY].append({'role': 'assistant', 'content': agent_response})