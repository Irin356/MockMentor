import os
import json
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

# Groq shut down llama-3.3-70b-versatile on 16 Aug 2026, which is what broke
# question generation. Models can be swapped without a code change by setting
# GROQ_MODEL / GROQ_FALLBACK_MODEL in the Elastic Beanstalk environment properties.
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_FALLBACK_MODEL = "openai/gpt-oss-20b"
MODEL = os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_MODEL
FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL", "").strip() or DEFAULT_FALLBACK_MODEL

# Groq error codes that mean "this model is gone", so we try the fallback model.
MODEL_GONE_CODES = {"model_decommissioned", "model_not_found"}


def groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set on the server. Add it in Elastic Beanstalk "
                   "under Configuration > Updates, monitoring, and logging > Environment properties.",
        )
    return key


def build_payload(model: str, prompt: str, max_tokens: int, stream: bool = False) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
        "temperature": 0.7,
    }
    if model.startswith("openai/gpt-oss"):
        # gpt-oss models are reasoning models: thinking tokens count against the
        # completion budget, so keep effort low and the budget generous.
        payload["reasoning_effort"] = "low"
    if stream:
        payload["stream"] = True
    return payload


def groq_error_details(resp) -> tuple:
    try:
        err = resp.json().get("error", {})
        return err.get("code", "") or "", err.get("message", "") or resp.text[:300]
    except (ValueError, AttributeError):
        return "", resp.text[:300]


def groq_post(prompt: str, max_tokens: int, stream: bool = False):
    """POST to Groq, falling back to FALLBACK_MODEL if the primary model is gone.
    Returns a 200 response, or raises HTTPException with a readable reason."""
    headers = {"Authorization": f"Bearer {groq_api_key()}", "Content-Type": "application/json"}
    models = [MODEL]
    if FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
        models.append(FALLBACK_MODEL)

    for i, model in enumerate(models):
        try:
            resp = requests.post(
                GROQ_URL,
                headers=headers,
                json=build_payload(model, prompt, max_tokens, stream),
                stream=stream,
                timeout=(5, 60),
            )
        except requests.Timeout:
            raise HTTPException(status_code=504, detail="Groq took too long to respond. Please try again.")
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Could not reach Groq ({e.__class__.__name__}).")

        if resp.status_code == 200:
            return resp

        code, message = groq_error_details(resp)
        status = resp.status_code
        resp.close()

        is_last = i == len(models) - 1
        if (code in MODEL_GONE_CODES or "decommission" in message.lower()) and not is_last:
            continue  # primary model retired: try the fallback
        if status == 401:
            raise HTTPException(status_code=502, detail="Groq rejected GROQ_API_KEY (invalid or revoked). Check the key in the environment properties.")
        if status == 429:
            raise HTTPException(status_code=429, detail="Groq rate limit reached. Wait a few seconds and try again.")
        raise HTTPException(status_code=502, detail=f"Groq error ({code or status}): {message}")

    raise HTTPException(status_code=502, detail="No Groq model available.")


def groq_chat(prompt: str, max_tokens: int = 1500) -> str:
    resp = groq_post(prompt, max_tokens)
    try:
        choice = resp.json()["choices"][0]
        text = (choice["message"].get("content") or "").strip()
    except (ValueError, KeyError, IndexError):
        raise HTTPException(status_code=502, detail="Unexpected response format from Groq.")
    if not text:
        raise HTTPException(
            status_code=502,
            detail=f"The model returned an empty answer (finish_reason={choice.get('finish_reason')}). Please try again.",
        )
    return text


def extract_json(text: str):
    """Pull the first JSON object out of a model reply, tolerating ``` fences and chatter."""
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


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
    return {"status": "ok", "key_set": bool(os.environ.get("GROQ_API_KEY", "").strip()), "model": MODEL}

@app.get("/api/roles")
def get_roles():
    return ROLES

# Plain `def` (not `async def`): the Groq call is blocking, so FastAPI runs it in a
# worker thread instead of freezing the whole server while waiting.
@app.post("/api/generate-question")
def generate_question(req: QuestionRequest):
    role_label = ROLES.get(req.role, {}).get("label", req.role)
    kind = "behavioral" if req.question_type == "behavioral" else "technical"
    prompt = (
        f'Generate ONE {req.difficulty} {kind} interview question for a {role_label}. '
        f'Return ONLY valid JSON, no markdown: '
        f'{{"question":"...","hint":"one-line tip","type":"{kind}","follow_up":"one follow-up"}}'
    )
    text = groq_chat(prompt, max_tokens=1500)
    data = extract_json(text)
    if isinstance(data, dict) and data.get("question"):
        return {
            "question": str(data["question"]),
            "hint": str(data.get("hint", "")),
            "type": str(data.get("type", kind)),
            "follow_up": str(data.get("follow_up", "")),
        }
    # Model ignored the JSON instruction: still show something usable.
    return {"question": text, "hint": "Think carefully.", "type": req.question_type, "follow_up": ""}

@app.post("/api/evaluate")
def evaluate_answer(req: EvaluateRequest):
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

    def stream():
        try:
            resp = groq_post(prompt, max_tokens=3000, stream=True)
        except HTTPException as e:
            yield sse({"text": f"Error: {e.detail}"})
            yield "data: [DONE]\n\n"
            return
        try:
            with resp:
                for raw in resp.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8")
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    # gpt-oss streams its thinking in a separate field; only forward the answer.
                    text = delta.get("content") or ""
                    if text:
                        yield sse({"text": text})
        except requests.RequestException as e:
            yield sse({"text": f"\n\nError: connection to Groq was lost ({e.__class__.__name__})."})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

frontend_path = pathlib.Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")