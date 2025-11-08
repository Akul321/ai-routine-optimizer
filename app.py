# app.py — AI Routine Optimizer (Groq, auto-model version)

import os
import streamlit as st
from groq import Groq
from groq._exceptions import GroqError  # for robust error handling

from scheduler import Task, plan_day, format_blocks
from prompts import ROUTINE_INTRO_PROMPT, TASK_NOTE_PROMPT

st.set_page_config(page_title="AI Routine Optimizer", page_icon="🗓️", layout="centered")

# ---------- Groq setup ----------
GROQ_KEY = os.getenv("GROQ_API_KEY") or (st.secrets.get("GROQ_API_KEY") if hasattr(st, "secrets") else "")
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

@st.cache_data(show_spinner=False)
def list_models():
    """Return a list of model IDs available to this key; empty list if no key or error."""
    if not client:
        return []
    try:
        return [m.id for m in client.models.list().data]
    except Exception:
        return []

def choose_model(available: list[str]) -> str | None:
    """
    Pick a model defensively.
    1) Try preferred list in order if present.
    2) Else any 'llama' model.
    3) Else any 'mixtral' model.
    4) Else first available.
    """
    if not available:
        return None

    preferred = [
        # keep several candidates so this survives future renames
        "llama-3.3-70b-specdec",
        "llama-3.2-70b-text",
        "llama-3.2-11b-text-preview",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "llama-3.1-8b-instant",
        "mixtral-8x7b",
    ]
    for m in preferred:
        if m in available:
            return m
    for m in available:
        if "llama" in m.lower():
            return m
    for m in available:
        if "mixtral" in m.lower():
            return m
    return available[0]

def ai_reply(system_text: str, user_text: str) -> str:
    """Call Groq chat with automatic model selection + graceful retries."""
    if not client:
        return "(AI disabled: no GROQ_API_KEY found)"

    available = list_models()
    model = st.session_state.get("_groq_model") or choose_model(available)
    if not model:
        return "(AI unavailable: no accessible models for this key)"

    # try current choice; if 400/404 about model, rotate through others
    tried = set()
    while True:
        tried.add(model)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_text},
                    {"role": "user",   "content": user_text or ""},
                ],
                temperature=0.7,
                max_tokens=180,
            )
            st.session_state["_groq_model"] = model
            return (resp.choices[0].message.content or "").strip()
        except GroqError as e:
            msg = str(e)
            # handle decommissioned/not found → pick a different model
            if "model" in msg.lower() and ("decommission" in msg.lower() or "not found" in msg.lower()):
                # pick next candidate not yet tried
                candidates = [m for m in available if m not in tried]
                # fallback heuristics if list empty: re-fetch once
                if not candidates:
                    fresh = list_models()
                    candidates = [m for m in fresh if m not in tried]
                if not candidates:
                    return f"(AI error: all candidate models failed; last tried: {model})"
                model = choose_model(candidates)
                continue
            # other API errors: return readable message
            return f"(AI error: {e})"
        except Exception as e:
            return f"(AI error: {e})"

st.title("🗓️ AI Routine Optimizer")
st.caption("Fill your day’s timings and tasks → get a tidy plan with breaks and AI coaching (Groq).")

with st.sidebar:
    st.subheader("Day setup")
    wake = st.text_input("Wake-up time", "06:30 AM")
    sleep = st.text_input("Sleep time",  "10:30 PM")

    st.subheader("Breaks")
    break_every = st.slider("Break every (minutes of work)", 30, 120, 60, step=5)
    break_len   = st.slider("Break length (minutes)", 3, 15, 5, step=1)

    st.markdown("---")
    n = st.number_input("How many tasks?", 1, 12, 5)

st.subheader("Tasks")
cols = st.columns([3, 1, 1])
tasks: list[Task] = []
for i in range(int(n)):
    with cols[0]:
        name = st.text_input(f"Task {i+1}", f"Task {i+1}")
    with cols[1]:
        mins = st.number_input(f"Minutes {i+1}", 10, 240, 60, step=5)
    with cols[2]:
        prio = st.slider(f"Priority {i+1}", 1, 5, 3)
    tasks.append(Task(name=name.strip(), duration=int(mins), priority=int(prio)))

if st.button("Generate Plan", type="primary"):
    blocks = plan_day(wake, sleep, tasks, break_every=break_every, break_len=break_len)
    table = format_blocks(blocks)

    plan_text = "\n".join(f"{row['Time']} — {row['Task']}" for row in table)
    overview = ai_reply(ROUTINE_INTRO_PROMPT, plan_text)

    st.markdown("### Overview")
    st.write(overview)

    st.markdown("### Schedule")
    st.table(table)

    st.markdown("### Quick Tips")
    for row in table:
        if "Break" in row["Task"] or "Buffer" in row["Task"]:
            tip = "Breathe, stretch, sip water."
        else:
            tip = ai_reply(
                TASK_NOTE_PROMPT.format(block_time=row["Time"], task_name=row["Task"]),
                ""
            )
        st.write(f"**{row['Time']} {row['Task']}** — {tip}")
else:
    st.info("Enter your tasks, tweak priorities/durations, then click **Generate Plan**.")

# Footer: show model + availability to help debugging
available_now = list_models()
chosen = st.session_state.get("_groq_model")
status = ("✅ enabled — model: " + chosen) if chosen else ("🛈 key ok" if GROQ_KEY else "⚠️ AI disabled (no key)")
st.caption(f"AI status: {status} • Available models: {', '.join(available_now) if available_now else 'none'}")
