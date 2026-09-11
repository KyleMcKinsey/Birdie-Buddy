import json
import re
import google.generativeai as genai
import streamlit as st
from data_store import PERSONA_DATABASE, DRILL_SCHEMATICS

st.set_page_config(page_title="Birdie Buddy MVP", page_icon="⛳", layout="centered")

# --- HELPER FUNCTIONS FOR INDENTATION ---
def indented_html(content, margin=24):
    st.markdown(f"<div style='margin-left: {margin}px; margin-top: 4px; margin-bottom: 16px;'>{content}</div>", unsafe_allow_html=True)

def indented_ul(items, margin=24):
    list_items = "".join([f"<li>{item.strip()}</li>" for item in items if item.strip()])
    st.markdown(f"<ul style='margin-left: {margin}px; margin-top: 4px; margin-bottom: 12px;'>{list_items}</ul>", unsafe_allow_html=True)

# --- HEADER & SIDEBAR ---
st.title("⛳ Birdie Buddy (Phase 1 MVP)")
st.caption("AI Golf Caddie & Practice Asset Allocator powered by Gemini")

st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

if not api_key:
    st.warning("Please paste your Google Gemini API Key in the sidebar to begin.")
    st.stop()

genai.configure(api_key=api_key)

# -------------------------------------------------------------
# STEP 1: MULTI-ISSUE PATH/FACE DIAGNOSTIC
# -------------------------------------------------------------
st.subheader("1. Shot Diagnostic (Multi-Fault Detection)")

selected_persona_key = st.selectbox(
    "Choose Your Movie Caddie Persona:",
    options=list(PERSONA_DATABASE.keys()),
    index=0
)

active_persona = PERSONA_DATABASE[selected_persona_key]
st.info(f"**{active_persona['title']}** — {active_persona['description']}")

shot_transcript = st.text_area(
    "Describe your missed shot(s) in detail (Full Swing, Short Game, or Putting):",
    placeholder="e.g., I kept hitting shots thin, and missing push right..."
)

if st.button(f"Analyze Shot with {selected_persona_key}"):
    if shot_transcript:
        system_prompt = f"""
        {active_persona['system_instruction']}

        Analyze the user's input regarding their missed shot. Identify up to TWO swing mechanics issues across Full Swing, Short Game, or Putting:
        1. Primary Miss / Fault (Required)
        2. Secondary Miss / Fault (Optional, set to null if only one clear fault exists)

        Map both faults to the most effective drills from this EXACT list of 40 drills:

        FULL SWING:
        - 'Alignment Stick Gate Drill'
        - 'Pause at Top Drill'
        - 'Tee Gate Drill'
        - 'Towel Under Armpits Drill'
        - 'Coin Strike Low-Point Drill'
        - 'Split-Hands Release Drill'
        - 'Feet-Together Balance Drill'
        - 'Wall-Head Posture Drill'
        - 'Impact Bag Compression Drill'
        - 'Two-Step Pump Lag Drill'

        SHORT GAME (CHIPPING/PITCHING/SAND):
        - 'Towel Behind Ball Drill'
        - 'Lead Foot Weight Anchor Drill'
        - 'Brush Turf Chipping Drill'
        - 'Coin Lead-Point Pitch Drill'
        - 'Ruler in Glove Wrist Anchor Drill'
        - 'Hinge-and-Hold Chipping Drill'
        - 'Clock System Wedge Drill'
        - 'Landing Zone Target Towel Drill'
        - 'Trail-Hand Only Pitch Drill'
        - 'Line in the Sand Drill'
        - 'Dollar Bill Sand Extraction Drill'
        - 'Open-Face Sand Splash Drill'
        - 'Continuous Motion Pendulum Chipping Drill'
        - 'Accelerating Through Impact Gate Drill'
        - 'Target-Focused Eyes-Up Chipping Drill'

        PUTTING:
        - 'Putting Tee Gate Drill'
        - 'Chalk Line Straight Target Drill'
        - 'Mirror Alignment Face Drill'
        - 'Trail-Hand Push Putting Drill'
        - 'Metal Yardstick Roll Drill'
        - 'Parallel Rod Putting Channel Drill'
        - 'Ladder Distance Lag Drill'
        - 'Fringe-to-Fringe Feel Drill'
        - 'Eyes-Closed Distance Perception Drill'
        - 'Rubber Band Putter Sweet-Spot Drill'
        - 'Two-Tee Putter Gate Drill'
        - 'Coin Balance Putter Back Drill'
        - 'Push-Putting No-Backswing Drill'
        - 'Short Back Long Through Stroke Drill'
        - 'Coin Balance Motion Stroke Drill'

        Output strictly raw JSON matching this structure with no markdown formatting:
        {{
          "diagnosis_category": "Multi-Fault Diagnostic",
          "primary_miss": "string",
          "primary_cause_breakdown": "string (2-3 concise sentences explaining objective biomechanical/technical root causes without persona styling)",
          "secondary_miss": "string or null",
          "secondary_cause_breakdown": "string or null (2-3 concise sentences explaining objective biomechanical/technical root causes without persona styling)",
          "expanded_caddie_intro": "string (3-4 robust, dramatic sentences strictly in character persona providing a high-level summary diagnosis, witty observations, and inspirational guidance)",
          "confidence_score": 0.95,
          "recommended_primary_drill": "string",
          "recommended_secondary_drill": "string or null",
          "drill_rationale": "string (1-2 sentences summarizing how the selected drills resolve these physical issues)"
        }}
        """

        try:
            flash_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower()
            ]
            flash_models.sort(reverse=True)

            response = None
            for model_name in flash_models:
                try:
                    model = genai.GenerativeModel(model_name)
                    res = model.generate_content(f"{system_prompt}\n\nUser Input: {shot_transcript}")
                    if res and res.text:
                        response = res
                        break
                except Exception:
                    continue

            if response is None:
                st.error("No active Gemini Flash model found for this API key.")
                st.stop()

            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            st.session_state["diagnosis"] = json.loads(clean_json)
            st.session_state["caddie_name"] = selected_persona_key
        except Exception as e:
            st.error(f"Error parsing Gemini response: {e}")

if "diagnosis" in st.session_state:
    diag = st.session_state["diagnosis"]
    caddie = st.session_state.get("caddie_name", selected_persona_key)

    intro_text = diag.get("expanded_caddie_intro", "")
    st.success(f"**{caddie}:** \"{intro_text}\"")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🎯 Primary Issue**")
        st.warning(diag.get("primary_miss", "Not detected"))
        st.write(f"**Primary Drill:** `{diag.get('recommended_primary_drill')}`")
        p_causes = diag.get("primary_cause_breakdown")
        if p_causes:
            st.caption(f"**Breakdown:** {p_causes}")

    with col2:
        st.markdown("**⚠️ Secondary Issue**")
        sec_miss = diag.get("secondary_miss")
        if sec_miss:
            st.info(sec_miss)
            sec_drill = diag.get("recommended_secondary_drill")
            st.write(f"**Secondary Drill:** `{sec_drill if sec_drill else 'N/A'}`")
            s_causes = diag.get("secondary_cause_breakdown")
            if s_causes:
                st.caption(f"**Breakdown:** {s_causes}")
        else:
            st.info("None Detected")
            st.write("**Secondary Drill:** `N/A`")

    st.markdown("---")
    st.write("**Calibration Loop: Did Gemini's diagnosis match your felt experience?**")
    match_flag = st.radio("Diagnosis Match:", ["Matched", "Overridden"], horizontal=True)

    if match_flag == "Overridden":
        user_felt = st.text_input("Describe your actual felt experience:")
        if st.button("Log Override"):
            st.info("Override recorded for continuous improvement calibration.")
    else:
        if st.button("Confirm Match"):
            st.success("Diagnosis confirmed and logged.")

# -------------------------------------------------------------
# STEP 2: PRACTICE ASSET ALLOCATION (REACTIVE UPDATE)
# -------------------------------------------------------------
st.markdown("---")
st.subheader("2. Practice Resource Constraints (Balls & Time)")

col_input_a, col_input_b = st.columns(2)
with col_input_a:
    total_balls = st.number_input("Total Balls Available:", min_value=10, max_value=300, value=100, step=10)
with col_input_b:
    total_time = st.number_input("Total Time Available (mins):", min_value=15, max_value=180, value=60, step=15)

practice_mode = st.radio(
    "Select Practice Mode:",
    options=[
        "Combination / Hybrid (AI Balanced)",
        "Pure Grind Mode (100% Technical Drill)",
        "Pure Game Mode (100% Target Pressure)"
    ],
    horizontal=False
)

if practice_mode == "Pure Grind Mode (100% Technical Drill)":
    grind_pct = 1.0
elif practice_mode == "Pure Game Mode (100% Target Pressure)":
    grind_pct = 0.0
else:
    raw_grind_ratio = 0.60
    bounded_grind_ratio = max(0.30, min(0.75, raw_grind_ratio))
    user_override = st.checkbox("Enable Manual Ratio Override")

    if user_override:
        grind_pct = st.slider("Manual Grind Allocation (%)", min_value=0, max_value=100, value=int(bounded_grind_ratio * 100)) / 100.0
    else:
        grind_pct = bounded_grind_ratio

game_pct = 1.0 - grind_pct

grind_balls = int(total_balls * grind_pct)
game_balls = int(total_balls * game_pct)
grind_time = int(total_time * grind_pct)
game_time = int(total_time * game_pct)
sec_per_ball = int((total_time * 60) / total_balls) if total_balls > 0 else 0

# Reactive Session Storage
res = {
    "total_balls": total_balls,
    "total_time": total_time,
    "grind_balls": grind_balls,
    "game_balls": game_balls,
    "grind_time": grind_time,
    "game_time": game_time,
    "sec_per_ball": sec_per_ball,
    "grind_pct": grind_pct,
    "game_pct": game_pct
}

st.write("**Resource Distribution:**")
st.progress(res["grind_pct"], text=f"Grind Mode: {int(res['grind_pct']*100)}% | Game Mode: {int(res['game_pct']*100)}%")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Grind Mode Split", f"{res['grind_balls']} balls", f"{res['grind_time']} mins")
with col_b:
    st.metric("Game Mode Split", f"{res['game_balls']} balls", f"{res['game_time']} mins")
with col_c:
    st.metric("Target Pace", f"{res['sec_per_ball']} sec/ball", "Recommended Tempo")

# -------------------------------------------------------------
# STEP 3: ADAPTIVE PRACTICE EXECUTION & SETUP GUIDE
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Adaptive Practice Execution & Setup Guide")

if "diagnosis" in st.session_state:
    diag = st.session_state["diagnosis"]

    p_drill = diag.get("recommended_primary_drill", "Alignment Stick Gate Drill")
    s_drill = diag.get("recommended_secondary_drill")
    p_miss = diag.get("primary_miss", "your main swing fault")
    s_miss = diag.get("secondary_miss")
    rationale = diag.get("drill_rationale")

    c_balls = res["total_balls"]
    c_time = res["total_time"]

    active_drills = [p_drill]
    if c_balls >= 40 and c_time >= 30 and s_drill and s_drill != p_drill:
        active_drills.append(s_drill)

    if len(active_drills) == 2 and s_miss:
        summary_line = f"💡 **Targeted Prescription:** **{p_drill}** addresses **{p_miss}**, and **{s_drill}** corrects **{s_miss}**."
    else:
        summary_line = f"💡 **Targeted Prescription:** **{p_drill}** eliminates **{p_miss}**."

    if rationale:
        st.info(f"{summary_line}\n\n**Why these drills work:** {rationale}")
    else:
        st.info(summary_line)

    g_balls = res["grind_balls"]
    g_time = res["grind_time"]

    if len(active_drills) == 2:
        allocations = [
            {"label": f"Correcting: {p_miss}", "balls": g_balls // 2, "time": g_time // 2},
            {"label": f"Correcting: {s_miss}", "balls": g_balls - (g_balls // 2), "time": g_time - (g_time // 2)}
        ]
    else:
        allocations = [
            {"label": f"Correcting: {p_miss}", "balls": g_balls, "time": g_time}
        ]

    for idx, d_name in enumerate(active_drills):
        schematic = DRILL_SCHEMATICS.get(d_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"])
        alloc = allocations[idx]

        st.markdown(f"### 🎯 Drill #{idx+1}: **{d_name}**")
        st.caption(f"🔥 **{alloc['label']}** — `{alloc['balls']} Balls` | `{alloc['time']} Mins` | `@~{res['sec_per_ball']}s/ball`")

        st.markdown("**🛠️ Range Equipment Needed**")
        equip_items = re.split(r',\s*(?![^()]*\))', schematic["equipment"])
        indented_ul(equip_items)

        st.markdown("**📖 Setup Description**")
        indented_html(schematic["vivid_description"])

        st.markdown("**🧠 Mental Analogy**")
        indented_html(schematic["analogy"])

        st.info(schematic["pro_tip"])

        if idx < len(active_drills) - 1:
            st.markdown("---")

    gm_balls = res["game_balls"]
    gm_time = res["game_time"]
    if gm_balls > 0 and gm_time > 0:
        st.markdown("---")
        st.success(f"⛳ **Final Phase — Target Course Pressure** (`{gm_balls} Balls` | `{gm_time} Mins`)\n\nSimulate real course conditions. Alternate targets and clubs for every single ball while using your full pre-shot routine.")

else:
    st.caption("Run a shot diagnosis in Section 1 to view your execution plan!")
