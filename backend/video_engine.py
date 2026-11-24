#!/usr/bin/env python3
"""
video engine.py — Universal Horror Shorts Production Engine
==============================================================
A reusable production tool that stitches scene images into a
9:16 vertical video with:

  • AI-powered word-level sync via faster-whisper transcription
  • Dynamic scene boundary detection from actual speech timing
  • Automatic fallback to text-weighted sync if Whisper unavailable
  • YouTube Shorts safe-zone captioning
  • Real-time FFmpeg progress logging
  • Configurable voiceover + background music mixing
  • Ken Burns zoom with anti-jitter sharpening
  • Found-footage film grade (grain, vignette, cold color, shake)
  • Smart Transition Snaps (white flash / VHS glitch / zoom jump)
  • Synced audio SFX pops at every scene cut

Usage:
    python3 "video engine.py"

Dependencies:
    pip install faster-whisper   (optional — enables AI sync)
"""

import subprocess
import os
import sys
import time
import json
import math
import tempfile
import shutil
import re
import unicodedata
import random

# ── Optional: faster-whisper for AI transcription sync ──
WHISPER_AVAILABLE = False
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    pass

# ══════════════════════════════════════════════
#  DYNAMIC TOOL RESOLUTION
# ══════════════════════════════════════════════

def resolve_tool(name):
    """Find a CLI tool on the system, with fallback paths."""
    path = shutil.which(name)
    if path:
        return path
    fallbacks = [
        f"/usr/local/bin/{name}",
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/opt/ffmpeg-full/bin/{name}",
        f"/usr/local/opt/ffmpeg/bin/{name}",
    ]
    for fb in fallbacks:
        if os.path.isfile(fb) and os.access(fb, os.X_OK):
            return fb
    return None

FFMPEG_BIN  = resolve_tool("ffmpeg")
FFPROBE_BIN = resolve_tool("ffprobe")


# ══════════════════════════════════════════════
#  PROJECT CONFIG — change these for each video
# ══════════════════════════════════════════════

ASSETS_DIR     = "/Users/vanshsehrawat/Desktop/new horror style/"

VOICEOVER_FILE = "voiceover_short.mp3"            # Layer 1 — main narration
BGM_FILE       = "bg 3 .mp3"                         # Layer 2 — atmospheric music (optional)
OUTPUT_FILE    = "/Users/vanshsehrawat/Desktop/new horror style/midnight_mimic_final.mp4"      # final render output

IMAGE_PREFIX   = "scene_"

# ── Universal Auto-Config ────────────────────
AUTO_DETECT_SCENES = True       # auto-count images from ASSETS_DIR
SCRIPT_FILE        = "script_short.txt"  # one sentence per line (overrides SCENE_TEXTS if found)
OUTRO_HOLD         = 2.5          # seconds to hold final frame after VO ends (0 = disabled)
VO_NORMALIZE       = True         # EBU R128 loudness normalization on voiceover

# ══════════════════════════════════════════════
#  SCENE TEXTS — word-by-word pop-up captions
# ══════════════════════════════════════════════

SCENE_TEXTS = [
    "Did you know there’s a forbidden video from a murder case in Florida?",
    "In 2021, a woman named Lila lived alone in a rented house near Tampa.",
    "She installed a camera in her bedroom after hearing footsteps at night.",
    "Every morning, the footage looked normal. Until one night at 3:42 a.m.",
    "The camera showed someone standing over her bed. Tall. Unmoving. Faceless.",
    "For six minutes, it didn’t breathe. Didn’t blink. Didn’t move.",
    "Then its jaw opened. Too wide. Skin splitting. Blood running down its neck.",
    "It leaned close to her ear and whispered: “I’ve been eating you in your sleep.”",
    "Lila never woke up. Her mother received one final video.",
    "It showed Lila sitting up. Eyes missing. Face torn. Smiling.",
    "Trying to scream... with something moving inside her throat.",
    "When police arrived, the house was empty. No body. No blood.",
    "Just the camera. Still recording. Still pointed at the bed. Waiting.",
]

# ── CAPTION STYLING ──────────────────────────
CAPTIONS_ENABLED   = True
CAPTION_FONT       = "Arial Black"
CAPTION_FONTSIZE   = 58
CAPTION_COLOR      = "&H0000FFFF"
CAPTION_OUTLINE_CLR= "&H00000000"
CAPTION_OUTLINE_SZ = 4
CAPTION_SHADOW_SZ  = 1
CAPTION_WORDS_PER_CHUNK = 3

# ── YOUTUBE SHORTS SAFE-ZONE ─────────────────
CAPTION_ALIGNMENT  = 2
CAPTION_MARGIN_V   = 380
CAPTION_MARGIN_L   = 30
CAPTION_MARGIN_R   = 110


# ══════════════════════════════════════════════
#  AUDIO MIX
# ══════════════════════════════════════════════

VO_VOLUME      = 1.0
BGM_VOLUME     = 0.30


# ══════════════════════════════════════════════
#  TIMING & ENCODING
# ══════════════════════════════════════════════

# AUTO_SYNC modes:
#   "whisper"       — AI transcription for exact word timestamps + scene boundaries
#   "text_weighted" — allocate time proportional to word count (fallback)
#   "proportional"  — scale all durations equally
#   "off"           — use SCENE_DURATIONS exactly as written
AUTO_SYNC = "whisper"

# Whisper model size: "tiny", "base", "small", "medium", "large-v3"
# "base" is the best balance of speed and accuracy for short-form content.
WHISPER_MODEL_SIZE = "base"

SCENE_DURATIONS = [
    5.0,  # Image 1
    4.0,  # Image 2
    5.0,  # Image 3
    5.0,  # Image 4
    4.0,  # Image 5
    4.0,  # Image 6
    4.0,  # Image 7
    5.0,  # Image 8
    5.0,  # Image 9
    4.0,  # Image 10
    5.0,  # Image 11
    4.0,  # Image 12
    2.0,  # Image 13
]

NUM_SCENES      = 13
FPS             = 30
SNAP_DUR        = 0.15        # transition duration (short = snappy)
OUTPUT_W, OUTPUT_H = 768, 1408


# ══════════════════════════════════════════════
#  VISUAL TIMELINE (Manual Image Timing)
# ══════════════════════════════════════════════
# When enabled, images change at the specified times regardless of speech.
# Captions still sync to speech (Whisper AI or fallback).
# "image" = image number (1-based), "start_time" = seconds in the video.
# The last image stays until the end of the voiceover.

USE_VISUAL_TIMELINE = False

VISUAL_TIMELINE = [
    {"image": 1, "start_time": 0.0},
    {"image": 2, "start_time": 3.5},
    {"image": 3, "start_time": 7.0},
    {"image": 4, "start_time": 10.5},
    {"image": 5, "start_time": 14.0},
    {"image": 6, "start_time": 17.0},
    {"image": 7, "start_time": 20.0},
    {"image": 8, "start_time": 23.0},
    {"image": 9, "start_time": 27.0},
    {"image": 10, "start_time": 31.0},
    {"image": 11, "start_time": 34.0},
    {"image": 12, "start_time": 38.0},
    {"image": 13, "start_time": 42.0},
]


# ══════════════════════════════════════════════
#  SMART TRANSITION SNAPS
# ══════════════════════════════════════════════
# Three snap types randomly alternate at each scene cut.
# Set SNAP_SEED for reproducible random order across runs.

SNAP_ENABLED     = True
SNAP_SEED        = 42          # random seed (change for different order)
SNAP_SFX_ENABLED = True        # audio pop at each transition
SNAP_SFX_VOLUME  = 0.06        # SFX loudness (0.0 – 1.0)

# Snap type definitions — maps to FFmpeg xfade transitions
# Each entry: (name, xfade_transition, sfx_type)
#   sfx_type: "click" = high-freq sine, "static" = white noise, "whomp" = low sine
SNAP_TYPES = [
    ("White Flash",    "fadewhite",  "click"),    # camera flash snap
    ("Static Flicker", "pixelize",   "static"),   # VHS digital glitch
    ("Zoom Jump",      "zoomin",     "whomp"),     # punch-in zoom
]


# ══════════════════════════════════════════════
#  KEN BURNS ZOOM
# ══════════════════════════════════════════════

UPSCALE_W, UPSCALE_H = 960, 1760
ZOOM_INCREMENT       = "0.0005"


# ══════════════════════════════════════════════
#  HANDHELD SHAKE
# ══════════════════════════════════════════════

SHAKE_ENABLED    = True
SHAKE_MARGIN     = 16
SHAKE_AMPLITUDE  = 3
SHAKE_SPEED_X    = 5.7
SHAKE_SPEED_Y    = 4.3
SHAKE_SPEED_X2   = 3.1
SHAKE_SPEED_Y2   = 2.9


# ══════════════════════════════════════════════
#  HORROR FILM GRADE
# ══════════════════════════════════════════════

SHARPEN_ENABLED  = True
SHARPEN_LUMA_X   = 5
SHARPEN_LUMA_Y   = 5
SHARPEN_LUMA_AMT = 0.8
SHARPEN_CHR_X    = 5
SHARPEN_CHR_Y    = 5
SHARPEN_CHR_AMT  = 0.4

GRADE_ENABLED    = True
GRADE_CONTRAST   = 1.35
GRADE_BRIGHTNESS = -0.06
GRADE_SATURATION = 0.65
GRADE_GAMMA      = 0.95
CB_SHADOWS_R     = -0.06
CB_SHADOWS_G     = -0.03
CB_SHADOWS_B     = 0.14
CB_MIDS_R        = -0.03
CB_MIDS_G        = -0.02
CB_MIDS_B        = 0.08
CB_HIGHS_R       = -0.02
CB_HIGHS_G       = -0.01
CB_HIGHS_B       = 0.06

GRAIN_ENABLED    = True
GRAIN_STRENGTH   = 14
GRAIN_FLAGS      = "t+u"

VIGNETTE_ENABLED = False
VIGNETTE_ANGLE   = "PI/3.5"


# ══════════════════════════════════════════════
#  STUDIO ENHANCEMENTS
# ══════════════════════════════════════════════

# ── Chromatic Aberration (Horror Lens Distortion) ──
CHROMA_AB_ENABLED = True
CHROMA_AB_RH      = 3           # red channel horizontal shift (px)
CHROMA_AB_BH      = -3          # blue channel horizontal shift (px)

# ── Brightness Flicker (Dying Light Effect) ──────
FLICKER_ENABLED   = True
FLICKER_AMOUNT    = 0.015       # brightness oscillation amplitude
FLICKER_SPEED     = 6.0         # oscillation frequency (Hz)

# ── Alternating Zoom Direction ───────────────────
ALT_ZOOM_ENABLED  = True        # even scenes push-in, odd scenes pull-out

# ── Flash Frame (Subliminal Shock) ───────────────
FLASH_ENABLED     = True
FLASH_SCENES      = [7]         # 1-based scene indices to flash before
FLASH_FRAMES      = 3           # white frames (3 @ 30fps = 0.1s)

# ── Cinematic Letterboxing ───────────────────────
LETTERBOX_ENABLED = True
LETTERBOX_HEIGHT  = 50          # px per bar (top + bottom)

# ── Scanlines (CRT / VHS Overlay) ────────────────
SCANLINES_ENABLED = True
SCANLINES_OPACITY = 0.08        # line darkness (0.0 – 1.0)

# ── Sub-Bass Rumble (Horror Drone) ───────────────
RUMBLE_ENABLED    = True
RUMBLE_FREQ       = 40          # Hz (30–60 for deep dread)
RUMBLE_VOLUME     = 0.03        # very subtle, felt more than heard

# ── Audio Ducking (Sidechain Compression) ────────
DUCKING_ENABLED   = True        # BGM auto-ducks when VO speaks


# ══════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════

def get_audio_duration(audio_path):
    """Use ffprobe to get the exact duration of an audio file."""
    if not FFPROBE_BIN:
        return None
    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
             "-show_format", audio_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
    except Exception:
        pass
    return None


def normalize_word(word):
    """Normalize a word for fuzzy matching: lowercase, strip punctuation & unicode."""
    word = word.lower().strip()
    # Replace common unicode chars
    word = word.replace("\u2019", "'").replace("\u2018", "'")
    word = word.replace("\u201c", "").replace("\u201d", "")
    word = word.replace("\u2026", "")
    # Strip all non-alphanumeric except apostrophes
    word = re.sub(r"[^a-z0-9']", "", word)
    return word


def discover_scene_images(assets_dir, prefix):
    """Scan assets folder for images matching {prefix}{N}.png.

    Returns sorted list of image numbers found.
    E.g. ["scene_1.png", "scene_2.png", "scene_5.png"] → [1, 2, 5]
    """
    pattern = re.compile(re.escape(prefix) + r"(\d+)\.png$", re.IGNORECASE)
    image_nums = []
    for fname in os.listdir(assets_dir):
        m = pattern.match(fname)
        if m:
            image_nums.append(int(m.group(1)))
    image_nums.sort()
    return image_nums


def load_script_file(assets_dir, script_filename):
    """Read script.txt — one sentence per line, skip blank lines.

    Returns list of sentences, or None if file not found.
    """
    path = os.path.join(assets_dir, script_filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines if lines else None


def compute_synced_durations(vo_duration, mode="proportional"):
    """Compute scene durations scaled to match the voiceover length."""
    total_overlap = (NUM_SCENES - 1) * SNAP_DUR
    target_sum = vo_duration + total_overlap

    if mode == "text_weighted" and SCENE_TEXTS:
        MIN_SCENE_DUR = 1.5
        word_counts = []
        for i in range(NUM_SCENES):
            text = SCENE_TEXTS[i].strip() if i < len(SCENE_TEXTS) else ""
            wc = len(text.split()) if text else 1
            word_counts.append(wc)

        total_words = sum(word_counts)
        raw_weighted = [(wc / total_words) * target_sum for wc in word_counts]

        deficit = 0.0
        above_min = 0
        for d in raw_weighted:
            if d < MIN_SCENE_DUR:
                deficit += MIN_SCENE_DUR - d
            else:
                above_min += 1

        durations = []
        for d in raw_weighted:
            if d < MIN_SCENE_DUR:
                durations.append(MIN_SCENE_DUR)
            else:
                durations.append(d - (deficit / above_min if above_min > 0 else 0))

        current_sum = sum(durations)
        if abs(current_sum - target_sum) > 0.01:
            correction = (target_sum - current_sum) / NUM_SCENES
            durations = [d + correction for d in durations]

        return durations
    else:
        raw_sum = sum(SCENE_DURATIONS)
        scale_factor = target_sum / raw_sum
        return [d * scale_factor for d in SCENE_DURATIONS]


def seconds_to_ass_time(seconds):
    """Convert seconds to ASS timestamp format: H:MM:SS.CC."""
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def compute_scene_starts(durations):
    """Compute subtitle start times for each scene in effective video time."""
    starts = [0.0]
    for i in range(1, len(durations)):
        t = sum(durations[:i]) - i * SNAP_DUR
        starts.append(t)
    return starts


def chunk_words(text, max_per_chunk):
    """Split text into chunks of up to max_per_chunk words."""
    words = text.split()
    if not words:
        return []

    total = len(words)
    num_chunks = math.ceil(total / max_per_chunk)

    base = total // num_chunks
    remainder = total % num_chunks

    chunks = []
    idx = 0
    for c in range(num_chunks):
        size = base + (1 if c < remainder else 0)
        chunks.append(" ".join(words[idx : idx + size]))
        idx += size

    return chunks


def format_time_hms(seconds):
    """Format seconds as MM:SS for display."""
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:05.2f}"


# ══════════════════════════════════════════════
#  WHISPER AI TRANSCRIPTION
# ══════════════════════════════════════════════

def get_word_level_timestamps(audio_path):
    """Transcribe audio using faster-whisper and return word-level timestamps.

    Returns:
        list of dicts: [{"word": "hello", "start": 0.0, "end": 0.5}, ...]
        None if transcription fails.
    """
    if not WHISPER_AVAILABLE:
        return None

    print(f"  ⏳ Loading Whisper model '{WHISPER_MODEL_SIZE}'...")
    try:
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    except Exception as e:
        print(f"  ⚠ Whisper model load failed: {e}")
        return None

    print(f"  ⏳ Transcribing audio (this may take a moment)...")
    try:
        segments, info = model.transcribe(
            audio_path,
            word_timestamps=True,
            language="en",
        )

        word_list = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    word_list.append({
                        "word": w.word.strip(),
                        "start": w.start,
                        "end": w.end,
                    })

        if not word_list:
            print("  ⚠ Whisper returned no words.")
            return None

        print(f"  ✓ Transcribed {len(word_list)} words "
              f"({word_list[0]['start']:.2f}s → {word_list[-1]['end']:.2f}s)")
        return word_list

    except Exception as e:
        print(f"  ⚠ Whisper transcription failed: {e}")
        return None


def match_scene_texts_to_whisper(whisper_words):
    """Match SCENE_TEXTS to Whisper word timestamps using sequential alignment.

    For each scene, finds the best matching span of Whisper words by walking
    through the transcript in order. Uses fuzzy word matching to handle
    minor transcription differences (e.g., "Haru" vs "haru", punctuation).

    Returns:
        scene_word_map: list of lists, each containing dicts with
            {"word": "ORIGINAL", "start": float, "end": float}
        scene_boundaries: list of (start_time, end_time) per scene
    """
    if not whisper_words:
        return None, None

    # Build normalized whisper word list for matching
    w_normalized = [normalize_word(w["word"]) for w in whisper_words]
    w_idx = 0  # cursor position in whisper transcript

    scene_word_map = []      # per-scene list of timed words
    scene_boundaries = []    # per-scene (start, end) in audio time

    for scene_idx in range(len(SCENE_TEXTS)):
        text = SCENE_TEXTS[scene_idx].strip() if scene_idx < len(SCENE_TEXTS) else ""
        if not text:
            scene_word_map.append([])
            scene_boundaries.append(None)
            continue

        scene_words_raw = text.split()
        scene_normalized = [normalize_word(w) for w in scene_words_raw]

        matched_words = []
        scene_start = None
        scene_end = None

        for s_word_idx, s_norm in enumerate(scene_normalized):
            if not s_norm:  # skip empty after normalization (e.g., pure punctuation)
                continue

            # Search forward in whisper transcript for a match
            best_match_idx = None
            search_limit = min(w_idx + 15, len(w_normalized))  # look ahead up to 15 words

            for wi in range(w_idx, search_limit):
                if w_normalized[wi] == s_norm:
                    best_match_idx = wi
                    break
                # Fuzzy: check if one contains the other (handles contractions)
                if s_norm in w_normalized[wi] or w_normalized[wi] in s_norm:
                    best_match_idx = wi
                    break

            if best_match_idx is not None:
                wdata = whisper_words[best_match_idx]
                matched_words.append({
                    "word": scene_words_raw[s_word_idx].upper(),
                    "start": wdata["start"],
                    "end": wdata["end"],
                })
                if scene_start is None:
                    scene_start = wdata["start"]
                scene_end = wdata["end"]
                w_idx = best_match_idx + 1  # advance cursor past this match
            else:
                # No match found — use interpolation later
                matched_words.append({
                    "word": scene_words_raw[s_word_idx].upper(),
                    "start": None,
                    "end": None,
                })

        # Interpolate any unmatched words within the scene's time span
        if scene_start is not None and scene_end is not None and matched_words:
            # Fill in unmatched words by interpolating between known timestamps
            known_times = [(i, mw["start"]) for i, mw in enumerate(matched_words) if mw["start"] is not None]
            for i, mw in enumerate(matched_words):
                if mw["start"] is None:
                    # Find nearest known timestamps before and after
                    before = [(ki, kt) for ki, kt in known_times if ki < i]
                    after = [(ki, kt) for ki, kt in known_times if ki > i]
                    if before and after:
                        b_idx, b_time = before[-1]
                        a_idx, a_time = after[0]
                        ratio = (i - b_idx) / (a_idx - b_idx)
                        interp_start = b_time + ratio * (a_time - b_time)
                        interp_dur = (a_time - b_time) / (a_idx - b_idx)
                        mw["start"] = interp_start
                        mw["end"] = interp_start + interp_dur
                    elif before:
                        b_idx, b_time = before[-1]
                        mw["start"] = b_time + 0.3 * (i - b_idx)
                        mw["end"] = mw["start"] + 0.3
                    elif after:
                        a_idx, a_time = after[0]
                        mw["start"] = max(0, a_time - 0.3 * (a_idx - i))
                        mw["end"] = mw["start"] + 0.3

        scene_word_map.append(matched_words)
        scene_boundaries.append((scene_start, scene_end) if scene_start is not None else None)

    return scene_word_map, scene_boundaries


def compute_whisper_durations(scene_boundaries, vo_duration):
    """Derive scene durations from Whisper-detected speech boundaries.

    Uses the start of each scene's first word and end of last word to
    define where each scene should begin and end. Adds padding for natural
    pacing (brief pause before speech starts + hold after it ends).
    """
    total_overlap = (NUM_SCENES - 1) * SNAP_DUR
    MIN_SCENE_DUR = 1.5
    PADDING_BEFORE = 0.3   # seconds of visual lead-in before speech starts
    PADDING_AFTER  = 0.3   # seconds to hold after speech ends

    # Collect raw boundaries: (speech_start, speech_end) per scene
    raw_starts = []
    raw_ends = []

    for i, bounds in enumerate(scene_boundaries):
        if bounds is not None:
            raw_starts.append(bounds[0])
            raw_ends.append(bounds[1])
        else:
            # No speech detected for this scene — use previous end + small gap
            prev_end = raw_ends[-1] if raw_ends else 0.0
            raw_starts.append(prev_end + 0.1)
            raw_ends.append(prev_end + MIN_SCENE_DUR)

    # Derive scene cut points from midpoints between speech end and next speech start
    cut_points = [0.0]  # video starts at 0
    for i in range(len(raw_starts) - 1):
        # Cut point = midpoint between current scene's last word end
        # and next scene's first word start (with padding bias)
        gap_start = raw_ends[i] + PADDING_AFTER
        gap_end   = raw_starts[i + 1] - PADDING_BEFORE

        if gap_end > gap_start:
            cut = (gap_start + gap_end) / 2.0
        else:
            # Overlapping speech — cut at average
            cut = (raw_ends[i] + raw_starts[i + 1]) / 2.0

        cut_points.append(cut)
    cut_points.append(vo_duration)  # last scene extends to end of audio

    # Convert cut points to durations (in the padded timeline for zoompan)
    durations = []
    for i in range(NUM_SCENES):
        dur = cut_points[i + 1] - cut_points[i]
        # Add crossfade overlap back for the internal timeline
        dur_with_overlap = dur + (SNAP_DUR if i < NUM_SCENES - 1 else 0)
        durations.append(max(dur_with_overlap, MIN_SCENE_DUR))

    # Verify effective duration matches VO
    effective = sum(durations) - total_overlap
    if abs(effective - vo_duration) > 0.1:
        # Distribute the correction evenly
        correction = (vo_duration + total_overlap - sum(durations)) / NUM_SCENES
        durations = [d + correction for d in durations]

    return durations, cut_points


def compute_timeline_durations(visual_timeline, total_duration):
    """Convert VISUAL_TIMELINE start_times to internal pipeline durations.

    Returns:
        durations: list of internal scene durations (includes xfade overlap)
        sorted_tl: timeline sorted by start_time
    """
    sorted_tl = sorted(visual_timeline, key=lambda e: e["start_time"])
    start_times = [e["start_time"] for e in sorted_tl]
    n = len(sorted_tl)
    durations = []
    for i in range(n - 1):
        eff = start_times[i + 1] - start_times[i]
        durations.append(eff + SNAP_DUR)  # add overlap for crossfade
    durations.append(total_duration - start_times[-1])  # last scene, no overlap
    return durations, sorted_tl


# ══════════════════════════════════════════════
#  ASS SUBTITLE GENERATORS
# ══════════════════════════════════════════════

def get_ass_header():
    """Return the common ASS file header."""
    return f"""[Script Info]
Title: Horror Shorts Captions
ScriptType: v4.00+
PlayResX: {OUTPUT_W}
PlayResY: {OUTPUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{CAPTION_FONT},{CAPTION_FONTSIZE},{CAPTION_COLOR}&,&H000000FF&,{CAPTION_OUTLINE_CLR}&,&H80000000&,-1,0,0,0,100,100,2,0,1,{CAPTION_OUTLINE_SZ},{CAPTION_SHADOW_SZ},{CAPTION_ALIGNMENT},{CAPTION_MARGIN_L},{CAPTION_MARGIN_R},{CAPTION_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generate_ass_whisper(scene_word_map, cut_points):
    """Generate ASS subtitles using Whisper's exact word timestamps.

    Groups words into chunks of CAPTION_WORDS_PER_CHUNK and uses the
    actual speech timestamps for start/end of each chunk.
    """
    header = get_ass_header()
    dialogue_lines = []

    for scene_idx in range(len(scene_word_map)):
        timed_words = scene_word_map[scene_idx]
        if not timed_words:
            continue

        # Filter out any words still without timing
        valid_words = [w for w in timed_words if w["start"] is not None]
        if not valid_words:
            continue

        # Group into chunks
        total = len(valid_words)
        num_chunks = math.ceil(total / CAPTION_WORDS_PER_CHUNK)
        base = total // num_chunks
        remainder = total % num_chunks

        idx = 0
        for c in range(num_chunks):
            size = base + (1 if c < remainder else 0)
            chunk_words_list = valid_words[idx : idx + size]
            idx += size

            if not chunk_words_list:
                continue

            chunk_text = " ".join(w["word"] for w in chunk_words_list)
            c_start = chunk_words_list[0]["start"]
            c_end = chunk_words_list[-1]["end"]

            # Ensure minimum visibility of 0.3s
            if c_end - c_start < 0.3:
                c_end = c_start + 0.3

            # Clamp to video timeline (cut_points define scene boundaries)
            # The subtitle times are in audio time which maps 1:1 to video time
            start_ts = seconds_to_ass_time(c_start)
            end_ts = seconds_to_ass_time(c_end)
            dialogue_lines.append(
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{chunk_text}"
            )

    ass_content = header + "\n".join(dialogue_lines) + "\n"
    ass_path = os.path.join(os.getcwd(), "temp_captions.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return ass_path


def generate_ass_fallback(durations, vo_duration=None):
    """Generate ASS subtitles using equal-time chunking (fallback mode).

    When USE_VISUAL_TIMELINE is active, durations refer to visual scenes
    (which may differ in count from SCENE_TEXTS). In that case, we distribute
    text proportionally over vo_duration instead.
    """
    num_texts = len(SCENE_TEXTS)
    header = get_ass_header()
    dialogue_lines = []

    if USE_VISUAL_TIMELINE and vo_duration:
        # Distribute text proportionally over the total VO duration
        word_counts = [len(t.split()) for t in SCENE_TEXTS]
        total_words = max(sum(word_counts), 1)
        text_starts = [0.0]
        for i in range(num_texts - 1):
            text_starts.append(text_starts[-1] + (word_counts[i] / total_words) * vo_duration)
        text_ends = text_starts[1:] + [vo_duration]
    else:
        # Legacy mode: use visual scene durations (1:1 with texts)
        text_starts = compute_scene_starts(durations)
        n_overlap = len(durations) - 1
        effective_video = sum(durations) - n_overlap * SNAP_DUR
        text_ends = list(text_starts[1:]) + [effective_video]

    for scene_idx in range(num_texts):
        text = SCENE_TEXTS[scene_idx].strip()
        if not text:
            continue

        text_upper = text.upper()
        chunks = chunk_words(text_upper, CAPTION_WORDS_PER_CHUNK)
        if not chunks:
            continue

        scene_start = text_starts[scene_idx]
        scene_end = text_ends[scene_idx]
        scene_dur = scene_end - scene_start
        chunk_dur = scene_dur / len(chunks)

        for c_idx, chunk_text in enumerate(chunks):
            c_start = scene_start + c_idx * chunk_dur
            c_end   = scene_start + (c_idx + 1) * chunk_dur
            start_ts = seconds_to_ass_time(c_start)
            end_ts   = seconds_to_ass_time(c_end)
            dialogue_lines.append(
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{chunk_text}"
            )

    ass_content = header + "\n".join(dialogue_lines) + "\n"
    ass_path = os.path.join(os.getcwd(), "temp_captions.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return ass_path


# ══════════════════════════════════════════════
#  PER-SCENE FILTER CHAIN
# ══════════════════════════════════════════════

def build_scene_filter(index, num_frames):
    parts = []
    parts.append(f"scale={UPSCALE_W}:{UPSCALE_H}")
    if SHAKE_ENABLED:
        zp_w = OUTPUT_W + SHAKE_MARGIN
        zp_h = OUTPUT_H + SHAKE_MARGIN
    else:
        zp_w = OUTPUT_W
        zp_h = OUTPUT_H

    # Alternating zoom: even scenes push-in, odd scenes pull-out
    if ALT_ZOOM_ENABLED and index % 2 == 1:
        max_zoom = 1.0 + float(ZOOM_INCREMENT) * num_frames
        parts.append(
            f"zoompan=z='if(eq(on,0),{max_zoom:.6f},zoom-{ZOOM_INCREMENT})':"
            f"d={num_frames}:s={zp_w}x{zp_h}:fps={FPS}"
        )
    else:
        parts.append(f"zoompan=z='zoom+{ZOOM_INCREMENT}':d={num_frames}:s={zp_w}x{zp_h}:fps={FPS}")
    parts.append("setsar=1")

    if SHAKE_ENABLED:
        cx, cy, a = SHAKE_MARGIN // 2, SHAKE_MARGIN // 2, SHAKE_AMPLITUDE
        parts.append(f"crop={OUTPUT_W}:{OUTPUT_H}:'{cx}+{a}*sin(t*{SHAKE_SPEED_X})+{a-1}*sin(t*{SHAKE_SPEED_X2})':'{cy}+{a}*cos(t*{SHAKE_SPEED_Y})+{a-1}*cos(t*{SHAKE_SPEED_Y2})'")

    if SHARPEN_ENABLED:
        parts.append(f"unsharp={SHARPEN_LUMA_X}:{SHARPEN_LUMA_Y}:{SHARPEN_LUMA_AMT}:{SHARPEN_CHR_X}:{SHARPEN_CHR_Y}:{SHARPEN_CHR_AMT}")

    if GRADE_ENABLED:
        # Brightness flicker: subtle sine oscillation for eerie dying-light feel
        if FLICKER_ENABLED:
            brightness_val = f"'{GRADE_BRIGHTNESS}+{FLICKER_AMOUNT}*sin(t*{FLICKER_SPEED})'"
            parts.append(
                f"eq=contrast={GRADE_CONTRAST}:brightness={brightness_val}"
                f":saturation={GRADE_SATURATION}:gamma={GRADE_GAMMA}:eval=frame"
            )
        else:
            parts.append(f"eq=contrast={GRADE_CONTRAST}:brightness={GRADE_BRIGHTNESS}:saturation={GRADE_SATURATION}:gamma={GRADE_GAMMA}")
        parts.append(f"colorbalance=rs={CB_SHADOWS_R}:gs={CB_SHADOWS_G}:bs={CB_SHADOWS_B}:rm={CB_MIDS_R}:gm={CB_MIDS_G}:bm={CB_MIDS_B}:rh={CB_HIGHS_R}:gh={CB_HIGHS_G}:bh={CB_HIGHS_B}")

    if GRAIN_ENABLED:
        parts.append(f"noise=c0s={GRAIN_STRENGTH}:c0f={GRAIN_FLAGS}")

    if VIGNETTE_ENABLED:
        parts.append(f"vignette={VIGNETTE_ANGLE}")

    # Chromatic aberration: subtle color fringing for horror/surveillance look
    if CHROMA_AB_ENABLED:
        parts.append(f"rgbashift=rh={CHROMA_AB_RH}:bh={CHROMA_AB_BH}")

    # Flash frame: brief white flash at the start of shock scenes
    if FLASH_ENABLED and (index + 1) in FLASH_SCENES:
        flash_dur = FLASH_FRAMES / FPS
        parts.append(f"fade=t=in:st=0:d={flash_dur:.4f}:color=white")

    chain = ",".join(parts)
    return f"[{index}:v]{chain}[v{index}]"


# ══════════════════════════════════════════════
#  FFMPEG COMMAND BUILDER
# ══════════════════════════════════════════════

def pick_snap_types(num_scenes=None):
    """Randomly assign a snap type to each transition."""
    n = num_scenes or NUM_SCENES
    rng = random.Random(SNAP_SEED)
    return [rng.choice(SNAP_TYPES) for _ in range(n - 1)]


def build_sfx_filter(snap_assignments, durations, num_scenes=None):
    """Generate FFmpeg filter chains for transition SFX audio pops.

    Creates a short synthesized sound at each transition offset:
      click  — 4kHz sine burst (camera shutter)
      static — white noise burst
      whomp  — 80Hz sine thud
    """
    n = num_scenes or NUM_SCENES
    sfx_filters = []
    sfx_labels = []

    for t in range(n - 1):
        _, _, sfx_type = snap_assignments[t]
        # Offset in effective video time
        offset_ms = int(sum(durations[:t + 1]) * 1000)

        if sfx_type == "click":
            src = f"sine=f=4000:d=0.08:sample_rate=44100,volume={SNAP_SFX_VOLUME}"
            src += ",afade=t=out:st=0.04:d=0.04"
        elif sfx_type == "static":
            src = f"anoisesrc=d=0.10:c=white:r=44100:a={SNAP_SFX_VOLUME}"
            src += ",afade=t=in:d=0.02,afade=t=out:st=0.08:d=0.02"
        else:  # whomp
            src = f"sine=f=80:d=0.12:sample_rate=44100,volume={SNAP_SFX_VOLUME * 1.2:.3f}"
            src += ",afade=t=out:st=0.05:d=0.07"

        label = f"sfx{t}"
        # Position the SFX at the transition offset using adelay
        sfx_filters.append(f"{src},adelay={offset_ms}|{offset_ms},apad=whole_dur=1[{label}]")
        sfx_labels.append(f"[{label}]")

    # Mix all SFX into one track
    n = len(sfx_labels)
    mix_input = "".join(sfx_labels)
    sfx_filters.append(f"{mix_input}amix=inputs={n}:duration=longest:normalize=0[snap_sfx]")

    return sfx_filters


def build_ffmpeg_command(durations, has_bgm, ass_path=None, total_duration=None,
                        image_indices=None, num_visual_scenes=None):
    vo_path     = os.path.join(ASSETS_DIR, VOICEOVER_FILE)
    bgm_path    = os.path.join(ASSETS_DIR, BGM_FILE)
    output_path = os.path.join(ASSETS_DIR, OUTPUT_FILE)

    n_vis = num_visual_scenes or NUM_SCENES
    snap_assignments = pick_snap_types(n_vis) if SNAP_ENABLED else None

    # ── Load image inputs ───────────────────────
    inputs = []
    if image_indices:
        # Visual timeline mode: load images by index
        for i, img_num in enumerate(image_indices):
            img_path  = os.path.join(ASSETS_DIR, f"{IMAGE_PREFIX}{img_num}.png")
            scene_dur = durations[i] + (SNAP_DUR if i < n_vis - 1 else 0)
            inputs.extend(["-loop", "1", "-t", f"{scene_dur:.4f}", "-i", img_path])
    else:
        # Legacy mode: sequential images 1..N
        for i in range(1, n_vis + 1):
            img_path  = os.path.join(ASSETS_DIR, f"{IMAGE_PREFIX}{i}.png")
            scene_dur = durations[i - 1] + (SNAP_DUR if i < n_vis else 0)
            inputs.extend(["-loop", "1", "-t", f"{scene_dur:.4f}", "-i", img_path])
    inputs.extend(["-i", vo_path])
    if has_bgm:
        inputs.extend(["-stream_loop", "-1", "-i", bgm_path])

    filters = []
    for i in range(n_vis):
        scene_dur    = durations[i] + (SNAP_DUR if i < n_vis - 1 else 0)
        total_frames = int(scene_dur * FPS)
        filters.append(build_scene_filter(i, total_frames))

    # ── Video transitions ───────────────────────
    prev_label = "v0"
    for t in range(n_vis - 1):
        cumulative_dur = sum(durations[: t + 1])
        offset = cumulative_dur
        out_label = "v_xfade" if t == n_vis - 2 else f"x{t}"

        if SNAP_ENABLED and snap_assignments:
            _, xfade_type, _ = snap_assignments[t]
            filters.append(
                f"[{prev_label}][v{t + 1}]xfade=transition={xfade_type}"
                f":duration={SNAP_DUR}:offset={offset:.4f}[{out_label}]"
            )
        else:
            filters.append(
                f"[{prev_label}][v{t + 1}]xfade=transition=fade"
                f":duration={SNAP_DUR}:offset={offset:.4f}[{out_label}]"
            )
        prev_label = out_label

    last_label = prev_label if n_vis > 1 else "v0"
    if ass_path and CAPTIONS_ENABLED:
        filters.append(f"[{last_label}]ass=filename='temp_captions.ass'[v_graded]")
    else:
        filters.append(f"[{last_label}]null[v_graded]")

    # ── Audio: SFX generation at transitions ────
    use_sfx = SNAP_ENABLED and SNAP_SFX_ENABLED and snap_assignments
    if use_sfx:
        sfx_filters = build_sfx_filter(snap_assignments, durations, n_vis)
        filters.extend(sfx_filters)

    # ── Effective video duration for time-based effects ──
    vid_dur = total_duration if total_duration else sum(durations) - (n_vis - 1) * SNAP_DUR

    # ── Audio: mix VO + BGM (+ ducking) + SFX + Rumble ──
    vo_idx, bgm_idx = n_vis, n_vis + 1
    # Build VO filter chain: optional loudnorm + volume
    vo_chain = f"[{vo_idx}:a]"
    if VO_NORMALIZE:
        vo_chain += "loudnorm=I=-16:TP=-1.5:LRA=11,"
    vo_chain += f"volume={VO_VOLUME}[vo]"

    if has_bgm:
        filters.append(vo_chain)
        filters.append(f"[{bgm_idx}:a]volume={BGM_VOLUME}[bgm]")
        if DUCKING_ENABLED:
            # Sidechain compress: BGM auto-ducks when VO is present
            filters.append("[vo]asplit=2[vo_main][vo_sc]")
            filters.append(
                "[bgm][vo_sc]sidechaincompress=threshold=0.02:ratio=6"
                ":attack=200:release=1000[bgm_ducked]"
            )
            filters.append("[vo_main][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=3[a_mix]")
        else:
            filters.append("[vo][bgm]amix=inputs=2:duration=first:dropout_transition=3[a_mix]")
        a_current = "a_mix"
    else:
        # Solo VO — reuse vo_chain but output label is a_vo
        solo_chain = f"[{vo_idx}:a]"
        if VO_NORMALIZE:
            solo_chain += "loudnorm=I=-16:TP=-1.5:LRA=11,"
        solo_chain += f"volume={VO_VOLUME}[a_vo]"
        filters.append(solo_chain)
        a_current = "a_vo"

    # Mix in transition SFX
    if use_sfx:
        filters.append(f"[{a_current}][snap_sfx]amix=inputs=2:duration=first:weights=1 0.5[a_sfx]")
        a_current = "a_sfx"

    # Sub-bass horror rumble drone
    if RUMBLE_ENABLED:
        filters.append(
            f"sine=f={RUMBLE_FREQ}:d={vid_dur:.4f}:sample_rate=44100,"
            f"volume={RUMBLE_VOLUME}[rumble]"
        )
        filters.append(
            f"[{a_current}][rumble]amix=inputs=2:duration=first"
            f":weights=1 0.3:normalize=0[a_rumbled]"
        )
        a_current = "a_rumbled"

    # ── Video post-processing: letterbox, scanlines, fades ──
    v_fade_out_start = max(vid_dur - 2.0, 0)
    a_fade_out_start = max(vid_dur - 2.0, 0)

    v_post = []
    if LETTERBOX_ENABLED:
        v_post.append(f"drawbox=x=0:y=0:w=iw:h={LETTERBOX_HEIGHT}:color=black:t=fill")
        v_post.append(f"drawbox=x=0:y=ih-{LETTERBOX_HEIGHT}:w=iw:h={LETTERBOX_HEIGHT}:color=black:t=fill")
    if SCANLINES_ENABLED:
        v_post.append(f"drawgrid=w=iw:h=2:t=1:c=black@{SCANLINES_OPACITY}")
    v_post.append(f"fade=t=in:st=0:d=1.5")
    v_post.append(f"fade=t=out:st={v_fade_out_start:.4f}:d=2.0")

    v_chain = ",".join(v_post)
    filters.append(f"[v_graded]{v_chain}[v_final]")

    # Audio cinematic fades + outro hold
    a_fade_chain = f"[{a_current}]afade=t=in:st=0:d=1.0,afade=t=out:st={a_fade_out_start:.4f}:d=2.0"
    if OUTRO_HOLD > 0:
        a_fade_chain += f",apad=pad_dur={OUTRO_HOLD:.2f}"
    a_fade_chain += "[a_final]"
    filters.append(a_fade_chain)

    filter_complex = ";".join(filters)

    cmd = [
        FFMPEG_BIN, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v_final]",
        "-map", "[a_final]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-progress", "pipe:1",
        "-stats_period", "1",
        output_path,
    ]
    return cmd, snap_assignments


# ══════════════════════════════════════════════
#  REAL-TIME PROGRESS RENDERER
# ══════════════════════════════════════════════

def run_ffmpeg_with_progress(cmd, total_duration):
    """Run FFmpeg and display a real-time progress bar."""
    import threading
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stderr_lines = []
    def _drain_stderr():
        for err_line in process.stderr:
            stderr_lines.append(err_line)
    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    bar_width = 40
    start_time = time.time()
    current_time_s = 0.0
    last_print_len = 0

    try:
        for line in process.stdout:
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    us = int(line.split("=")[1])
                    current_time_s = us / 1_000_000.0
                except (ValueError, IndexError):
                    continue

                progress = min(current_time_s / total_duration, 1.0) if total_duration > 0 else 0
                filled = int(bar_width * progress)
                bar = "█" * filled + "░" * (bar_width - filled)
                pct = progress * 100

                elapsed = time.time() - start_time
                if progress > 0.01:
                    eta = (elapsed / progress) - elapsed
                    eta_str = f"ETA {eta:.0f}s"
                else:
                    eta_str = "ETA --"

                status = (
                    f"\r  ▸ Rendering: |{bar}| {pct:5.1f}%  "
                    f"{format_time_hms(current_time_s)} / {format_time_hms(total_duration)}  "
                    f"{eta_str}   "
                )
                status = status.ljust(last_print_len)
                last_print_len = len(status)
                sys.stdout.write(status)
                sys.stdout.flush()

            elif line.startswith("progress=end"):
                break

    except KeyboardInterrupt:
        process.kill()
        print("\n  ✗ Render cancelled by user.")
        sys.exit(1)

    process.wait()
    stderr_thread.join(timeout=2)
    sys.stdout.write("\n")
    sys.stdout.flush()

    stderr_output = "".join(stderr_lines)
    return process.returncode, stderr_output


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  UNIVERSAL VIDEO ENGINE — Horror Shorts")
    print("  AI Sync + Film Grade + Audio Mix + Captions")
    print("=" * 60)
    print()

    # ── CHECK TOOLS ─────────────────────────────
    if not FFMPEG_BIN:
        print("  ✗ ERROR: ffmpeg not found.  →  brew install ffmpeg")
        sys.exit(1)
    if not FFPROBE_BIN:
        print("  ✗ ERROR: ffprobe not found.  →  brew install ffmpeg")
        sys.exit(1)

    print(f"  ✓ ffmpeg       : {FFMPEG_BIN}")
    print(f"  ✓ ffprobe      : {FFPROBE_BIN}")
    print(f"  {'✓' if WHISPER_AVAILABLE else '⚠'} faster-whisper : "
          f"{'installed' if WHISPER_AVAILABLE else 'NOT INSTALLED (pip install faster-whisper)'}")
    print()

    # ── Auto-Discovery & Script Loading ─────────
    # These run before validation so NUM_SCENES and SCENE_TEXTS are correctly set.
    global NUM_SCENES, SCENE_TEXTS

    if AUTO_DETECT_SCENES:
        discovered = discover_scene_images(ASSETS_DIR, IMAGE_PREFIX)
        if discovered:
            NUM_SCENES = len(discovered)
            print(f"  ✓ Auto-detected   : {NUM_SCENES} images ({IMAGE_PREFIX}1..{discovered[-1]}.png)")
        else:
            print(f"  ⚠ No images matching '{IMAGE_PREFIX}*.png' found — using NUM_SCENES = {NUM_SCENES}")

    script_lines = load_script_file(ASSETS_DIR, SCRIPT_FILE)
    if script_lines:
        SCENE_TEXTS = script_lines
        print(f"  ✓ Script loaded   : {len(SCENE_TEXTS)} lines from {SCRIPT_FILE}")
    else:
        print(f"  ✓ Script source   : hardcoded SCENE_TEXTS ({len(SCENE_TEXTS)} lines)")

    # Auto-generate SCENE_DURATIONS if auto-detecting and count changed
    if AUTO_DETECT_SCENES and len(SCENE_DURATIONS) != NUM_SCENES:
        avg_dur = 4.0  # reasonable default per scene, will be overridden by sync
        globals()['SCENE_DURATIONS'] = [avg_dur] * NUM_SCENES

    print()

    # ── Validate arrays ─────────────────────
    num_visual_scenes = NUM_SCENES
    image_indices = None
    sorted_timeline = None

    if USE_VISUAL_TIMELINE:
        if not VISUAL_TIMELINE:
            print("  ✗ ERROR: VISUAL_TIMELINE is empty.")
            sys.exit(1)
        sorted_timeline = sorted(VISUAL_TIMELINE, key=lambda e: e["start_time"])
        num_visual_scenes = len(sorted_timeline)
        image_indices = [entry["image"] for entry in sorted_timeline]
        print(f"  ✓ Visual Timeline : {num_visual_scenes} cuts (manual timing)")
        print(f"  ✓ Text Scenes     : {len(SCENE_TEXTS)} sentences")
    else:
        if len(SCENE_DURATIONS) != NUM_SCENES:
            print(f"  ✗ ERROR: SCENE_DURATIONS has {len(SCENE_DURATIONS)} entries, "
                  f"expected {NUM_SCENES}.")
            sys.exit(1)

        if CAPTIONS_ENABLED and len(SCENE_TEXTS) != NUM_SCENES:
            print(f"  ✗ ERROR: SCENE_TEXTS has {len(SCENE_TEXTS)} entries, "
                  f"expected {NUM_SCENES}.")
            sys.exit(1)

    # ── Verify assets ───────────────────────
    vo_path  = os.path.join(ASSETS_DIR, VOICEOVER_FILE)
    bgm_path = os.path.join(ASSETS_DIR, BGM_FILE)

    missing_images = []
    if USE_VISUAL_TIMELINE:
        # Check all images referenced in the timeline
        needed_images = sorted(set(image_indices))
        for img_num in needed_images:
            p = os.path.join(ASSETS_DIR, f"{IMAGE_PREFIX}{img_num}.png")
            if not os.path.exists(p):
                missing_images.append(p)
    else:
        for i in range(1, NUM_SCENES + 1):
            p = os.path.join(ASSETS_DIR, f"{IMAGE_PREFIX}{i}.png")
            if not os.path.exists(p):
                missing_images.append(p)

    if missing_images:
        print("  ✗ ERROR: Missing images:")
        for m in missing_images:
            print(f"      {m}")
        sys.exit(1)

    if not os.path.exists(vo_path):
        print(f"  ✗ ERROR: VO missing: {vo_path}")
        sys.exit(1)

    has_bgm = os.path.exists(bgm_path)

    print("  ✓ All images found.")
    print(f"  ✓ Voiceover : {VOICEOVER_FILE}")
    if has_bgm:
        print(f"  ✓ BGM       : {BGM_FILE}  @ {int(BGM_VOLUME * 100)}% (auto-loop)")
    else:
        print(f"  ⚠ BGM       : {BGM_FILE} — not found, VO-only")
    print(f"  ✓ Output    : {OUTPUT_FILE}")
    print()

    # ── Probe VO duration ───────────────────────
    vo_duration = get_audio_duration(vo_path)
    if vo_duration is None:
        print("  ✗ ERROR: Could not detect VO duration.")
        sys.exit(1)

    print(f"  Voiceover duration : {vo_duration:.2f}s")

    # ════════════════════════════════════════
    #  SYNC MODE SELECTION
    # ════════════════════════════════════════

    whisper_words = None
    scene_word_map = None
    scene_boundaries = None
    cut_points = None
    sync_mode_used = AUTO_SYNC

    if USE_VISUAL_TIMELINE:
        # ── Visual Timeline: image timing is manual ──
        durations, sorted_timeline = compute_timeline_durations(VISUAL_TIMELINE, vo_duration)
        sync_mode_used = "visual_timeline"

        # Still run Whisper for caption timestamps (not image timing)
        if CAPTIONS_ENABLED and AUTO_SYNC == "whisper" and WHISPER_AVAILABLE:
            print()
            print("  ── AI Transcription (captions only) ─────")
            whisper_words = get_word_level_timestamps(vo_path)
            if whisper_words:
                scene_word_map, scene_boundaries = match_scene_texts_to_whisper(whisper_words)
                if scene_word_map:
                    matched = sum(1 for b in scene_boundaries if b is not None)
                    print(f"  ✓ Matched {matched}/{len(SCENE_TEXTS)} text scenes for captions")
                else:
                    print("  ⚠ Whisper matching failed — fallback captions will be used")
            else:
                print("  ⚠ Transcription failed — fallback captions will be used")

    elif AUTO_SYNC == "whisper":
        if WHISPER_AVAILABLE:
            print()
            print("  ── AI Transcription Pass ────────────────")
            whisper_words = get_word_level_timestamps(vo_path)

            if whisper_words:
                scene_word_map, scene_boundaries = match_scene_texts_to_whisper(whisper_words)

                if scene_boundaries:
                    matched = sum(1 for b in scene_boundaries if b is not None)
                    print(f"  ✓ Matched {matched}/{len(SCENE_TEXTS)} scene boundaries to audio")

                    durations, cut_points = compute_whisper_durations(scene_boundaries, vo_duration)
                    sync_mode_used = "whisper"
                    print(f"  ✓ Scene durations derived from speech timestamps")
                else:
                    print("  ⚠ Scene matching failed — falling back to text_weighted")
                    durations = compute_synced_durations(vo_duration, mode="text_weighted")
                    sync_mode_used = "text_weighted"
            else:
                print("  ⚠ Transcription failed — falling back to text_weighted")
                durations = compute_synced_durations(vo_duration, mode="text_weighted")
                sync_mode_used = "text_weighted"
        else:
            print("  ⚠ faster-whisper not installed — falling back to text_weighted")
            print("    Install with: pip install faster-whisper")
            durations = compute_synced_durations(vo_duration, mode="text_weighted")
            sync_mode_used = "text_weighted"

    elif AUTO_SYNC == "text_weighted":
        durations = compute_synced_durations(vo_duration, mode="text_weighted")
    elif AUTO_SYNC == "proportional" or AUTO_SYNC is True:
        durations = compute_synced_durations(vo_duration, mode="proportional")
        sync_mode_used = "proportional"
    else:
        durations = list(SCENE_DURATIONS)
        sync_mode_used = "off"

    print()
    sync_labels = {
        "visual_timeline": "VISUAL TIMELINE  (manual image timing)",
        "whisper": "WHISPER AI  (word-level timestamps)",
        "text_weighted": "TEXT-WEIGHTED  (by word count, fallback)",
        "proportional": "PROPORTIONAL  (equal scaling)",
        "off": "OFF  (manual durations)",
    }
    print(f"  Sync mode          : {sync_labels.get(sync_mode_used, sync_mode_used)}")

    total_scene_time = sum(durations)
    total_overlap    = (num_visual_scenes - 1) * SNAP_DUR
    effective_video  = total_scene_time - total_overlap

    # Apply outro hold: extend effective video duration
    if OUTRO_HOLD > 0:
        durations[-1] += OUTRO_HOLD
        effective_video += OUTRO_HOLD
        print(f"  Outro hold         : +{OUTRO_HOLD:.1f}s (last frame held)")

    print(f"  Effective video    : {effective_video:.2f}s")
    diff = effective_video - vo_duration - OUTRO_HOLD
    if abs(diff) < 0.5:
        print(f"  Sync delta         : {diff:+.2f}s  ✓")
    elif diff < -0.5:
        print(f"  ⚠  Video SHORTER than VO by {abs(diff):.2f}s!")
    else:
        print(f"  ⚠  Video LONGER by {diff:.2f}s — -shortest trims")

    print(f"  Resolution         : {OUTPUT_W}×{OUTPUT_H} (9:16)")
    print(f"  Codec              : libx264 High / AAC 192k / {FPS}fps")
    print(f"  VO Normalize       : {'ON  (EBU R128 loudnorm)' if VO_NORMALIZE else 'OFF'}")
    print()

    # ── Film grade summary ──────────────────────
    print("  Film Grade:")
    print(f"    Ken Burns     : ON  (+{ZOOM_INCREMENT}/frame)")
    print(f"    Alt Zoom      : {'ON  (push/pull alternate)' if ALT_ZOOM_ENABLED else 'OFF'}")
    print(f"    Shake         : {'ON  (±' + str(SHAKE_AMPLITUDE) + 'px)' if SHAKE_ENABLED else 'OFF'}")
    print(f"    Sharpen       : {'ON' if SHARPEN_ENABLED else 'OFF'}")
    print(f"    Color Grade   : {'ON' if GRADE_ENABLED else 'OFF'}")
    print(f"    Flicker       : {'ON  (amp ' + str(FLICKER_AMOUNT) + ', ' + str(FLICKER_SPEED) + 'Hz)' if FLICKER_ENABLED else 'OFF'}")
    print(f"    Film Grain    : {'ON  (str ' + str(GRAIN_STRENGTH) + ')' if GRAIN_ENABLED else 'OFF'}")
    print(f"    Vignette      : {'ON' if VIGNETTE_ENABLED else 'OFF'}")
    print(f"    Chroma Aberr  : {'ON  (±' + str(CHROMA_AB_RH) + 'px)' if CHROMA_AB_ENABLED else 'OFF'}")
    print(f"    Flash Frame   : {'ON  (scenes ' + str(FLASH_SCENES) + ')' if FLASH_ENABLED else 'OFF'}")
    print(f"    Letterbox     : {'ON  (' + str(LETTERBOX_HEIGHT) + 'px bars)' if LETTERBOX_ENABLED else 'OFF'}")
    print(f"    Scanlines     : {'ON  (opacity ' + str(SCANLINES_OPACITY) + ')' if SCANLINES_ENABLED else 'OFF'}")
    print(f"    Sub-Bass      : {'ON  (' + str(RUMBLE_FREQ) + 'Hz drone)' if RUMBLE_ENABLED else 'OFF'}")
    print(f"    Audio Ducking : {'ON  (sidechain compress)' if DUCKING_ENABLED and has_bgm else 'OFF'}")
    print()

    # ── Caption info ────────────────────────────
    if CAPTIONS_ENABLED:
        print("  Captions (YouTube Shorts Safe-Zone):")
        print(f"    Font          : {CAPTION_FONT} @ {CAPTION_FONTSIZE}px")
        print(f"    Sync source   : {'Whisper AI timestamps' if sync_mode_used == 'whisper' else 'equal-time chunking'}")
        print(f"    Words/chunk   : {CAPTION_WORDS_PER_CHUNK}")
        print()

    # ── Timing map ──────────────────────────
    print("  Timing Map:")
    if USE_VISUAL_TIMELINE:
        print("  ┌────────┬─────┬────────────────────────────┬──────────┐")
        print("  │  Cut   │ Img │  Timeline                  │ Duration │")
        print("  ├────────┼─────┼────────────────────────────┼──────────┤")
        cumulative = 0.0
        for i, dur in enumerate(durations, 1):
            end = cumulative + dur
            img_num = image_indices[i - 1] if image_indices else i
            print(f"  │  {i:2d}    │ {img_num:3d} │  {cumulative:6.2f}s  →  {end:6.2f}s      │  {dur:.2f}s   │")
            cumulative = end
        print("  └────────┴─────┴────────────────────────────┴──────────┘")
    elif sync_mode_used == "whisper" and scene_boundaries:
        print("  ┌────────┬────────────────────────────┬──────────┬──────────────────────┐")
        print("  │ Scene  │  Timeline                  │ Duration │ Speech Window         │")
        print("  ├────────┼────────────────────────────┼──────────┼──────────────────────┤")
        cumulative = 0.0
        for i, dur in enumerate(durations, 1):
            end = cumulative + dur
            bounds = scene_boundaries[i - 1] if i - 1 < len(scene_boundaries) else None
            if bounds:
                speech = f"{bounds[0]:5.2f}s → {bounds[1]:5.2f}s"
            else:
                speech = "  (no match)      "
            print(f"  │  {i:2d}    │  {cumulative:6.2f}s  →  {end:6.2f}s      │  {dur:.2f}s   │ {speech:>20s} │")
            cumulative = end
        print("  └────────┴────────────────────────────┴──────────┴──────────────────────┘")
    else:
        print("  ┌────────┬────────────────────────────┬──────────┬───────┐")
        print("  │ Scene  │  Timeline                  │ Duration │ Words │")
        print("  ├────────┼────────────────────────────┼──────────┼───────┤")
        cumulative = 0.0
        for i, dur in enumerate(durations, 1):
            end = cumulative + dur
            wc = len(SCENE_TEXTS[i-1].split()) if i-1 < len(SCENE_TEXTS) and SCENE_TEXTS[i-1].strip() else 0
            print(f"  │  {i:2d}    │  {cumulative:6.2f}s  →  {end:6.2f}s      │  {dur:.2f}s   │  {wc:3d}  │")
            cumulative = end
        print("  └────────┴────────────────────────────┴──────────┴───────┘")
    print()

    # ── Generate captions ─────────────────────
    ass_path = None
    if CAPTIONS_ENABLED:
        if sync_mode_used in ("whisper", "visual_timeline") and scene_word_map and cut_points:
            ass_path = generate_ass_whisper(scene_word_map, cut_points)
            print(f"  ✓ AI-synced captions generated: {os.path.basename(ass_path)}")
        elif sync_mode_used == "visual_timeline" and scene_word_map:
            # Whisper succeeded but no cut_points (timeline mode)
            ass_path = generate_ass_whisper(scene_word_map, None)
            print(f"  ✓ AI-synced captions generated: {os.path.basename(ass_path)}")
        else:
            ass_path = generate_ass_fallback(durations, vo_duration=vo_duration)
            print(f"  ✓ Fallback captions generated: {os.path.basename(ass_path)}")

    # ── Build & render ──────────────────────
    cmd, snap_assignments = build_ffmpeg_command(
        durations, has_bgm, ass_path,
        total_duration=effective_video,
        image_indices=image_indices,
        num_visual_scenes=num_visual_scenes,
    )

    # ── Snap transition map ─────────────────────
    if SNAP_ENABLED and snap_assignments:
        print("  Transition Snaps:")
        for t, (snap_name, _, sfx_type) in enumerate(snap_assignments):
            offset = sum(durations[:t + 1])
            print(f"    Cut {t+1:2d}  @ {offset:6.2f}s  →  {snap_name:<16s}  sfx:{sfx_type}")
        print()

    print("─" * 60)
    print("  Rendering with real-time progress...")
    print("─" * 60)
    print()

    start_time = time.time()
    returncode, stderr_output = run_ffmpeg_with_progress(cmd, effective_video)
    elapsed = time.time() - start_time

    if ass_path and os.path.exists(ass_path):
        try:
            os.remove(ass_path)
        except OSError:
            pass

    if returncode != 0:
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  RENDER FAILED                                         ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        print("FFmpeg stderr:")
        print(stderr_output[-3000:] if len(stderr_output) > 3000 else stderr_output)
        sys.exit(1)

    output_path = os.path.join(ASSETS_DIR, OUTPUT_FILE)
    size_mb = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  RENDER COMPLETE ✓                                     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  Output     : {output_path}")
    print(f"  Size       : {size_mb:.1f} MB")
    print(f"  Render time: {elapsed:.1f}s")
    print(f"  Sync mode  : {sync_mode_used}")
    print()


if __name__ == "__main__":
    main()
