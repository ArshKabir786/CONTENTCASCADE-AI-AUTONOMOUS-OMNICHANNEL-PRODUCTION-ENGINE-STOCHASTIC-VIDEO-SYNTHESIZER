import os
import asyncio
import json
import subprocess
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_FRONTEND_PUBLIC_DIR = PROJECT_ROOT / "frontend" / "public"
DEFAULT_GCP_CREDENTIALS_PATH = BASE_DIR / "gcp-credentials.json"


def get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; falling back to {default}.")
        return default


def resolve_google_credentials_path() -> Path | None:
    env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path:
        expanded = Path(env_path).expanduser()
        if not expanded.is_absolute():
            expanded = (BASE_DIR / expanded).resolve()
        if expanded.exists():
            return expanded
        print(f"GOOGLE_APPLICATION_CREDENTIALS points to missing file: {expanded}")

    if DEFAULT_GCP_CREDENTIALS_PATH.exists():
        return DEFAULT_GCP_CREDENTIALS_PATH
    return None


def load_google_credentials():
    credentials_path = resolve_google_credentials_path()
    if not credentials_path:
        return None

    try:
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(str(credentials_path))
    except Exception as exc:
        print(f"Failed to load Google credentials from {credentials_path}: {exc}")
        return None


def resolve_video_engine_path() -> Path:
    env_path = os.getenv("VIDEO_ENGINE_PATH")
    if env_path:
        expanded = Path(env_path).expanduser()
        if not expanded.is_absolute():
            expanded = (BASE_DIR / expanded).resolve()
        return expanded

    local_path = BASE_DIR / "video_engine.py"
    if local_path.exists():
        return local_path

    desktop_path = Path.home() / "Desktop" / "new horror style" / "video engine.py"
    if desktop_path.exists():
        return desktop_path

    return local_path


def ensure_ffmpeg_on_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        import glob
        matches = glob.glob(os.path.join(local_app, "Microsoft", "WinGet", "**", "ffmpeg.exe"), recursive=True)
        if matches:
            bin_dir = os.path.dirname(matches[0])
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            return matches[0]
    return "ffmpeg"


FFMPEG_BIN = ensure_ffmpeg_on_path()
FRONTEND_PUBLIC_DIR = Path(
    os.getenv("FRONTEND_PUBLIC_DIR", str(DEFAULT_FRONTEND_PUBLIC_DIR))
).expanduser()
VIDEO_ENGINE_PATH = resolve_video_engine_path()
VIDEO_RENDER_TIMEOUT_SECONDS = get_int_env("VIDEO_RENDER_TIMEOUT_SECONDS", 420)
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0441766511")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_groq_api_key = os.getenv("GROQ_API_KEY")
if _groq_api_key:
    groq_client = Groq(api_key=_groq_api_key)
else:
    groq_client = None
    print("WARNING: GROQ_API_KEY not set. AI text generation will not work until the key is provided.")

class ContentRequest(BaseModel):
    topic: str
    include_video: bool = True
    bgm_style: str = "suspense"
    platforms: list[str] = ["twitter", "linkedin", "blog", "instagram"]

async def generate_text_content(prompt: str, role: str) -> str:
    try:
        def _call_groq():
            return groq_client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                messages=[
                    {"role": "system", "content": role},
                    {"role": "user", "content": prompt}
                ]
            )
        response = await asyncio.to_thread(_call_groq)
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating content: {e}")
        return f"Error: {e}"

# ─────────────────────────────────────────────────────────────
# SSE STREAMING ENDPOINT — The Beast Mode Feature
# ─────────────────────────────────────────────────────────────
async def sse_pipeline(topic: str, include_video: bool, bgm_style: str = "suspense", platforms: list[str] = None):
    """Generator that yields SSE events as each pipeline stage completes."""
    
    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"
    
    results = {}
    if platforms is None:
        platforms = ["twitter", "linkedin", "blog", "instagram"]
    
    # Create unique temp directory for this run early so we can save text assets
    run_id = str(uuid.uuid4())[:8]
    temp_dir = os.path.join(os.getcwd(), f"pipeline_assets_{run_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # ── Stage 0: URL Parsing (Optional) ──
    original_topic = topic
    if topic.strip().startswith("http://") or topic.strip().startswith("https://"):
        yield sse("stage", {"id": 0, "name": "Extracting Article", "status": "active"})
        try:
            print(f"URL detected. Extracting content from: {topic}")
            import urllib.request
            import urllib.parse
            req = urllib.request.Request(
                f"https://r.jina.ai/{topic.strip()}",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                scraped_text = response.read().decode('utf-8')
                
            # Truncate to avoid LLM context limits (roughly 3000 words)
            scraped_text = scraped_text[:15000]
            
            # Rewrite topic to be the scraped text
            topic = f"The following is an extracted article/webpage. Base all content strictly on this information:\n\n{scraped_text}"
            print("✓ Successfully scraped article.")
        except Exception as e:
            print(f"Failed to scrape URL: {e}")
            yield sse("data", {"key": "error", "content": f"Failed to extract article: {e}"})
            # Fall back to just treating the URL as a string topic if scraping fails
            pass
            
            
    # ── Stage 1: Narrative Arc ──
    yield sse("stage", {"id": 0, "name": ("Analyzing Intent" if original_topic == topic else "Analyzing Article"), "status": "active"})
    
    ideation_role = "You are a master content strategist and narrative architect."
    ideation_prompt = f"""Create a comprehensive 3-point narrative arc about: {topic}
    
Structure it as:
1. Hook — A compelling opening insight that grabs attention
2. Core Argument — The main thesis with supporting evidence  
3. Call to Action — What the audience should think or do differently

Keep it focused, vivid, and under 200 words."""
    
    results['narrative'] = await generate_text_content(ideation_prompt, ideation_role)
    yield sse("stage", {"id": 0, "name": "Analyzing Intent", "status": "done"})
    
    # ── Stage 2: All Content in Parallel ──
    yield sse("stage", {"id": 1, "name": "Generating Content", "status": "active"})
    
    twitter_role = "You are a viral Twitter/X thread writer with 500K+ followers. You know how to write hooks that stop the scroll."
    twitter_prompt = f"""Write a killer 5-tweet thread about this narrative:
{results['narrative']}

Rules:
- Tweet 1 must be a hook that stops the scroll (use a bold claim or surprising stat)
- Use short punchy sentences, line breaks between ideas
- Include 2-3 relevant hashtags on the last tweet only
- Add 1 emoji per tweet maximum
- End with a call to engage (reply, retweet, or follow)"""
    
    linkedin_role = "You are a LinkedIn Top Voice with expertise in thought leadership content."
    linkedin_prompt = f"""Write a compelling LinkedIn post about this narrative:
{results['narrative']}

Rules:
- Start with a hook line followed by a line break
- Use short paragraphs (2-3 sentences max)  
- Include a personal insight or "hot take" 
- End with a question to drive comments
- Add 3-5 relevant hashtags at the bottom
- Tone: Professional but conversational, not corporate jargon"""
    
    blog_role = "You are an SEO expert blog writer who creates content that ranks on Google."
    blog_prompt = f"""Write a 500-word SEO-optimized blog post about this narrative:
{results['narrative']}

Rules:
- Include a compelling H1 title with the main keyword
- Add 2-3 H2 subheadings
- First paragraph must hook the reader (no throat-clearing)
- Include actionable takeaways
- End with a strong conclusion and CTA
- Write in an engaging, authoritative voice"""

    instagram_role = "You are a top Instagram content creator who specializes in carousel-style educational content."
    instagram_prompt = f"""Write an Instagram caption for a carousel post about this narrative:
{results['narrative']}

Rules:
- Start with a hook line (question or bold statement)  
- Use line breaks for readability
- Include a call-to-action (save, share, comment)
- Add 15-20 relevant hashtags at the end  
- Keep it under 300 words
- Tone: Relatable, inspiring, and educational"""

    tasks = []
    platform_keys = []
    
    if "twitter" in platforms:
        tasks.append(generate_text_content(twitter_prompt, twitter_role))
        platform_keys.append("twitter")
    if "linkedin" in platforms:
        tasks.append(generate_text_content(linkedin_prompt, linkedin_role))
        platform_keys.append("linkedin")
    if "blog" in platforms:
        tasks.append(generate_text_content(blog_prompt, blog_role))
        platform_keys.append("blog")
    if "instagram" in platforms:
        tasks.append(generate_text_content(instagram_prompt, instagram_role))
        platform_keys.append("instagram")
        
    generated_content = await asyncio.gather(*tasks)
    
    for key, content in zip(platform_keys, generated_content):
        results[key] = content
    
    yield sse("stage", {"id": 1, "name": "Generating Content", "status": "done"})
    
    # Send each piece of content as it becomes available
    for key in platform_keys:
        yield sse("data", {"key": key, "content": results[key]})
    yield sse("data", {"key": "narrative", "content": results['narrative']})
    
    # Save all text content to a text file for the ZIP export
    campaign_path = os.path.join(temp_dir, "campaign_assets.txt")
    with open(campaign_path, "w") as f:
        f.write(f"=== CAMPAIGN TOPIC ===\n{topic}\n\n")
        f.write(f"=== NARRATIVE ARC ===\n{results.get('narrative')}\n\n")
        if "twitter" in platforms:
            f.write(f"=== TWITTER/X THREAD ===\n{results.get('twitter')}\n\n")
        if "linkedin" in platforms:
            f.write(f"=== LINKEDIN POST ===\n{results.get('linkedin')}\n\n")
        if "instagram" in platforms:
            f.write(f"=== INSTAGRAM CAPTION ===\n{results.get('instagram')}\n\n")
        if "blog" in platforms:
            f.write(f"=== SEO BLOG POST ===\n{results.get('blog')}\n\n")
    
    if include_video:
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel
        import shutil
        
        public_dir = Path(FRONTEND_PUBLIC_DIR) if isinstance(FRONTEND_PUBLIC_DIR, str) else FRONTEND_PUBLIC_DIR
        os.makedirs(public_dir, exist_ok=True)
        
        # ── Stage 3: Video Script Generation ──
        yield sse("stage", {"id": 2, "name": "Scripting Video", "status": "active"})
        
        video_role = "You are an expert short-form video producer who specializes in creating perfectly synchronized visual-audio content. Your image prompts must EXACTLY depict what the narration describes — no abstract or unrelated imagery."
        video_prompt = f"""
Based on this narrative: "{results['narrative']}"

Create a 30-second video script with EXACTLY 6 scenes.

CRITICAL RULES:
1. Write EXACTLY 6 short narration sentences (1-2 lines each).
2. For EACH narration sentence, write a HYPER-SPECIFIC image prompt that visually depicts EXACTLY what that sentence describes.
   - If the narration says "children stare at glowing screens", the image prompt MUST show children staring at screens.
   - If the narration says "forests are being destroyed", the image prompt MUST show deforestation.
   - NEVER write generic/abstract prompts like "a dark atmospheric scene" — always depict the SPECIFIC subject, action, and setting from the narration.
3. Every image prompt must include: the exact subject from the narration, the specific action happening, the environment/setting, and the mood. Style: photorealistic, cinematic, 8k, dramatic lighting.
4. Return ONLY a raw JSON array (no markdown, no backticks):
[
  {{"narration": "The exact narration sentence...", "image_prompt": "A photorealistic scene showing [exact subject from narration] [doing exact action from narration] in [specific setting], cinematic lighting, 8k, dramatic composition"}},
  ...
]

EXAMPLE of correct alignment:
- Narration: "The oceans are rising, swallowing coastlines whole."
- Image prompt: "A photorealistic aerial view of ocean waves flooding a coastal city, water rushing through streets and submerging buildings, dramatic storm clouds overhead, cinematic lighting, 8k resolution"

Return the JSON array now:
"""
        pipeline_json_str = await generate_text_content(video_prompt, video_role)
        
        try:
            json_str = pipeline_json_str.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
                
            script_data = json.loads(json_str.strip())
            
            narrations = [item.get("narration", "") for item in script_data]
            raw_prompts = [item.get("image_prompt", "") for item in script_data]
            
            prompts = []
            for i, (narr, prompt) in enumerate(zip(narrations, raw_prompts)):
                if prompt:
                    enriched = f"Depicting: '{narr}'. {prompt}"
                else:
                    enriched = f"A photorealistic cinematic scene depicting: '{narr}'. Dramatic lighting, 8k resolution, detailed environment."
                prompts.append(enriched)
            
            script_text = "\n".join(narrations)
            results['video_script'] = script_text

            while len(prompts) < 6:
                prompts.append("A dark cinematic horror scene, highly detailed, 8k")
            prompts = prompts[:6]
            
        except Exception as e:
            print(f"Failed to parse prompts: {e}")
            prompts = ["A dark cinematic horror scene, highly detailed, 8k"] * 6
            narrations = ["Scene narration unavailable."] * 6
            script_text = "Scene narration unavailable."
            results['video_script'] = script_text

        yield sse("stage", {"id": 2, "name": "Scripting Video", "status": "done"})
        yield sse("data", {"key": "video_script", "content": results['video_script']})
        
        script_path = os.path.join(temp_dir, "script_short.txt")
        with open(script_path, "w") as f:
            f.write(script_text)

        # ── Stage 4: TTS + Image Generation ──
        yield sse("stage", {"id": 3, "name": "Generating Media", "status": "active"})
        
        # 1. Generate Voiceover
        audio_path = os.path.join(temp_dir, "voiceover_short.mp3")
        google_credentials = load_google_credentials()
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        
        tts_success = False
        
        # Primary: ElevenLabs (George)
        if elevenlabs_key and not tts_success:
            try:
                print("Generating TTS with ElevenLabs...")
                import requests as req_lib
                eleven_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
                eleven_url = f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}"
                headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": elevenlabs_key
                }
                data = {
                    "text": script_text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
                }
                response = await asyncio.to_thread(
                    lambda: req_lib.post(eleven_url, json=data, headers=headers, timeout=60)
                )
                if response.status_code == 200 and len(response.content) > 1000:
                    with open(audio_path, "wb") as f:
                        f.write(response.content)
                    print("✓ ElevenLabs TTS generated successfully.")
                    tts_success = True
                else:
                    print(f"ElevenLabs TTS failed with status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"ElevenLabs Error: {e}")
                
        # Secondary: Google Cloud TTS
        if google_credentials and not tts_success:
            try:
                print("Generating TTS with Google Cloud TTS fallback...")
                from google.cloud import texttospeech
                
                tts_client = texttospeech.TextToSpeechClient(credentials=google_credentials)
                synthesis_input = texttospeech.SynthesisInput(text=script_text)
                
                voice = texttospeech.VoiceSelectionParams(
                    language_code="en-US",
                    name="en-US-Journey-D"
                )
                
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                response = tts_client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                
                with open(audio_path, "wb") as f:
                    f.write(response.audio_content)
                    
                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    print("✓ Google Cloud TTS (Journey) generated successfully.")
                    tts_success = True
                else:
                    print("Google TTS returned empty file")
            except Exception as e:
                print(f"Google TTS Error: {e}")
                
        # Last Resort: gTTS
        if not tts_success:
            print("Using free gTTS fallback for Audio...")
            try:
                from gtts import gTTS
                tts = gTTS(text=script_text, lang='en', slow=False)
                tts.save(audio_path)
                print("✓ Fallback gTTS generated successfully.")
            except Exception as fallback_e:
                print(f"gTTS Error: {fallback_e}")

        # 2. Generate Images
        try:
            print(f"Generating {len(prompts)} images...")
            import urllib.parse
            
            imagen_model = None
            imagen_model_fast = None
            try:
                if google_credentials:
                    vertexai.init(
                        project=GCP_PROJECT_ID,
                        location=GCP_LOCATION,
                        credentials=google_credentials,
                    )
                    imagen_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
                    imagen_model_fast = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")
                else:
                    print("Imagen 3 credentials unavailable; using fallback image provider.")
            except Exception as cred_e:
                print(f"Imagen 3 credentials not available: {cred_e}")

            hf_token = os.getenv("HF_TOKEN")
            image_urls = []
            for idx, prompt in enumerate(prompts):
                img_path = os.path.join(temp_dir, f"scene_{idx+1}.png")
                public_img_filename = f"scene_{idx+1}_{run_id}.png"
                public_img_path = os.path.join(public_dir, public_img_filename)
                success = False
                
                yield sse("progress", {"message": f"Generating image {idx+1}/{len(prompts)}..."})
                
                # PRIMARY: Hugging Face Router (FLUX.1-schnell via fal-ai)
                if hf_token and not success:
                    try:
                        print(f"Generating scene {idx+1} via Hugging Face FLUX.1...")
                        import requests as req_lib
                        hf_url = "https://router.huggingface.co/fal-ai/fal-ai/flux/schnell"
                        hf_headers = {"Authorization": f"Bearer {hf_token}"}
                        hf_payload = {"prompt": prompt[:500]}
                        hf_resp = await asyncio.to_thread(
                            lambda: req_lib.post(hf_url, headers=hf_headers, json=hf_payload, timeout=30)
                        )
                        if hf_resp.status_code == 200:
                            content_type = hf_resp.headers.get("content-type", "")
                            if content_type.startswith("image/") and len(hf_resp.content) > 1000:
                                with open(img_path, 'wb') as f:
                                    f.write(hf_resp.content)
                                print(f"✓ scene_{idx+1}.png via Hugging Face FLUX.1")
                                success = True
                            elif "application/json" in content_type:
                                hf_json = hf_resp.json()
                                img_url = (hf_json.get("images") or [{}])[0].get("url")
                                if img_url:
                                    img_dl = await asyncio.to_thread(lambda: req_lib.get(img_url, timeout=30))
                                    if img_dl.status_code == 200 and len(img_dl.content) > 1000:
                                        with open(img_path, 'wb') as f:
                                            f.write(img_dl.content)
                                        print(f"✓ scene_{idx+1}.png via Hugging Face FLUX.1")
                                        success = True
                        if not success:
                            print(f"HF returned status {hf_resp.status_code}: {hf_resp.text[:200]}")
                    except Exception as hf_e:
                        print(f"Hugging Face failed for scene {idx+1}: {hf_e}")

                # FALLBACK: Imagen 3 (Standard)
                if imagen_model and not success:
                    try:
                        print(f"Generating scene {idx+1} via Imagen 3...")
                        def _gen_standard():
                            return imagen_model.generate_images(
                                prompt=prompt[:1000], number_of_images=1, language="en", aspect_ratio="9:16"
                            )
                        img_response = await asyncio.to_thread(_gen_standard)
                        
                        # Process response
                        for img in (img_response if not hasattr(img_response, 'images') else img_response.images):
                            img.save(location=img_path, include_generation_parameters=False)
                            break
                            
                        if os.path.exists(img_path) and os.path.getsize(img_path) > 1000:
                            print(f"✓ scene_{idx+1}.png via Imagen 3")
                            success = True
                    except Exception as img_e:
                        print(f"Imagen 3 failed for scene {idx+1}: {img_e}")
                        
                # SECONDARY: Imagen 3 (Fast) 
                if imagen_model_fast and not success:
                    try:
                        print(f"Generating scene {idx+1} via Imagen 3 (Fast fallback)...")
                        def _gen_fast():
                            return imagen_model_fast.generate_images(
                                prompt=prompt[:1000], number_of_images=1, language="en", aspect_ratio="9:16"
                            )
                        img_response_fast = await asyncio.to_thread(_gen_fast)
                        
                        # Process response
                        for img in (img_response_fast if not hasattr(img_response_fast, 'images') else img_response_fast.images):
                            img.save(location=img_path, include_generation_parameters=False)
                            break
                            
                        if os.path.exists(img_path) and os.path.getsize(img_path) > 1000:
                            print(f"✓ scene_{idx+1}.png via Imagen 3 (Fast)")
                            success = True
                    except Exception as img_e:
                        print(f"Imagen 3 (Fast) failed for scene {idx+1}: {img_e}")
                
                # TERTIARY: Pollinations via requests
                if not success:
                    for attempt in range(2):
                        try:
                            import requests as req_lib
                            short_prompt = prompt[:400] + ", photorealistic, cinematic, 8k"
                            encoded_prompt = urllib.parse.quote(short_prompt)
                            # the image.pollinations endpoint is throwing 530, try an alternate seed structure
                            poll_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={idx + attempt * 100}"
                            
                            resp = await asyncio.to_thread(
                                lambda: req_lib.get(poll_url, timeout=30, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                })
                            )
                            if resp.status_code == 200 and len(resp.content) > 5000:
                                with open(img_path, 'wb') as f:
                                    f.write(resp.content)
                                print(f"✓ scene_{idx+1}.png via Pollinations")
                                success = True
                                break
                            else:
                                print(f"Pollinations returned status {resp.status_code}")
                                await asyncio.sleep(2)
                        except Exception as poll_e:
                            print(f"Pollinations attempt {attempt+1} failed: {type(poll_e).__name__}")
                
                # QUATERNARY: AI Horde (100% free, no signup)
                if not success:
                    try:
                        import requests as req_lib
                        print(f"Generating scene {idx+1} via AI Horde...")
                        horde_payload = {
                            "prompt": prompt[:400] + ", photorealistic, cinematic, 8k",
                            "params": {"width": 512, "height": 896, "steps": 15, "n": 1},
                            "models": ["Deliberate", "AlbedoBase XL (SDXL)", "SDXL 1.0"],
                        }
                        sub_resp = await asyncio.to_thread(
                            lambda: req_lib.post(
                                "https://aihorde.net/api/v2/generate/async",
                                headers={"apikey": "0000000000"},
                                json=horde_payload,
                                timeout=15,
                            )
                        )
                        if sub_resp.status_code == 202:
                            job_id = sub_resp.json().get("id")
                            for _ in range(20):
                                await asyncio.sleep(2)
                                chk = await asyncio.to_thread(
                                    lambda: req_lib.get(f"https://aihorde.net/api/v2/generate/check/{job_id}", timeout=10)
                                )
                                if chk.status_code == 200 and chk.json().get("done"):
                                    st = await asyncio.to_thread(
                                        lambda: req_lib.get(f"https://aihorde.net/api/v2/generate/status/{job_id}", timeout=15)
                                    )
                                    gens = st.json().get("generations", []) if st.status_code == 200 else []
                                    if gens and gens[0].get("img"):
                                        img_dl = await asyncio.to_thread(lambda: req_lib.get(gens[0]["img"], timeout=20))
                                        if img_dl.status_code == 200 and len(img_dl.content) > 1000:
                                            tmp_webp = os.path.join(temp_dir, f"scene_{idx+1}.webp")
                                            with open(tmp_webp, "wb") as f:
                                                f.write(img_dl.content)
                                            subprocess.run([FFMPEG_BIN, "-y", "-i", tmp_webp, img_path], capture_output=True)
                                            if os.path.exists(img_path) and os.path.getsize(img_path) > 1000:
                                                print(f"✓ scene_{idx+1}.png via AI Horde")
                                                success = True
                                    break
                    except Exception as horde_e:
                        print(f"AI Horde failed for scene {idx+1}: {horde_e}")

                # LAST RESORT: gradient frame via FFmpeg
                if not success:
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1080x1920:d=1",
                        "-frames:v", "1", img_path
                    ], capture_output=True)
                    print(f"✗ scene_{idx+1}.png via fallback frame")
                
                # Copy to public dir for Review UI
                if os.path.exists(img_path):
                    shutil.copy(img_path, public_img_path)
                    image_urls.append(f"/{public_img_filename}")
                        
                await asyncio.sleep(2)
                
            print("Image generation complete.")
        except Exception as e:
            print(f"Image Gen Error: {e}")
            
        # 3. Generate BGM Drone
        bgm_path = os.path.join(temp_dir, "bgm_short.mp3")
        if bgm_style != "none":
            try:
                print(f"Generating procedural BGM ({bgm_style})...")
                
                # Configure different procedural sounds using FFmpeg's aevalsrc math filter
                if bgm_style == "suspense":
                    # Deep 40Hz sub drone with 42Hz wobble/beating effect
                    filter_str = "aevalsrc=0.1*sin(2*PI*40*t)+0.1*sin(2*PI*42*t):s=44100:d=60"
                elif bgm_style == "heartbeat":
                    # Slow, pulsing rhythm using heavily muffled square waves
                    filter_str = "aevalsrc='volume=expr=0.3*sgn(sin(2*PI*1.4*t)):aevalsrc=0.5*sin(2*PI*30*t)':s=44100:d=60"
                    # We'll use a simpler heartbeat approximation that FFmpeg can parse easily
                    filter_str = "aevalsrc=0.5*sin(2*PI*55*t)*pow(sin(2*PI*1.2*t),10):s=44100:d=60"
                elif bgm_style == "tension":
                    # High pitched, unpleasant ringing tone to build anxiety (approx 8000Hz + 8005Hz) mixed with low drone
                    filter_str = "aevalsrc=0.03*sin(2*PI*8000*t)+0.03*sin(2*PI*8005*t)+0.08*sin(2*PI*45*t):s=44100:d=60"
                else:
                    filter_str = "aevalsrc=0.1*sin(2*PI*40*t)+0.1*sin(2*PI*42*t):s=44100:d=60"

                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", 
                    "-i", filter_str, 
                    "-b:a", "128k", bgm_path
                ], capture_output=True)
                
                if os.path.exists(bgm_path) and os.path.getsize(bgm_path) > 1000:
                    print(f"✓ BGM generated ({bgm_style}).")
                else:
                    bgm_path = None
                    print("BGM generation resulted in empty or missing file.")
            except Exception as e:
                print(f"Failed to generate BGM: {e}")
                bgm_path = None
        else:
            print("BGM disabled by user.")
            bgm_path = None
            
        yield sse("stage", {"id": 3, "name": "Generating Media", "status": "done"})

        # ── INTERCEPT: Pause for Director's Cut ──
        yield sse("stage", {"id": 4, "name": "Review", "status": "active"})
        
        # Send the script and images to the frontend
        yield sse("data", {
            "key": "review_data", 
            "content": {
                "run_id": run_id,
                "images": image_urls,
                "script": narrations,
                "bgm_path": bgm_path
            }
        })
        
        # We stop the stream here so the frontend can pause.
        yield sse("done", {"message": "Pipeline paused for review.", "run_id": run_id, "requires_review": True})
        return

    # ── DONE (If no video included) ──
    yield sse("done", {"message": "Pipeline complete!", "run_id": run_id})

class RenderRequest(BaseModel):
    run_id: str
    script: list[str]
    bgm_path: str | None = None

@app.post("/api/render-video")
async def render_video(req: RenderRequest):
    """Takes the approved script, re-runs TTS if needed, and renders the video."""
    temp_dir = os.path.join(os.getcwd(), f"pipeline_assets_{req.run_id}")
    public_dir = Path(FRONTEND_PUBLIC_DIR) if isinstance(FRONTEND_PUBLIC_DIR, str) else FRONTEND_PUBLIC_DIR
    
    if not os.path.exists(temp_dir):
        return {"error": "Run ID not found or expired"}
        
    script_text = "\n".join(req.script)
    script_path = os.path.join(temp_dir, "script_short.txt")
    
    # Check if script changed to see if we need new TTS
    needs_new_tts = True
    if os.path.exists(script_path):
        with open(script_path, "r") as f:
            old_text = f.read()
        if old_text.strip() == script_text.strip():
            needs_new_tts = False
            
    # Save the approved script
    with open(script_path, "w") as f:
        f.write(script_text)
        
    audio_path = os.path.join(temp_dir, "voiceover_short.mp3")
    
    if needs_new_tts:
        # Quick fallback gTTS for the updated text to save time/money
        print("Script edited! Regenerating TTS using free fallback...")
        try:
            from gtts import gTTS
            tts = gTTS(text=script_text, lang='en', slow=False)
            tts.save(audio_path)
            print("✓ Updated TTS generated.")
        except Exception as e:
            print(f"Failed to regenerate TTS: {e}")

    # ── Render Video ──
    video_engine_path = VIDEO_ENGINE_PATH
    patched_engine_path = os.path.join(temp_dir, "video_engine_patched.py")
    output_filename = f"output_{req.run_id}.mp4"
    output_filepath = public_dir / output_filename
    
    try:
        with open(video_engine_path, "r", encoding="utf-8") as f:
            engine_code = f.read()
            
        import re
        temp_dir_posix = Path(temp_dir).as_posix()
        output_filepath_posix = Path(output_filepath).as_posix()
        engine_code = re.sub(r'ASSETS_DIR\s*=\s*".*?"', lambda _: f'ASSETS_DIR = "{temp_dir_posix}/"', engine_code)
        engine_code = re.sub(r'OUTPUT_FILE\s*=\s*".*?"', lambda _: f'OUTPUT_FILE = "{output_filepath_posix}"', engine_code)
        
        if req.bgm_path and os.path.exists(req.bgm_path):
            bgm_posix = Path(req.bgm_path).as_posix()
            engine_code = re.sub(r'BGM_FILE\s*=\s*".*?"', lambda _: f'BGM_FILE = "{bgm_posix}"', engine_code)
        else:
            engine_code = re.sub(r'BGM_FILE\s*=\s*".*?"', 'BGM_FILE = ""', engine_code)
        
        num_lines = len([line for line in script_text.splitlines() if line.strip()])
        engine_code = re.sub(r'NUM_SCENES\s*=\s*\d+', f'NUM_SCENES = {num_lines}', engine_code)
        engine_code = re.sub(r'if\s+len\(lines\)\s*!=\s*NUM_SCENES:', r'if False:', engine_code)
        engine_code = re.sub(r'print\(f"  ✗ ERROR: SCENE_TEXTS has \{len\(SCENE_TEXTS\)\} entries, expected \{NUM_SCENES\}."\)\n\s+sys.exit\(1\)', r'pass', engine_code)
        engine_code = re.sub(r'VIGNETTE_ENABLED\s*=\s*True', 'VIGNETTE_ENABLED = False', engine_code)
        engine_code = re.sub(r'GRADE_ENABLED\s*=\s*True', 'GRADE_ENABLED = False', engine_code)
        engine_code = re.sub(r'SHARPEN_ENABLED\s*=\s*True', 'SHARPEN_ENABLED = False', engine_code)
        engine_code = re.sub(r'GRAIN_ENABLED\s*=\s*True', 'GRAIN_ENABLED = False', engine_code)
        engine_code = re.sub(r'AUTO_SYNC\s*=\s*"whisper"', 'AUTO_SYNC = "text_weighted"', engine_code)

        with open(patched_engine_path, "w", encoding="utf-8") as f:
            f.write(engine_code)

        print(f"Rendering updated video to {output_filepath}...")
        subprocess_result = await asyncio.to_thread(
            subprocess.run,
            ["python", patched_engine_path],
            capture_output=True,
            text=True,
            timeout=VIDEO_RENDER_TIMEOUT_SECONDS
        )
        
        if subprocess_result.returncode == 0:
            return {"status": "success", "video_url": f"/{output_filename}"}
        else:
            return {"status": "error", "message": f"Video Engine Error: {subprocess_result.stderr[-200:]}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/download/{run_id}")
async def download_assets(run_id: str):
    """Zips the pipeline assets folder and returns it as a downloadable file."""
    temp_dir = os.path.join(os.getcwd(), f"pipeline_assets_{run_id}")
    if not os.path.exists(temp_dir):
        raise HTTPException(status_code=404, detail="Assets not found or expired.")
        
    zip_filename = f"content_cascade_{run_id}.zip"
    zip_filepath = os.path.join(os.getcwd(), zip_filename)
    
    # Copy the final video into the temp_dir if it exists before zipping
    public_dir = FRONTEND_PUBLIC_DIR
    output_video = public_dir / f"output_{run_id}.mp4"
    if output_video.exists():
        shutil.copy(output_video, os.path.join(temp_dir, f"output_{run_id}.mp4"))
        
    try:
        shutil.make_archive(zip_filepath.replace('.zip', ''), 'zip', temp_dir)
        from starlette.responses import FileResponse
        return FileResponse(path=zip_filepath, media_type='application/zip', filename=zip_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-stream")
async def generate_content_stream(req: ContentRequest):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="Groq API Key not set.")
    
    return StreamingResponse(
        sse_pipeline(req.topic, req.include_video, req.bgm_style, req.platforms),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

# Keep the old endpoint as fallback
@app.post("/api/generate")
async def generate_content(req: ContentRequest):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="Groq API Key not set.")
    
    results = {}
    async for event_str in sse_pipeline(req.topic, req.include_video, req.bgm_style, req.platforms):
        # Parse SSE data events to build results  
        if event_str.startswith("event: data"):
            try:
                data_line = event_str.split("data: ", 1)[1].strip()
                parsed = json.loads(data_line)
                results[parsed['key']] = parsed['content']
            except:
                pass
    
    return {"status": "success", "data": results}

if __name__ == "__main__":
    # pyrefly: ignore[missing-import]
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
