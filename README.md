# StudyFlow — Smart Study Planner with Ollama AI

## 🤖 4 AI Features (100% Free, Local, No Internet Required)

| Feature | Where | What it does |
|---|---|---|
| **Floating AI Chat** | Every page (🤖 button) | Ask anything — study tips, concepts, motivation |
| **Topic AI Tips** | Topics page (✨ AI Tips button) | 5 actionable study tips per topic |
| **Schedule Insights** | Schedule page (auto-loads) | Workload analysis & improvement suggestions |
| **Dashboard AI Advisor** | Dashboard (auto-loads) | Personalised daily focus plan |

---

## ⚡ Quick Start

### 1. Install Ollama (one-time)
```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download installer from https://ollama.com/download
```

### 2. Pull a model
```bash
ollama pull llama3.2        # recommended (~2GB, fast)
# or
ollama pull mistral         # alternative
```

### 3. Start Ollama
```bash
ollama serve
# Keep this terminal open
```

### 4. Run the app
```bash
pip install flask
python app.py
# Open http://localhost:5000
```

---

## 🔧 Change the AI Model
Edit `app.py` line:
```python
OLLAMA_MODEL = "llama3.2"   # change to any installed model
```

List installed models: `ollama list`

## 💡 Works Offline
After setup, everything runs locally — no API keys, no costs, no data leaves your machine.
