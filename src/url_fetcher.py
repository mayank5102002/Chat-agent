import os
import requests
from bs4 import BeautifulSoup
from google import genai
from dotenv import load_dotenv

load_dotenv()
# Secondary stateless Gemini client used to summarize fetched pages.
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
# Model name used by the webpage summarization worker.
WORKER_MODEL = "gemini-3.5-flash-lite"

def fetch_url_content(url: str) -> str:
    """Fetch and, when necessary, summarize webpage text.

    Parameters:
        url: Web address to retrieve.

    Returns:
        Extracted webpage text, an AI-generated summary for large pages, or an error message.
    """
    print(f"[Worker Agent] Fetching URL: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strip out scripts and styles before extracting text
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
            
        raw_text = soup.get_text(separator='\n', strip=True)
        
        # If it's a short page, just return it directly to save time
        if len(raw_text) < 8000:
            return raw_text
            
        print("[Worker Agent] Content is large. Summarizing before returning to main agent...")
        
        # The Map-Reduce summarization prompt
        prompt = f"""
        Extract the core information, main arguments, and key facts from the following webpage text. 
        Do not leave out important data. Provide a highly detailed summary.
        
        Webpage Text:
        {raw_text[:100000]} # Cap at 100k characters to prevent memory overflow
        """
        
        temp_chat = client.chats.create(model=WORKER_MODEL)
        summary_response = temp_chat.send_message(prompt)
        
        return f"[Summarized Webpage Content]:\n{summary_response.text}"
        
    except Exception as e:
        return f"Error fetching the URL: {str(e)}"