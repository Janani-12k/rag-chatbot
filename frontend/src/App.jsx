import { useState, useEffect, useRef } from "react"; 
import { collection, addDoc, getDocs, query, orderBy, doc, deleteDoc, where } from "firebase/firestore";
import { onAuthStateChanged, signOut, signInWithEmailAndPassword, createUserWithEmailAndPassword } from "firebase/auth";
import { db, auth } from "./firebase";
import { Globe, Plus, LogOut, Send, Search, Trash2, User } from "lucide-react";
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [messages, setMessages] = useState([]); 
  const [url, setUrl] = useState(""); 
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [chunks, setChunks] = useState([]);
  const [pageTitle, setPageTitle] = useState("");
  const [highlightedChunks, setHighlightedChunks] = useState([]);
  const [exactQuote, setExactQuote] = useState("");
  const [toast, setToast] = useState({ show: false, message: "", type: "" });
  const messagesEndRef = useRef(null);

  // Auto scroll for chat messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  useEffect(() => {
    if (highlightedChunks.length > 0) {
      // Small timeout to ensure the DOM has updated with the new highlights
      const timer = setTimeout(() => {
        // First try to find the exact highlight span
        let targetElement = document.querySelector('.exact-highlight');
        
        // Fallback to the highlighted chunk container if no exact span found
        if (!targetElement) {
          targetElement = document.querySelector('.highlighted-chunk');
        }

        if (targetElement) {
          targetElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
          });
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [highlightedChunks, exactQuote]);

  const showToast = (message, type = "error") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast({ show: false, message: "", type: "" }), 3000);
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      if (currentUser) {
        fetchHistory(currentUser.uid);
      } else {
        setChatHistory([]);
      }
    });
    return () => unsubscribe();
  }, []);

  const fetchHistory = async (userId) => {
    try {
      const q = query(
        collection(db, "chats"), 
        where("userId", "==", userId)
      );
      const querySnapshot = await getDocs(q);
      let chats = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      
      // Manual sorting to avoid index requirement
      chats.sort((a, b) => {
        const timeA = a.timestamp?.seconds || 0;
        const timeB = b.timestamp?.seconds || 0;
        return timeB - timeA;
      });

      setChatHistory(chats);
    } catch (err) {
      console.error("Error fetching chat history:", err);
      showToast("Could not load history. You might need to create a Firestore Index.");
    }
  };

  const handleEmailAuth = async (e) => {
    e.preventDefault();
    setAuthError("");
    if (!email || !password) {
      setAuthError("Please enter email and password.");
      return;
    }
    try {
      if (isLoginMode) {
        await signInWithEmailAndPassword(auth, email, password);
        showToast("Sign In Successful!", "success");
      } else {
        if (password !== confirmPassword) {
          setAuthError("Passwords do not match.");
          return;
        }
        await createUserWithEmailAndPassword(auth, email, password);
        showToast("Signup Successful!", "success");
      }
      setEmail("");
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      let errorMessage = "An error occurred. Please try again.";
      if (err.code === 'auth/wrong-password') {
        errorMessage = "Incorrect password. Please try again.";
      } else if (err.code === 'auth/user-not-found') {
        errorMessage = "No account found with this email.";
      } else if (err.code === 'auth/email-already-in-use') {
        errorMessage = "This email is already registered.";
      } else if (err.code === 'auth/invalid-email') {
        errorMessage = "Invalid email format.";
      } else if (err.code === 'auth/weak-password') {
        errorMessage = "Password should be at least 6 characters.";
      }
      setAuthError(errorMessage);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut(auth);
      setUrl("");
      setMessages([]);
      setChunks([]);
      setHighlightedChunks([]);
      setExactQuote("");
    } catch (err) {
      showToast("Sign out failed.");
    }
  };

  const handleScrape = async () => { 
    if (!url) {
      showToast("Please enter a URL.");
      return;
    }
    setLoading(true);
    setMessages([]);
    setChunks([]);
    setPageTitle("");
    setHighlightedChunks([]);
    setExactQuote("");
    try {
      // Using the production Render URL as the default backend for testing
      const API_BASE = "https://rag-chatbot-ep72.onrender.com";

      console.log(`DEBUG: Scraping ${url} using ${API_BASE}`);
      
      const res = await fetch(`${API_BASE}/scrape`, { 
        method: "POST", 
        headers: { "Content-Type": "application/json" }, 
        body: JSON.stringify({ url }), 
      }); 
      
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}: ${res.statusText}`);
      }

      const data = await res.json(); 
      console.log("DEBUG: Received data:", data);

      if (data.paragraphs && data.paragraphs.length > 0) {
        setChunks(data.paragraphs);
        setPageTitle(data.title || "Extracted Content");
        setMessages([{ type: "bot", text: "Knowledge extracted! What would you like to know about this site?" }]);
      } else if (data.paragraphs && data.paragraphs.length === 0) {
        setMessages([{ type: "bot", text: "I couldn't find much text on this page. Try a different URL or one with more content." }]);
      } else if (data.error) {
        setMessages([{ type: "bot", text: "Error: " + data.error }]);
      } else {
        setMessages([{ type: "bot", text: "Received an unexpected response from the server." }]);
      }
    } catch (err) {
      console.error("DEBUG: Scrape error:", err);
      showToast(`Connection error: ${err.message}`);
      setMessages([{ type: "bot", text: "Failed to connect to the backend server. Make sure it's running." }]);
    } finally {
      setLoading(false);
    }
  }; 

  const handleAsk = async () => {
    if (!question) return;

    const userQ = question;
    setQuestion("");
    // Push the user message immediately for real-time bubbles
    setMessages(prev => [...prev, { type: "user", text: userQ }]);
    setChatLoading(true);

    try {
      const API_BASE = "https://rag-chatbot-ep72.onrender.com";

      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          url,
          question: userQ 
        }),
      });
      
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();

      if (data.answer) {
        setMessages(prev => [...prev, { 
          type: "bot", 
          text: data.answer,
          exact_quote: data.exact_quote
        }]);
        
        if (data.sources) {
          setHighlightedChunks(data.sources);
        } else {
          setHighlightedChunks([]);
        }
        
        if (data.exact_quote) {
          setExactQuote(data.exact_quote);
        } else {
          setExactQuote("");
        }

        // Save to Firebase
        try {
          const newChat = {
            userId: user.uid,
            url,
            question: userQ,
            answer: data.answer,
            sources: data.sources || [],
            exact_quote: data.exact_quote || "",
            timestamp: new Date()
          };
          const docRef = await addDoc(collection(db, "chats"), newChat);
          setChatHistory(prev => [{ id: docRef.id, ...newChat }, ...prev]);
        } catch (err) {
          console.error("Error saving chat:", err);
        }
      } else if (data.error) {
        setMessages(prev => [...prev, { type: "bot", text: "Error: " + data.error }]);
      }
    } catch (err) {
      showToast("Error connecting to server.");
    } finally {
      setChatLoading(false);
    }
  };

  const loadOldChat = async (chat) => {
    if (historyLoading) return;
    
    setUrl(chat.url);
    setMessages([
      { type: "user", text: chat.question },
      { type: "bot", text: chat.answer, exact_quote: chat.exact_quote }
    ]);
    
    setChunks([]); // clear old chunks while loading new ones
    setPageTitle(chat.title || "");
    setHighlightedChunks(chat.sources || []);
    setExactQuote(chat.exact_quote || "");
    if (chat.url) {
      setHistoryLoading(true);
      // Re-fetch the content silently in the background
      try {
        const API_BASE = "https://rag-chatbot-ep72.onrender.com";

        const res = await fetch(`${API_BASE}/scrape`, { 
          method: "POST", 
          headers: { "Content-Type": "application/json" }, 
          body: JSON.stringify({ url: chat.url }), 
        }); 
        
        if (!res.ok) {
          throw new Error(`Server returned ${res.status}: ${res.statusText}`);
        }

        const data = await res.json(); 
        if (data.paragraphs) {
          setChunks(data.paragraphs);
          setPageTitle(data.title || chat.title || "Extracted Content");
        }
      } catch (err) {
        console.error("Could not fetch chunks for history item", err);
      } finally {
        setHistoryLoading(false);
      }
    }
  };

  const startNewChat = () => {
    setUrl("");
    setQuestion("");
    setMessages([]);
    setChunks([]);
    setPageTitle("");
    setHighlightedChunks([]);
    setExactQuote("");
  };

  // Helper to render text with specific yellow highlight
  const renderText = (text, quote) => {
    if (!quote || !text || text.indexOf(quote) === -1) return text;
    const parts = text.split(quote);
    return (
      <>
        {parts[0]}
        <span className="exact-highlight">{quote}</span>
        {parts.slice(1).join(quote)}
      </>
    );
  };

  const handleDeleteChat = async (e, chatId) => {
    e.stopPropagation();
    try {
      await deleteDoc(doc(db, "chats", chatId));
      setChatHistory(prev => prev.filter(c => c.id !== chatId));
    } catch (err) {
      console.error("Error deleting chat:", err);
      showToast("Failed to delete chat.");
    }
  };

  if (!user) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '15px' }}>
            <Globe size={48} color="#60a5fa" />
          </div>
          <h2>{isLoginMode ? "Sign In" : "Sign Up"}</h2>
          <p className="auth-subtitle">{isLoginMode ? "Login to access your web research and extraction tools" : "Join WebScraperX to start extracting insights from the web"}</p>
          
          {authError && <div className="auth-error-msg">{authError}</div>}

          <form onSubmit={handleEmailAuth} className="auth-form">
            <div className="input-group">
              <label>Email</label>
              <input 
                type="email" 
                placeholder="you@example.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            
            <div className="input-group">
              <label>Password</label>
              <input 
                type="password" 
                placeholder="••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {!isLoginMode && (
              <div className="input-group">
                <label>Confirm Password</label>
                <input 
                  type="password" 
                  placeholder="••••••••" 
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
            )}

            <button type="submit" className="login-btn">
              {isLoginMode ? "Sign In" : "Sign Up"}
            </button>
          </form>

          <div className="auth-toggle">
            {isLoginMode ? (
              <p>Need an account? <span onClick={() => setIsLoginMode(false)}>Sign Up</span></p>
            ) : (
              <p>Already have an account? <span onClick={() => setIsLoginMode(true)}>Log In</span></p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      {/* Toast Notification */}
      {toast.show && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}

      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', marginBottom: '10px' }}>
            <Globe size={28} color="#60a5fa" />
            <h2 style={{ margin: 0 }}>WebScraperX</h2>
          </div>
          <div className="user-info">
             <img src={user.photoURL || `https://ui-avatars.com/api/?name=${user.email}&background=random`} alt={user.displayName || user.email} />
             <span style={{ overflow: "hidden", textOverflow: "ellipsis", fontWeight: '500' }}>{user.displayName || user.email}</span>
          </div>
        </div>
        <button className="new-chat" onClick={startNewChat}>
          <Plus size={18} />
          New Chat
        </button>

        <h3 style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "12px", marginTop: "15px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.1em" }}>History</h3>
        <div className="chat-list">
          {chatHistory.map((chat) => (
            <div key={chat.id} className={`chat-item ${historyLoading && url === chat.url ? 'loading' : ''}`} onClick={() => loadOldChat(chat)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, paddingRight: "10px" }} title={chat.question}>
                {chat.question}
              </div>
              {historyLoading && url === chat.url ? (
                <div className="mini-spinner"></div>
              ) : (
                <button 
                  onClick={(e) => handleDeleteChat(e, chat.id)}
                  style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
                  title="Delete chat"
                  onMouseOver={(e) => e.currentTarget.style.color = '#ef4444'}
                  onMouseOut={(e) => e.currentTarget.style.color = '#64748b'}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
        <button onClick={handleSignOut} className="signout-btn">
          <LogOut size={18} />
          Sign Out
        </button>
      </div>

      {/* Main Chat Area */}
      <div className="chat-area">
        <div className="glass-card">
          {/* URL Input */}
          <div className="url-bar">
            <Search size={20} color="#94a3b8" />
            <input 
              type="text" 
              placeholder="Paste website URL to analyze..." 
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              style={{ marginLeft: '10px' }}
            />
            <button onClick={handleScrape} disabled={loading}>
              {loading ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div className="mini-spinner"></div>
                  <span>Scraping...</span>
                </div>
              ) : "Extract"}
            </button>
          </div>

          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
            {/* Chat Column */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              {/* Messages */}
              <div className="messages">
                {messages.length === 0 && !loading && (
                   <div style={{ margin: "auto", color: "#64748b", textAlign: "center", maxWidth: '300px' }}>
                     <Globe size={48} style={{ marginBottom: '15px', opacity: 0.2 }} />
                     <p>Paste a URL above and Extract Info to start your research journey.</p>
                   </div>
                )}
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    className={msg.type === "user" ? "user-msg" : "bot-msg"}
                  >
                    <div className="msg-text">
                      {msg.type === "bot" ? renderText(msg.text, msg.exact_quote) : msg.text}
                    </div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="bot-msg">
                    <div className="typing-indicator">
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Box */}
              <div className="input-box">
                <input 
                  type="text" 
                  placeholder="Ask a question about the content..." 
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleAsk(); }}
                />
                <button onClick={handleAsk} disabled={chatLoading || !url}>
                  <Send size={18} />
                  Send
                </button>
              </div>
            </div>

            {/* Extracted Knowledge Sidebar */}
            {chunks.length > 0 && (
              <div className="extracted-sidebar">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '1rem', margin: 0, color: '#e2e8f0', fontWeight: '700' }}>Extracted Knowledge</h3>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {chunks.map((p, i) => {
                    const isHighlighted = highlightedChunks.includes(p);
                    
                    return (
                      <div 
                        key={i} 
                        className={`extracted-chunk ${isHighlighted ? "highlighted-chunk" : ""}`}
                      >
                        <span className="chunk-index">{i + 1}</span>
                        <div className="chunk-text">
                          {isHighlighted ? renderText(p, exactQuote) : p}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
