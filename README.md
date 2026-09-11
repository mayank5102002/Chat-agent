# Autonomous Gemini Chat Agent

A containerized, async-first AI chat agent utilizing the Google Gemini SDK and FastAPI. This project demonstrates advanced backend patterns, including non-blocking Server-Sent Events (SSE), dynamic tool execution, and hierarchical context summarization.

---

## 🚀 Architecture & Core Capabilities

* **Autonomous URL Browsing & Summarization:** When a user shares a link, the agent dynamically triggers a custom URL finder (powered by `requests` and `BeautifulSoup4`). It surfs the web page, parses the HTML, and uses a stateless sub-agent to generate a concise summary before injecting it into the main chat, saving tokens and keeping the conversation focused.
* **Concurrency Bridging:** Uses `asyncio.to_thread` to wrap synchronous SDK calls, keeping the FastAPI event loop unblocked during streaming generation.
* **Hierarchical Pipeline:** Offloads heavy processing and data compression to background workers before the context ever reaches the primary conversational window.
* **Decoupled Persona:** Personality configurations are externalized into `persona.txt` for hot-swappable agent behaviors without requiring code changes or server restarts.

---

## 🧠 State Management & Future Scalability

This agent currently utilizes a lightweight, file-based persistence system to maintain conversational context and summarization data.

* **Local File Persistence:** Conversational state is continuously serialized and written to local flat files (`chat_history.json` and `long_term_memory.txt`) to reduce overhead for single-instance deployments.
* **Container Volume Mounting:** Because Docker containers are inherently ephemeral, the run command uses a volume mount (`-v ${PWD}:/app`) to bridge the container's storage to your local hard drive, ensuring memories survive container shutdowns.
* **Static Model Configuration:** The specific Gemini AI model version is currently declared statically within the application logic. Future iterations will externalize this into environment variables (e.g., `GEMINI_MODEL=gemini-3.5-flash-lite`) to allow seamless, dynamic model swapping without altering code.
* **Future Database Integration:** If deployment needs scale up, this local flat-file architecture is designed to be easily swapped out for a centralized, managed database system, allowing the memory state to be completely decoupled from the local host environment.
* **Observability:** Future updates will integrate structured JSON logging and distributed tracing for multi-agent workflows.

---

## Tech Stack Overview

| Component | Technology |
| :--- | :--- |
| **API Framework** | FastAPI, Uvicorn, Starlette |
| **AI SDK** | Google GenAI SDK (`google-genai`) |
| **Scraping** | Requests, BeautifulSoup4 |
| **Infrastructure** | Docker, Git |

---

## Local Development & Docker Quickstart

Follow these commands to deploy the agent locally using Docker. 

**1. Clone the Repository**
```bash
git clone https://github.com/mayank5102002/Chat-agent.git
cd Chat-agent
```

**2. Set Up Environment Variables**
Create a `.env` file in the root of the project. Add your Gemini API key exactly as shown below, with no quotation marks:
```text
GEMINI_API_KEY=your_actual_key_here
```

**3. Build the Container Image**
Compile the Dockerfile into a runnable image:
```bash
docker build -t ai-agent .
```

**4. Run the Application**
Start the container. This command maps port 8000, injects your `.env` file, and mounts the current directory to persist chat history and long-term memory files locally.
```bash
docker run -p 8000:8000 --env-file .env -v ${PWD}:/app ai-agent
```
(If you are using standard Windows Command Prompt instead of PowerShell, replace ${PWD} with %cd%).

**5. Start Chatting**
Navigate to **`http://localhost:8000`** in your web browser.

---

## Project Structure

* `src/` - Core routing, agent logic, and tool definitions.
* `static/` - Frontend HTML and JS assets.
* `main.py` - FastAPI entry point and SSE configuration.
* `persona.txt` - System instructions for the LLM.
* `chat_history.json` / `long_term_memory.txt` - Local persistence layers.