# Legal MERN Chatbot

A full-stack legal question-answering system combining MERN stack with Retrieval-Augmented Generation (RAG) using hybrid search (BM25 + semantic vectors) and LLM-as-a-Judge evaluation.

## 🎯 Features

- **Hybrid Retrieval**: Combines BM25 lexical matching with semantic vector search (90% accuracy on legal queries)
- **Multi-turn Conversations**: Context-aware responses with automatic summarization
- **LLM-as-a-Judge Evaluation**: 5-dimension quality assessment (factual accuracy, legal reasoning, citation quality, clarity, completeness)
- **Token Budgeting**: Automatic context trimming to stay within API limits
- **Query Rewriting**: Rewrites ambiguous follow-up queries using conversation context
- **Debug Transparency**: Shows retrieved context and token usage for every response

## 📊 Performance

| Metric | Hybrid (BM25+Vector) | Vector-Only | Improvement |
|--------|---------------------|-------------|-------------|
| Easy Questions | 100% | 71.4% | +28.6% |
| Medium Questions | 69.2% | 76.9% | -7.7% |
| Hard Questions | 80% | 70% | +10% |
| **Overall** | **83.3%** | **72.9%** | **+10.4%** |

---

## 🏗️ Architecture

```
legal_mern_chatbot/
├── frontend/          # React UI
├── backend/           # Node.js/Express API
└── rag_service/       # Python RAG + FastAPI
    ├── data/          # PDF documents (Indian Constitution, UDHR)
    ├── src/           # RAG pipeline modules
    ├── vector_store/  # FAISS index + embeddings
    └── main.py        # FastAPI server
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** 16+ and npm
- **Python** 3.8+ with pip
- **MongoDB** I used MongoDB Compass
- **Groq API Key** 

---

## 📦 Installation

### 1. Clone Repository

```bash
git clone (https://github.com/NiharikaKondepudi/INDIERAG-Legal-Chatbot.git)
cd legal_mern_chatbot
```

### 2. Setup RAG Service (Python)

```bash
cd rag_service

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Create `rag_service/.env`:**
```env
MONGODB_URI=mongodb://local.../legal_mern
GROQ_API_KEY=groq_api_key
RAG_DATA_FOLDER=./data
PORT=8000
MODEL_MAX_TOKENS=6000
RESERVED_RESPONSE_TOKENS=1000
RETRIEVE_K=5
ENABLE_TURN_SUMMARIZATION=false
```

**Download Legal Documents:**

Place these PDFs in `rag_service/data/`:
1. [Indian Constitution](https://cdnbbsr.s3waas.gov.in/s380537a945c7aaa788ccfcdf1b99b5d8f/uploads/2023/05/2023050195.pdf)
2. [UDHR](https://www.ohchr.org/sites/default/files/UDHR/Documents/UDHR_Translations/eng.pdf)

**Start RAG Service:**
```bash
uvicorn main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","initialized":true}`

---

### 3. Setup Backend (Node.js)

```bash
cd ../backend

# Install dependencies
npm install
```

**Create `backend/.env`:**
```env
MONGODB_URI=mongodb://local...
JWT_SECRET=your_random_secret_key_here
PORT=5000
RAG_SERVICE_URL=http://localhost:8000
```

**Start Backend:**
```bash
npm run dev
```

Verify: `curl http://localhost:5000/health` → `{"ok":true}`

---

### 4. Setup Frontend (React)

```bash
cd ../frontend

# Install dependencies
npm install

# Start development server
npm start
```

Frontend runs on http://localhost:3000

---

## 🎮 Usage

### Web UI

1. **Register/Login** at http://localhost:3000
2. **Create Chat**: Click "+ New" button
3. **Ask Questions**: Type legal queries (e.g., "What is Article 21?")
4. **View Debug**: Click "🔍 Debug" to see retrieved context and token usage
5. **Enable Evaluation**: Check "Enable LLM-as-a-Judge" for quality scores

### API Endpoints

**RAG Service (Port 8000)**

```bash
# Health check
GET /health

# Initialize/rebuild vector store
POST /initialize
{
  "force_rebuild": true
}

# Create chat session
POST /sessions
{
  "user_id": "user123",
  "title": "Legal Query"
}

# Chat (with history)
POST /chat
{
  "session_id": "uuid",
  "query": "What is Article 21?",
  "include_history": true,
  "evaluate": false
}

# Reset session
POST /sessions/{session_id}/reset
```

**Backend (Port 5000)**

```bash
# Register
POST /api/auth/register
{
  "email": "user@example.com",
  "password": "password123"
}

# Login
POST /api/auth/login
{
  "email": "user@example.com",
  "password": "password123"
}

# List chats (requires auth token)
GET /api/chats
Headers: { "Authorization": "Bearer <token>" }

# Send message
POST /api/chats/{chatId}/messages
{
  "text": "What is Article 21?",
  "evaluate": false
}
```

---

## 🧪 Running Benchmark

Evaluate hybrid vs vector-only retrieval:

```bash
cd rag_service

# Ensure rag_service is running (port 8000)

# Run benchmark
python benchmark_retrieval.py
```

**Output:**
```
Running benchmark: Human Rights Legal RAG Benchmark
Total questions: 30

================================================================================
OVERALL RESULTS
================================================================================
Hybrid Retrieval Hit@3 Accuracy: 83.3% (25/30)
Vector-Only Hit@3 Accuracy:      72.9% (22/30)
Absolute Improvement:            +10.4%

BREAKDOWN BY DIFFICULTY
EASY    : Hybrid 100.0% | Vector 71.4% | Gain: +28.6%
MEDIUM  : Hybrid 69.2% | Vector 76.9% | Gain: -7.7%
HARD    : Hybrid 80.0% | Vector 70.0% | Gain: +10.0%
```

Results saved to `benchmark_results.json`

---

## 🔧 Configuration

### Adjust Hybrid Search Balance

Edit `rag_service/src/hybrid_retriever.py`:

```python
# In search() method, adjust alpha (0-1)
# alpha=0.9 → 90% vector, 10% BM25
# alpha=0.5 → 50% vector, 50% BM25
def search(self, query: str, k: int = 5, alpha: float = 0.6):
    # ...existing code...
```

### Toggle Turn-by-Turn Summarization

```env
# In rag_service/.env
ENABLE_TURN_SUMMARIZATION=true  # Doubles Groq API calls but saves tokens long-term
```

### Adjust Token Limits

```env
MODEL_MAX_TOKENS=6000           # Total tokens available for context
RESERVED_RESPONSE_TOKENS=1000   # Reserved for model response
RETRIEVE_K=5                    # Number of chunks to retrieve
```

---

## 📁 Project Structure

```
legal_mern_chatbot/
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.js   # Main chat UI
│   │   │   ├── Dashboard.js    # Chat list
│   │   │   └── Navbar.js
│   │   ├── services/
│   │   │   └── api.js          # API client
│   │   └── App.js
│   └── package.json
├── backend/                    # Node.js backend
│   ├── controllers/
│   │   ├── authController.js
│   │   └── chatController.js   # Forwards to RAG service
│   ├── models/
│   │   ├── User.js
│   │   └── Conversation.js     # Stores messages + ragSessionId
│   ├── routes/
│   ├── middleware/
│   │   └── auth.js
│   └── server.js
└── rag_service/                # Python RAG engine
    ├── src/
    │   ├── rag_pipeline.py     # Main RAG orchestrator
    │   ├── hybrid_retriever.py # BM25 + Vector fusion
    │   ├── vector_store.py     # FAISS + embeddings
    │   ├── conversation_manager.py  # Mongo-backed history
    │   ├── legal_evaluator.py  # LLM-as-a-Judge
    │   └── document_processor.py
    ├── data/                   # PDFs go here
    ├── vector_store/           # Generated FAISS index
    ├── benchmark_queries.json  # 30 legal Q&A pairs
    ├── benchmark_retrieval.py  # Evaluation script
    ├── main.py                 # FastAPI server
    └── requirements.txt
```

---

## 🗄️ MongoDB Collections

**Backend Database (`legal_mern`)**
- `users`: User accounts
- `conversations`: Chat sessions with messages array

**RAG Service Database (`rag_service`)**
- `sessions`: RAG session metadata
- `messages`: User/assistant messages with debug info
- `conversation_summaries`: Auto-generated summaries
- `evaluations`: LLM-as-a-Judge scores

---

## 📚 Tech Stack

- **Frontend**: React, Axios
- **Backend**: Node.js, Express, JWT, Mongoose
- **RAG Service**: Python, FastAPI, FAISS, Sentence-Transformers, Groq LLM
- **Database**: MongoDB Compass
- **Search**: Hybrid (BM25 via `rank-bm25` + Semantic via `sentence-transformers`)
- **LLM**: Llama 3.1 8B via Groq API

---



## 🙏 Acknowledgments

- Indian Constitution text from [India.gov.in](https://www.india.gov.in)
<!-- - UDHR from [UN.org](https://www.un.org) -->
- Groq for fast LLM inference
- MongoDB Compass for database hosting
