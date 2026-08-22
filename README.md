# MockMentor-AI — AI-Powered Interview Coach

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Groq-LLaMA3-F55036?style=for-the-badge&logo=meta&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-Containerised-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/AWS-Elastic%20Beanstalk-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
</p>

<p align="center">
  <b>MockMentor-AI</b> is a full-stack AI interview coaching platform that simulates real technical and HR interview sessions, evaluates answers in real time using LLMs, and gives structured feedback — helping candidates prepare smarter for placements.
</p>

---

## Table of Contents
- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Docker Setup](#-docker-setup)
- [AWS Deployment](#-aws-deployment)
- [API Reference](#-api-reference)
- [Screenshots](#-screenshots)
- [Roadmap](#-roadmap)

---

## Overview

MockMentor-AI addresses a real gap in campus placement preparation — candidates often don't know how their answers will be perceived by an actual interviewer. This platform:

- Generates **role-specific interview questions** (technical, HR, behavioural)
- **Evaluates candidate responses** using Groq's LLaMA3 inference API
- Delivers **structured feedback**: clarity, depth, relevance, and improvement tips
- Runs as a **containerised microservice**, deployed on AWS Elastic Beanstalk

Built as a production-ready portfolio project targeting placements at companies like Deloitte, IBM, EY, and FactSet.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        CLIENT                           │
│                  React Frontend (Vite)                  │
│         Interview UI · Question Display · Feedback      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                       │
│                                                         │
│   /generate-question  →  Question Engine                │
│   /evaluate-answer    →  LLM Evaluation Pipeline        │
│   /session            →  Session State Manager          │
│   /history            →  Response Logger                │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐      ┌───────────────────────────┐
│   Groq API       │      │   PostgreSQL (planned)    │
│   LLaMA3-8B      │      │   Session · History · User│
│   Inference      │      │   Analytics               │
└──────────────────┘      └───────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                  Docker Container                       │
│              AWS Elastic Beanstalk                      │
│            (EC2 + Load Balancer + S3)                   │
└─────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **AI Mock Interview** | Simulates full interview sessions with role-specific questions |
| **LLM-Based Evaluation** | Uses Groq's LLaMA3 to assess answers on clarity, depth, and relevance |
| **Structured Feedback** | Returns actionable improvement tips per answer |
| **Session Management** | Tracks multi-turn interview conversations |
| **Dockerised** | Fully containerised — runs identically locally and in production |
| **Cloud Deployed** | Hosted on AWS Elastic Beanstalk with environment-based config |
| **Fast Inference** | Groq API delivers sub-second LLM response times |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **LLM Inference** | Groq API (LLaMA3-8B-8192) |
| **Frontend** | React (Vite), Axios |
| **Containerisation** | Docker, Docker Compose |
| **Cloud** | AWS Elastic Beanstalk, EC2 |
| **Database** *(planned)* | PostgreSQL |
| **Environment** | python-dotenv, Pydantic Settings |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API Key → [console.groq.com](https://console.groq.com)
- Docker (optional, for containerised run)

### 1. Clone the Repository
```bash
git clone https://github.com/Irin356/MockMentor-AI.git
cd MockMentor-AI
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file inside `/backend`:
```env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Run the Backend
```bash
uvicorn main:app --reload --port 8000
```
API docs available at: `http://localhost:8000/docs`

### 5. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```
Frontend available at: `http://localhost:5173`

---

## 🐳 Docker Setup

### Build and Run with Docker Compose
```bash
docker-compose up --build
```

### Build Backend Image Only
```bash
cd backend
docker build -t mockmentor-ai .
docker run -p 8000:8000 --env-file .env mockmentor-ai
```

---

## ☁️ AWS Deployment

MockMentor-AI is deployed on **AWS Elastic Beanstalk** using a Docker platform.

### Deployment Steps

**1. Install EB CLI**
```bash
pip install awsebcli
```

**2. Initialise Elastic Beanstalk**
```bash
eb init mockmentor-ai --platform docker --region ap-south-1
```

**3. Create Environment**
```bash
eb create mockmentor-env
```

**4. Set Environment Variables on AWS**
```bash
eb setenv GROQ_API_KEY=your_groq_api_key_here
```

**5. Deploy**
```bash
eb deploy
```

**6. Open the App**
```bash
eb open
```

> ℹ️ The `Dockerfile` at the project root is used by Elastic Beanstalk automatically.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/generate-question` | Generate interview question by role/domain |
| `POST` | `/evaluate-answer` | Evaluate candidate answer using LLM |
| `GET` | `/session/{session_id}` | Retrieve session history |

### Example — Generate Question
```bash
curl -X POST http://localhost:8000/generate-question \
  -H "Content-Type: application/json" \
  -d '{"role": "Software Engineer", "domain": "Data Structures", "difficulty": "medium"}'
```

### Example — Evaluate Answer
```bash
curl -X POST http://localhost:8000/evaluate-answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain the difference between a stack and a queue.",
    "answer": "A stack follows LIFO and a queue follows FIFO..."
  }'
```

---

## 📸 Screenshots

> *Screenshots will be added post-deployment.*

| Interview Session | Feedback View | Dashboard |
|---|---|---|
| *Coming soon* | *Coming soon* | *Coming soon* |

---

## 🗺️ Roadmap

- [x] FastAPI backend with Groq LLM integration
- [x] Docker containerisation
- [x] AWS Elastic Beanstalk deployment
- [ ] PostgreSQL integration for session persistence
- [ ] User authentication (JWT)
- [ ] Answer history & performance analytics
- [ ] Voice input support
- [ ] Role-specific question banks (DSA, System Design, HR)

---

## 👩‍💻 Author

**Irin Antony**  
B.Tech CSE (Cyber Security Honours) — Government Model Engineering College, Kochi  
[GitHub](https://github.com/Irin356) · [LinkedIn](https://linkedin.com/in/irin-antony)

---

## 📄 Licence

This project is open source and available under the [MIT License](LICENSE).
