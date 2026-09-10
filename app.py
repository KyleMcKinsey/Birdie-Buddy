import streamlit as st
import google.generativeai as genai
import json

st.set_page_config(page_title="Birdie Buddy MVP", page_icon="⛳", layout="centered")

st.title("⛳ Birdie Buddy (Phase 1 MVP)")
st.caption("AI Golf Caddie & Practice Asset Allocator powered by Gemini")

# Sidebar - API Key Input & Settings
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

# -------------------------------------------------------------
# PERSONA DATABASE (System Prompts & Talking Styles)
# -------------------------------------------------------------
PERSONA_DATABASE = {
    "Tom Shanks": {
        "title": "Tom Shanks (Sarcastic Strategist)",
        "description": "Brutally honest, witty, and sharp caddie who calls out bad choices with dry humor.",
        "system_instruction": """
        You are 'Tom Shanks,' a lightheartedly sarcastic yet highly strategic AI golf caddie.
        Tone: Dry, witty, slightly condescending but fundamentally helpful.
        Sample Catchphrases: 'Fore right into the timber sale!', 'Bold choice aiming for the parking lot.'
        Analyze the shot error against the 'Path/Face' domain.
        """
    },
    "Bernie Hacks": {
        "title": "Bernie Hacks (Weekend Duffer)",
        "description": "Over-enthusiastic high-handicapper who blames equipment, luck, and wind instead of swing mechanics.",
        "system_instruction": """
        You are 'Bernie Hacks,' an over-enthusiastic weekend golfer who uses golf jargon slightly wrong and always blames external factors (the wind, dirty ball, cheap tees, bad luck) before acknowledging swing errors.
        Tone: Hype-man, chaotic, wildly optimistic, funny, uses heavy slang like 'pure strain', 'butter cut', 'nuked it'.
        Sample Catchphrases: 'That was definitely a gust of wind at 100 feet!', 'Time to buy a new $600 driver!'
        Analyze the shot error against the 'Path/Face' domain while keeping this comedic persona.
        """
    },
    "Coach Grace": {
        "title": "Coach Grace (Mindful Mentor)",
        "description": "Calm, encouraging, and focused on swing tempo, breathwork, and positive mental re-framing.",
        "system_instruction": """
        You are 'Coach Grace,' a serene and supportive PGA master instructor focusing on mental clarity, swing tempo, and constructive encouragement.
        Tone: Empathetic, balanced, warm, professional, encouraging.
        Sample Catchphrases: 'Breathe through the release.', 'Every missed shot is just data for growth.'
        Analyze the shot error against the 'Path/Face' domain while offering calm, positive encouragement.
        """
    }
}

selected_persona_key = st.sidebar.selectbox(
    "Choose Your Caddie Persona:",
    options=list(PERSONA_DATABASE.keys())
)

active_persona = PERSONA_DATABASE[selected_persona_key]
st.sidebar.info(f"**{active_persona['title']}**\n\n{active_persona['description']}")

if not api_key:
    st.warning("Please paste your Google Gemini API Key in the sidebar to begin.")
    st.stop()

genai.configure(api_key=api_key)

# -------------------------------------------------------------
# STEP 1: PATH/FACE DIAGNOSTIC SPIKE
# -------------------------------------------------------------
st.subheader("1. Shot Diagnostic (Path/Face Domain)")

shot_transcript = st.text_area(
    "Describe your missed shot:", 
    placeholder="e.g., I swung hard out to right field and the ball sliced way off target..."
)

if st.button(f"Analyze Shot with {selected_persona_key}"):
    if shot_transcript:
        system_prompt = f"""
        {active_persona['system_instruction']}

        Analyze the user's input regarding a missed shot. Strictly evaluate errors against the 'Path/Face' domain (club path relative to target line, face angle relative to path). 
        Output strictly raw JSON matching this structure with no markdown formatting:
        {{
          "diagnosis_category": "Path/Face",
          "detected_miss": "string",
          "tom_shanks_response": "string (1-2 sentences max, matching your assigned persona style)",
          "confidence_score": 0.95,
          "recommended_grind_drill": "string"
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
            st.session_state['diagnosis'] = json.loads(clean_json)
            st.session_state['caddie_name'] = selected_persona_key
        except Exception as e:
            st.error(f"Error parsing Gemini response: {e}")

if 'diagnosis' in st.session_state:
    diag = st.session_state['diagnosis']
    caddie = st.session_state.get('caddie_name', selected_persona_key)
    
    st.success(f"**{caddie}:** \"{diag['tom_shanks_response']}\"")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Category", diag['diagnosis_category'])
        st.write(f"**Detected Miss:** {diag['detected_miss']}")
    with col2:
        st.metric("Confidence Score", f"{int(diag['confidence_score'] * 100)}%")
        st.write(f"**Recommended Drill:** {diag['recommended_grind_drill']}")

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
# STEP 2: PRACTICE ASSET ALLOCATION & TRUST BOUNDS
# -------------------------------------------------------------
st.markdown("---")
st.subheader("2. Practice Asset Allocation & Trust Bounds")

total_balls = st.number_input("Total Practice Balls Available:", min_value=10, max_value=300, value=100, step=10)

raw_grind_ratio = 0.60
bounded_grind_ratio = max(0.30, min(0.75, raw_grind_ratio))

user_override = st.checkbox("Enable Manual Override")

if user_override:
    grind_pct = st.slider("Manual Grind Allocation (%)", min_value=0, max_value=100, value=int(bounded_grind_ratio * 100)) / 100.0
    st.caption("Manual override active. Sum locked to 100%.")
else:
    grind_pct = bounded_grind_ratio
    st.info(f"AI Default Grind Allocation: {int(grind_pct * 100)}% (Enforced within 30%–75% guardrails)")

game_pct = 1.0 - grind_pct

grind_balls = int(total_balls * grind_pct)
game_balls = int(total_balls * game_pct)

st.write("**Asset Distribution:**")
st.progress(grind_pct, text=f"Grind Mode: {int(grind_pct * 100)}% | Game Mode: {int(game_pct * 100)}%")

col_a, col_b = st.columns(2)
with col_a:
    st.metric("Grind Mode Balls", f"{grind_balls} balls", f"{int(grind_pct * 100)}%")
with col_b:
    st.metric("Game Mode Balls", f"{game_balls} balls", f"{int(game_pct * 100)}%")

# -------------------------------------------------------------
# STEP 3: ACTIONABLE PRACTICE ROUTINE CARD
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Actionable Practice Execution Plan")

if 'diagnosis' in st.session_state:
    diag = st.session_state['diagnosis']
    drill_name = diag.get('recommended_grind_drill', 'Standard Alignment Drill')
    
    st.info(f"🎯 **Target Drill:** {drill_name}")
    
    reps_per_set = 10
    total_sets = max(1, grind_balls // reps_per_set)
    
    st.markdown(f"""
    **Block 1: Technical Grind ({grind_balls} Balls)**
    * **Structure:** {total_sets} sets of {reps_per_set} balls using *{drill_name}*.
    * **Focus:** Execute 3-second freeze at finish position on every rep.
    
    **Block 2: Target Pressure Game ({game_balls} Balls)**
    * **Structure:** Single-ball target switching (Fairway simulation).
    * **Focus:** Full pre-shot routine; switch target flag after every single ball.
    """)
else:
    st.caption("Run a shot diagnosis above to generate your customized drill routine!")
