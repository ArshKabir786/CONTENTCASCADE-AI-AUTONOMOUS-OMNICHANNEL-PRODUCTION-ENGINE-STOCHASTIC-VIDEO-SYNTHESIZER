# ContentCascade.ai - Hackathon Submission

An AI-Powered Omnichannel Production Engine. Automatically generates video scripts, social media copy, background music, images, and synthesizes them into stunning videos from just a topic or URL.

## Features
- **URL Repurposer**: Extracts and rewrites entire articles using Jina AI's Reader API
- **Director's Cut Timeline**: A beautiful human-in-the-loop review UI to edit the script before rendering the final video.
- **Cinematic Procedural BGM**: Dynamically generates soundscapes using FFmpeg filters.
- **SSE Real-time UI**: Next.js streaming dashboard.
- **Zip Export**: Export all generated campaigns in a single click.

## Quickstart

### Backend (FastAPI + Python)
1. \`cd backend\`
2. \`python3 -m venv venv\`
3. \`source venv/bin/activate\`
4. \`pip install -r requirements.txt\`
5. Copy \`.env.example\` to \`.env\` and add your API keys (Groq, ElevenLabs, Google Cloud, etc).
6. \`uvicorn main:app --reload\`

### Frontend (Next.js + React)
1. \`cd frontend\`
2. \`npm install\`
3. \`npm run dev\`

Visit \`http://localhost:3000\` to launch a campaign!
