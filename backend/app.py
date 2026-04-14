from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import cloudscraper
from bs4 import BeautifulSoup
import re
import urllib3
import os
from groq import Groq
from dotenv import load_dotenv

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

# Store Chunks (GLOBAL) - mapping URL to list of paragraphs
url_chunks_cache = {}

class ScrapeRequest(BaseModel):
    url: str

class QuestionRequest(BaseModel):
    url: str
    question: str

def clean_text(text: str) -> str:
    # Remove multiple spaces, newlines, and tabs
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    if not text:
        return []
    
    # Pre-clean text
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
            # Looking at a slightly wider range to find a good break point
            search_range = text[max(start, end - 150):end + 50]
            last_break = -1
            for punct in ['. ', '! ', '? ', '\n']:
                idx = search_range.rfind(punct)
                if idx > last_break:
                    last_break = idx
            
            if last_break != -1:
                # Adjust 'end' to the punctuation + space
                end = max(start, end - 150) + last_break + 1
            else:
                # Fallback to last space if no punctuation found
                last_space = text.rfind(' ', start, end)
                if last_space != -1 and last_space > start:
                    end = last_space
        
        chunk = text[start:end].strip()
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
        if url in url_chunks_cache:
            print(f"DEBUG: Serving {url} from cache")
            return {
                "paragraphs": url_chunks_cache[url]
            }

        print(f"DEBUG: Scraping {url}...")
        
        # Using cloudscraper to bypass bot protection
        scraper = cloudscraper.create_scraper()
        try:
            response = scraper.get(url, timeout=10)
        except Exception as e:
            print(f"DEBUG: Cloudscraper failed, trying standard requests: {e}")
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            response = requests.get(url, timeout=10, verify=False)
            
        if not response or not response.text:
            return {"error": "Could not retrieve any content from this URL."}

        soup = BeautifulSoup(response.text, "html.parser")

        # Check if body exists
        if not soup.body:
            return {"error": "The website appears to have no readable content (no body tag found)."}

        # Remove noise elements
        for noise in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "svg", "path", "iframe"]):
            noise.decompose()

        # Get all text from body with newline separator to preserve paragraph breaks
        body_text = soup.body.get_text(separator='\n', strip=True)
        
        # Split into potential paragraphs by newlines
        lines = [clean_text(line) for line in body_text.split('\n')]
        
        # Filter and process lines
        unique_blocks = []
        seen = set()
        for line in lines:
            if len(line) < 30: # Skip very short snippets
                continue
                
            if line.lower() not in seen:
                # If a block is too long, split it into smaller, manageable chunks
                if len(line) > 500:
                    sub_chunks = chunk_text(line, chunk_size=450)
                    for sc in sub_chunks:
                        if sc.lower() not in seen:
                            unique_blocks.append(sc)
                            seen.add(sc.lower())
                else:
                    unique_blocks.append(line)
                    seen.add(line.lower())

        # Final cleanup and limit to 50 chunks
        paragraphs = unique_blocks[:50]
        
        print(f"DEBUG: Extracted {len(paragraphs)} chunks from {url}")
        
        # Keep semantic paragraphs for AI (global store)
        url_chunks_cache[url] = paragraphs

        # Return paragraphs for a more natural UI display
        return {
            "paragraphs": paragraphs
        }

    except Exception as e:
        print(f"DEBUG: Scrape error for {url}: {e}")
        return {"error": str(e)}

@app.post("/ask")
async def ask(req: QuestionRequest):
    url = req.url
    question = req.question
    
    # Retrieve chunks for this specific URL
    stored_chunks = url_chunks_cache.get(url)
    
    if not stored_chunks:
        return {"error": "No context available for this URL. Please scrape it first."}

    try:
        # Get top relevant chunks
        relevant_chunks = get_relevant_chunks(question, stored_chunks, top_k=5)
        
        # Combine relevant paragraphs for full context
        context = "\n".join(relevant_chunks)
        
        # Use Groq for the chat completion
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Answer the user's question based ONLY on the provided context. You must respond in valid JSON format with two keys: 'answer' (your concise answer) and 'exact_quote' (the exact verbatim substring from the context that contains the answer. If you cannot find an exact quote, return an empty string)."
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=500,
        )
        
        import json
        response_data = json.loads(completion.choices[0].message.content)
        answer = response_data.get("answer", "I don't know based on the website content.")
        exact_quote = response_data.get("exact_quote", "")
        
        return {"answer": answer, "sources": relevant_chunks, "exact_quote": exact_quote}
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
