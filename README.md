# WebScraperX

A powerful web scraping and research tool that extracts content from any website and allows you to chat with the extracted information using AI.

![WebScraperX](https://img.shields.io/badge/Version-1.0.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Tech](https://img.shields.io/badge/Tech-React%20%7C%20FastAPI%20%7C%20Groq%20AI-orange)

## 🎯 Project Overview

**WebScraperX** is a full-stack web application that enables users to:
- Extract clean, structured content from any website
- View extracted content in a neat, card-based interface
- Ask questions about the extracted content using natural language
- Get AI-powered answers with exact source quotes

## ✨ Features

- **Smart Content Extraction**: Extracts text from websites while removing noise (navigation, footers, scripts)
- **Clean Card Interface**: Content displayed in numbered, well-aligned cards for easy reading
- **AI-Powered Q&A**: Ask questions about the extracted content and get accurate answers
- **Citation Highlighting**: See exactly which parts of the content were used to answer your questions
- **User Authentication**: Sign up/login functionality using Firebase Authentication
- **Chat History**: Save and reload your previous research sessions

## 🛠️ Tech Stack

**Frontend:**
- React (Vite)
- Firebase Authentication
- Lucide React Icons

**Backend:**
- FastAPI (Python)
- Groq AI (Llama-3.3-70B model)
- BeautifulSoup4
- CloudScraper

## 📋 Prerequisites

Before running this project, ensure you have:

- **Python 3.8+** installed
- **Node.js 16+** installed
- **Groq API Key** (Get one for free at [console.groq.com](https://console.groq.com))

## 🚀 Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Janani-12k/rag-chatbot.git
cd rag-chatbot
```

### 2. Backend Setup

Navigate to the backend folder and install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory with your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Start the backend server:

```bash
python app.py
# or
py app.py
```

The backend will run at `http://127.0.0.1:5000`

### 3. Frontend Setup

Open a new terminal and navigate to the frontend folder:

```bash
cd frontend
npm install
npm run dev
```

The frontend will run at `http://localhost:5173`

### 4. Firebase Setup (Optional)

This project uses Firebase for authentication. To enable full functionality:

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable **Authentication** with Email/Password provider
3. Enable **Firestore Database**
4. Replace the Firebase configuration in `frontend/src/firebase.js` with your own config

## 📖 Usage

1. **Sign Up**: Create a new account or sign in with an existing account
2. **Enter URL**: Paste any website URL in the input bar (e.g., `https://react.dev`)
3. **Extract**: Click the "Extract" button to scrape and process the content
4. **Ask Questions**: Type your research question in the chat input
5. **Get Answers**: Receive AI-powered answers with source citations

## 🧠 Solution Approach

### Content Extraction Pipeline

1. **Request**: Website URL is sent to the FastAPI backend
2. **Scraping**: CloudScraper bypasses bot protection; BeautifulSoup parses HTML
3. **Noise Removal**: Scripts, styles, nav, footer, and other non-content elements are removed
4. **Text Processing**: Content is split into logical chunks at sentence boundaries
5. **Deduplication**: Duplicate content is filtered out while preserving order

### AI Question Answering

1. **Relevant Chunks**: The system identifies the top 5 most relevant content chunks based on keyword matching
2. **Context Building**: Selected chunks are combined into a context prompt
3. **AI Response**: Groq's Llama model generates an answer based ONLY on the provided context
4. **Quote Extraction**: The AI returns both an answer and the exact quote used as source

## 📁 Project Structure

```
rag-chatbot/
├── backend/
│   ├── app.py              # FastAPI backend application
│   ├── requirements.txt    # Python dependencies
│   └── .env                # Environment variables (API keys)
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React component
│   │   ├── App.css         # Application styles
│   │   ├── firebase.js     # Firebase configuration
│   │   └── main.jsx        # React entry point
│   ├── index.html          # HTML template
│   └── package.json         # Node.js dependencies
├── .gitignore             # Git ignore rules
└── README.md              # Project documentation
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check - "Backend is running with Groq AI" |
| POST | `/scrape` | Extract content from a URL |
| POST | `/ask` | Ask a question about extracted content |

### Example Request

```bash
# Scrape a website
curl -X POST http://127.0.0.1:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Ask a question
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "question": "What is this page about?"}'
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

## 👤 Author

**Janani**

---

⭐ If you found this project useful, please give it a star!
