import os
import json
import asyncio
import pathlib 
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="AI Mock Interview Coach")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROLES = {
    "software_engineer": {"label": "Software Engineer", "topics": ["Data Structures & Algorithms", "System Design", "OOP"], "icon": "💻"},
    "data_engineer":     {"label": "Data Engineer",     "topics": ["SQL & Databases", "ETL Pipelines", "Big Data"],        "icon": "🗄️"},
    "ml_engineer":       {"label": "ML Engineer",       "topics": ["Machine Learning", "Model Deployment", "Statistics"],  "icon": "🤖"},
    "cloud_engineer":    {"label": "Cloud Engineer",    "topics": ["AWS Services", "IaC", "Containerization"],             "icon": "☁️"},
    "cybersecurity":     {"label": "Cybersecurity Analyst", "topics": ["Network Security", "Threat Analysis", "OWASP"],    "icon": "🛡️"},
    "product_manager":   {"label": "Product Manager",   "topics": ["Product Strategy", "User Research", "Agile"],         "icon": "📊"},
}

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

def groq_headers():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

def groq_chat(prompt: str, max_tokens: int = 500) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    resp = requests.post(GROQ_URL, headers=groq_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Groq error: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

class QuestionRequest(BaseModel):
    role: str
    difficulty: str
    question_type: str = "behavioral"

class EvaluateRequest(BaseModel):
    role: str
    question: str
    answer: str
    question_type: str = "behavioral"

@app.get("/api/health")
def health():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    return {"status": "ok", "key_set": bool(api_key), "key_prefix": api_key[:8] if api_key else "NOT SET"}

@app.get("/api/roles")
def get_roles():
    return ROLES

@app.post("/api/generate-question")
async def generate_question(req: QuestionRequest):
    role_label = ROLES.get(req.role, {}).get("label", req.role)
    if req.question_type == "behavioral":
        prompt = f'Generate ONE {req.difficulty} behavioral interview question for a {role_label}. Return ONLY valid JSON no markdown: {{"question":"...","hint":"one-line tip","type":"behavioral","follow_up":"one follow-up"}}'
    else:
        prompt = f'Generate ONE {req.difficulty} technical interview question for a {role_label}. Return ONLY valid JSON no markdown: {{"question":"...","hint":"one-line tip","type":"technical","follow_up":"one follow-up"}}'
    try:
        text = groq_chat(prompt, max_tokens=500)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return data
    except json.JSONDecodeError:
        return {"question": text, "hint": "Think carefully.", "type": req.question_type, "follow_up": ""}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/evaluate")
async def evaluate_answer(req: EvaluateRequest):
    role_label = ROLES.get(req.role, {}).get("label", req.role)
    if req.question_type == "behavioral":
        prompt = f"""You are a senior {role_label} interviewer. Evaluate using STAR method.
Question: {req.question}
Answer: {req.answer}
Cover: 1. **STAR Score** (X/10) 2. **Strengths** 3. **Areas to Improve** 4. **Stronger Version** 5. **Overall Score** X/10"""
    else:
        prompt = f"""You are a senior {role_label} technical interviewer.
Question: {req.question}
Answer: {req.answer}
Cover: 1. **Technical Accuracy** (X/10) 2. **What They Got Right** 3. **Gaps & Errors** 4. **Ideal Answer** 5. **Overall Score** X/10"""

    async def stream():
        try:
            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7,
                "stream": True,
            }
            api_key = os.environ.get("GROQ_API_KEY", "").strip()
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            with requests.post(GROQ_URL, headers=headers, json=payload, stream=True, timeout=60) as resp:
                for line in resp.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                obj = json.loads(data)
                                text = obj["choices"][0]["delta"].get("content", "")
                                if text:
                                    yield f"data: {json.dumps({'text': text})}\n\n"
                                    await asyncio.sleep(0)
                            except:
                                pass
        except Exception as e:
            yield f"data: {json.dumps({'text': f'Error: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

frontend_path = pathlib.Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")