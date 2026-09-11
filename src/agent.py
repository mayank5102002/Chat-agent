import os
import asyncio
import json
import uuid
from dotenv import load_dotenv
from google import genai
from google.genai import types
from typing import AsyncGenerator
from src.url_fetcher import fetch_url_content
import src.url_fetcher as url_fetcher

load_dotenv()

# Authenticated Gemini client used by the primary conversational agent.
client        = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
# Model name used for conversations and memory summarization.
MODEL_USED    = "gemini-3.5-flash-lite"
# JSON file used to persist the visible chat history.
HISTORY_FILE  = "chat_history.json"
# Active Gemini chat session, or None when no session is initialized.
chat_instance = None

def get_full_history():
    """Read the persisted chat log.

    Returns:
        The saved message list, or an empty list when the file is missing or invalid.
    """
    try:
        with open(HISTORY_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return an empty list if the file doesn't exist yet
        return []

def append_to_history(role: str, text: str, msg_id: str = None, error: bool = False):
    """Append one message to the persisted chat log.

    Parameters:
        role: Sender label, such as ``user`` or ``agent``.
        text: Message content to store.
        msg_id: Optional identifier used to track a user message.
        error: Whether the message ended in an error.

    """
    history = get_full_history()
    entry = {"role": role, "text": text, "error": error}
    if msg_id:
        entry["id"] = msg_id
    history.append(entry)
    with open(HISTORY_FILE, "w") as file:
        json.dump(history, file, indent=4)

def mark_message_error(msg_id: str):
    """Mark a persisted message as failed.

    Parameters:
        msg_id: Identifier of the message to flag.

    """
    history = get_full_history()
    for msg in history:
        if msg.get("id") == msg_id:
            msg["error"] = True
            break
    with open(HISTORY_FILE, "w") as file:
        json.dump(history, file, indent=4)

def reset_all_memory():
    """
    Delete all persisted memory and clear the active chat session.
    """
    global chat_instance
    
    # 1. Clear the chat history JSON
    with open(HISTORY_FILE, "w") as file:
        json.dump([], file)
        
    # 2. Delete the long-term memory text file if it exists
    try:
        os.remove("long_term_memory.txt")
    except FileNotFoundError:
        pass
        
    # 3. Reset the active chat instance so the next message starts completely fresh
    chat_instance = None

def chat_with_agent_stream(chat_instance, user_input):
    """Send input to a chat session and return its response stream.

    Parameters:
        chat_instance: Gemini chat session that receives the message.
        user_input: User message sent to the session.

    Returns:
        The SDK response stream for the generated message.
    """
    return chat_instance.send_message_stream(user_input)

def summarize_and_store(chat_instance):
    """Summarize the current chat and save it as long-term memory.

    Parameters:
        chat_instance: Gemini chat session whose history is summarized.

    """
    history_text = ""
    for message in chat_instance.get_history():
        role = message.role
        # Extract text from the parts array
        text = message.parts[0].text if message.parts else "[Tool Execution]"
        history_text += f"{role.upper()}: {text}\n"

    try:
        with open("long_term_memory.txt", "r") as file:
            past_memories = file.read()
    except FileNotFoundError:
        past_memories = "No prior memory."

    # 2. Define the summarization instruction
    prompt = f"""
    Here is the existing user profile, and here is a new conversation.
    Update the existing profile with any new facts. Consolidate duplicate topics.
    Do not delete established facts unless the new conversation explicitly contradicts them.

    Conversation History:
    {history_text}

    Existing Profile:
    {past_memories}
    """

    # 3. Call the model statelessly (no chat loop needed for summarization)
    temp_chat = client.chats.create(model=MODEL_USED)
    summary_response = temp_chat.send_message(prompt)

    # 4. Append to your database or local file
    with open("long_term_memory.txt", "w") as file:
        file.write(summary_response.text + "\n")

def start_new_session_with_memory():
    """Create a Gemini chat session seeded with persona and saved memory.

    Returns:
        A configured Gemini chat session with URL-fetching enabled.
    """
    # 1. Load the past summaries and persona prompt from local files    
    try:
        with open("long_term_memory.txt", "r") as file:
            past_memories = file.read()
    except FileNotFoundError:
        past_memories = "No prior memory."

    try:
        with open("persona.txt", "r") as file:
            persona_prompt = file.read().strip()
    except FileNotFoundError:
        persona_prompt = "You are a helpful AI assistant."

    # 2. Inject it into the system prompt
    dynamic_system_prompt = f"""
    {persona_prompt}

    If you lack context to complete a task or understand a query, 
    ask the user directly in your response.

    Here is everything you remember about the user from past conversations:
    {past_memories}
    """

    # 3. Initialize the new chat with the injected memory
    memory_enabled_chat = client.chats.create(
        model=MODEL_USED,
        config=types.GenerateContentConfig(
            system_instruction=dynamic_system_prompt,
            tools=[fetch_url_content],
        )
    )

    return memory_enabled_chat

def initialize_chat():
    """
    Create the global chat session if one is not already active.
    """
    global chat_instance
    if chat_instance is None:
        chat_instance = start_new_session_with_memory()

def close_chat():
    """Summarize the active session and release it.

    Returns:
        None.
    """
    global chat_instance
    if chat_instance is not None:
        # Only summarize if at least one message was exchanged
        if chat_instance.get_history():
            summarize_and_store(chat_instance)
        chat_instance = None
        print("Memory saved and chat session cleared.")

def converse_stream(question):
    """Initialize the session when needed and start a response stream.

    Parameters:
    question: User question sent to the active chat session.

    Returns:
    The SDK response stream for the generated answer.
    """
    initialize_chat()  # Ensure chat is initialized with memory

    return chat_with_agent_stream(chat_instance, question)

async def run_agent_stream(session_id: str, message: str) -> AsyncGenerator[str, None]:
    """Persist a user message and stream the agent's response.

    Parameters:
        session_id: Client-provided session identifier.
        message: User message to send to the agent.

    Yields:
        Text chunks from the agent response.
    """
    msg_id = str(uuid.uuid4())
    # 1. Record user message (error defaults to False)
    append_to_history("user", message, msg_id=msg_id, error=False)
    
    completed = False
    try:
        response_stream = await asyncio.to_thread(converse_stream, message)  
        full_agent_response = ""

        while True:
            chunk = await asyncio.to_thread(next, response_stream, None)
            if chunk is None:
                break
                
            if chunk.text:
                full_agent_response += chunk.text
                yield chunk.text

        # 2. Only save agent message if stream completed with content
        if full_agent_response.strip():
            append_to_history("agent", full_agent_response)
            completed = True

    except Exception:
        mark_message_error(msg_id)
        raise
    finally:
        # 3. If the client disconnected or execution terminated early
        if not completed:
            mark_message_error(msg_id)