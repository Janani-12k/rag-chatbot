from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import re
import urllib3
import os
from groq import Groq
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

# Load environment variables
load_dotenv()

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq (FREE AI)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# Store Chunks (GLOBAL) - mapping URL to metadata and chunks
url_data_cache = {}

class ScrapeRequest(BaseModel):
    url: str

class QuestionRequest(BaseModel):
    url: str
    question: str

def clean_text(text: str) -> str:
    if not text:
        return ""
    # Remove excessive newlines/tabs but keep single ones if they separate content
    text = re.sub(r'[\t\r]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    if not text:
        return []
    
    # Pre-clean text but keep it as blocks
    text = clean_text(text)
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        # Initial end point
        end = start + chunk_size
        
        # If we are not at the end of the string, look for a sentence break
        if end < text_len:
            # Look for the last sentence-ending punctuation within the chunk
            # Looking at a wider range to find a good break point
            search_range = text[max(start, end - 200):end + 100]
            last_break = -1
            # Prioritize paragraph breaks, then sentence breaks
            for punct in ['\n\n', '\n', '. ', '! ', '? ']:
                idx = search_range.rfind(punct)
                if idx > last_break:
                    last_break = idx
            
            if last_break != -1:
                # Adjust 'end' to the punctuation + space
                end = max(start, end - 200) + last_break + len(punct.strip()) + 1
            else:
                # Fallback to last space if no punctuation found
                last_space = text.rfind(' ', start, end)
                if last_space != -1 and last_space > start:
                    end = last_space
        
        chunk = text[start:end].replace('\n', ' ').strip()
        if len(chunk) > 30: # Only add substantial chunks
            chunks.append(chunk)
        
        # Move start forward to the end of the current chunk (no overlap)
        start = end
            
    # Deduplicate in case overlapping caused exact same chunks
    return list(dict.fromkeys(chunks))

def get_relevant_chunks(question: str, chunks: list[str], top_k: int = 5) -> list[str]:
    if not chunks:
        return []
    
    # Common English stopwords to ignore for better matching
    stopwords = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being", 
                 "in", "on", "at", "to", "for", "with", "by", "about", "against", 
                 "between", "into", "through", "during", "before", "after", "above", 
                 "below", "from", "up", "down", "out", "off", "over", "under", "again", 
                 "further", "then", "once", "here", "there", "when", "where", "why", 
                 "how", "all", "any", "both", "each", "few", "more", "most", "other", 
                 "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
                 "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"}
    
    q_words = [w for w in re.findall(r'\w+', question.lower()) if w not in stopwords]
    if not q_words:
        # If all words were stopwords, fallback to basic word match
        q_words = re.findall(r'\w+', question.lower())
        
    scored_chunks = []
    for chunk in chunks:
        c_words = set(re.findall(r'\w+', chunk.lower()))
        # Score based on how many unique question words appear in the chunk
        score = sum(1 for word in q_words if word in c_words)
        scored_chunks.append((score, chunk))
        
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    # Filter out zero-score chunks if possible, but keep at least one if we have chunks
    results = [c[1] for c in scored_chunks if c[0] > 0]
    if not results:
        return chunks[:top_k]
    return results[:top_k]

def get_selenium_content(url: str) -> str:
    """Fallback scraper using Selenium Headless Chrome"""
    print(f"DEBUG: Attempting Selenium Fallback for {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # Anti-detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = None
    try:
        # Check if running on Render (Render has chrome binary at specific location)
        # For Render, we often need to specify the binary location if not in path
        chrome_bin = os.getenv("CHROME_BINARY_PATH")
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
            
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Additional anti-detection: execute CDP command to hide automation
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        driver.get(url)
        
        # Wait for body to be present (max 20 seconds)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Extra wait for dynamic content
        time.sleep(3) 
        
        html = driver.page_source
        print(f"DEBUG: Selenium successfully extracted {len(html)} bytes")
        return html
    except Exception as e:
        print(f"DEBUG: Selenium fallback failed: {e}")
        return ""
    finally:
        if driver:
            driver.quit()

@app.get("/")
async def home():
    return {"message": "Backend is running with Groq AI"}

@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    url = req.url
    if not url:
        raise HTTPException(status_code=400, detail="No URL provided")

    try:
        # Check cache first
        if url in url_data_cache:
            print(f"DEBUG: Serving {url} from cache")
            return {
                "paragraphs": url_data_cache[url]["chunks"],
                "title": url_data_cache[url]["title"]
            }

        print(f"DEBUG: Scraping {url}...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

        response = None
        try:
            # Using curl_cffi to bypass bot protection - Profile 1
            print(f"DEBUG: Attempting curl_cffi (Chrome 120) for {url}")
            response = curl_requests.get(url, impersonate="chrome120", timeout=30)
        except Exception as e:
            print(f"DEBUG: curl_cffi Profile 1 failed: {e}")
            
        if not response or response.status_code != 200:
            try:
                # Retry with Profile 2
                print(f"DEBUG: Retrying curl_cffi (Edge 101) for {url}")
                response = curl_requests.get(url, impersonate="edge101", timeout=30)
            except Exception as e:
                print(f"DEBUG: curl_cffi Profile 2 failed: {e}")

        if not response or response.status_code != 200:
            # Final fallback to standard requests
            target_url = url if url.startswith(('http://', 'https://')) else 'https://' + url
            try:
                print(f"DEBUG: Final fallback to standard requests for {target_url}")
                response = requests.get(target_url, timeout=30, verify=False, headers=headers)
            except Exception as req_e:
                print(f"DEBUG: Standard requests fallback failed for {target_url}: {req_e}")
                # Don't return yet, let it fall through to Selenium
                response = None 
            
        if not response or response.status_code != 200 or not response.text or len(response.text.strip()) < 100:
            # All normal scraping failed, trigger Selenium Fallback
            selenium_html = get_selenium_content(url)
            if selenium_html:
                soup = BeautifulSoup(selenium_html, "html.parser")
            else:
                # If both fail, return original error or a clean message
                error_msg = "All scraping attempts failed. This website might have very strict bot protection."
                if not response:
                    error_msg += " (No response received)"
                elif response.status_code != 200:
                    error_msg += f" (Status code: {response.status_code})"
                return {"error": error_msg}
        else:
            soup = BeautifulSoup(response.text, "html.parser")

        # Extract Title
        page_title = soup.title.string if soup.title else "Unknown Website"
        page_title = clean_text(page_title)

        # Check if body exists
        if not soup.body:
            return {"error": "The website appears to have no readable content (no body tag found)."}

        # Remove noise elements
        for noise in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "svg", "path", "iframe"]):
            noise.decompose()

        # Extract content from natural block-level elements
        raw_blocks = []
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'article', 'section', 'div', 'span']):
            text = clean_text(tag.get_text(strip=True))
            # Lowered threshold and added length limit to avoid massive chunks
            if 30 < len(text) < 2000: 
                raw_blocks.append(text)
        
        # Fallback if no specific tags found
        if not raw_blocks:
            print("DEBUG: No semantic tags found, falling back to body text")
            text = clean_text(soup.body.get_text(separator=' '))
            raw_blocks = [text[i:i+500] for i in range(0, len(text), 500)]

        # Deduplicate while preserving order
        unique_raw = []
        seen = set()
        for b in raw_blocks:
            if b.lower() not in seen:
                unique_raw.append(b)
                seen.add(b.lower())

        # Professional Grouping Logic: Merge small consecutive blocks
        # This keeps headings with their paragraphs and lists together in one card.
        professional_chunks = []
        current_group = ""
        
        for block in unique_raw:
            # If current group is empty, start it
            if not current_group:
                current_group = block
            # If adding this block doesn't exceed a reasonable card size (700 chars), merge it
            elif len(current_group) + len(block) < 700:
                current_group += "\n\n" + block
            # Otherwise, save the current group and start a new one
            else:
                # If the group is long enough, split it properly at sentence boundaries
                if len(current_group) > 800:
                    professional_chunks.extend(chunk_text(current_group, chunk_size=600))
                else:
                    professional_chunks.append(current_group)
                current_group = block
        
        # Add the last group
        if current_group:
            if len(current_group) > 800:
                professional_chunks.extend(chunk_text(current_group, chunk_size=600))
            else:
                professional_chunks.append(current_group)

        # Final cleanup and limit to top 25 high-quality chunks
        paragraphs = [p.replace('\n\n', ' ') for p in professional_chunks if len(p) > 60][:25]
        
        print(f"DEBUG: Extracted {len(paragraphs)} high-quality professional chunks from {url}")
        
        # Keep semantic paragraphs for AI (global store)
        url_data_cache[url] = {
            "chunks": paragraphs,
            "title": page_title
        }

        # Return paragraphs for a more natural UI display
        return {
            "paragraphs": paragraphs,
            "title": page_title
        }

    except Exception as e:
        print(f"DEBUG: Scrape error for {url}: {e}")
        return {"error": str(e)}

@app.post("/ask")
async def ask(req: QuestionRequest):
    url = req.url
    question = req.question
    
    # Retrieve data for this specific URL
    cached_data = url_data_cache.get(url)
    
    if not cached_data:
        return {"error": "No context available for this URL. Please scrape it first."}

    stored_chunks = cached_data["chunks"]
    page_title = cached_data["title"]

    try:
        # Get top relevant chunks
        relevant_chunks = get_relevant_chunks(question, stored_chunks, top_k=5)
        
        # Combine relevant paragraphs for full context
        context = "\n".join(relevant_chunks)
        
        # Use Groq for the chat completion with a better prompt
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"You are WebScraperX, an advanced AI Website Knowledge Assistant. Your goal is to provide rich, detailed, and natural-sounding answers based ONLY on the provided context from the website '{page_title}'. \n\n"
                               "Guidelines:\n"
                               "- If the information is available, provide a comprehensive explanation (2-4 sentences).\n"
                               "- Use a professional and helpful tone.\n"
                               "- Do not mention 'the context' or 'the provided text' in your answer.\n"
                               "- You must respond in valid JSON format with two keys: 'answer' (your rich answer) and 'exact_quote' (the exact verbatim substring from the context that contains the key information)."
                },
                {
                    "role": "user",
                    "content": f"Context from {page_title}:\n{context}\n\nQuestion: {question}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3, # Slightly higher temperature for more natural flow
            max_tokens=800,
        )
        
        import json
        response_data = json.loads(completion.choices[0].message.content)
        answer = response_data.get("answer", "I don't know based on the website content.")
        exact_quote = response_data.get("exact_quote", "")
        
        return {
            "answer": answer, 
            "sources": relevant_chunks, 
            "exact_quote": exact_quote,
            "title": page_title
        }
        
    except Exception as e:
        print(f"DEBUG: Ask error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000)
