import streamlit as st
import google.generativeai as genai
import json

st.set_page_config(page_title="Birdie Buddy MVP", page_icon="⛳", layout="centered")

st.title("⛳ Birdie Buddy (Phase 1 MVP)")
st.caption("AI Golf Caddie & Practice Asset Allocator powered by Gemini")

# Sidebar - API Key Input
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

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

if st.button("Analyze Shot with Tom Shanks"):
    if shot_transcript:
        system_prompt = """
        You are 'Tom Shanks,' a lightheartedly sarcastic yet highly strategic AI golf caddie. 
        Analyze the user's input regarding a missed shot. For Phase 1, strictly evaluate errors against the 'Path/Face' domain (club path relative to target line, face angle relative to path). 
        Output strictly raw JSON matching this structure with no markdown formatting:
        {
          "diagnosis_category": "Path/Face",
          "detected_miss": "string",
          "tom_shanks_response": "string (1-2 sentences max, comedic persona)",
          "confidence_score": 0.95,
          "recommended_grind_drill": "string"
        }
        """
        
        try:
            # Query active Flash models and sort newest first
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
        except Exception as e:
            st.error(f"Error parsing Gemini response: {e}")

if 'diagnosis' in st.session_state:
    diag = st.session_state['diagnosis']
    
    st.success(f"**Tom Shanks:** \"{diag['tom_shanks_response']}\"")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Category", diag['diagnosis_category'])
        st.write(f"**Detected Miss:** {diag['detected_miss']}")
    with col2:
        st.metric("Confidence Score", f"{int(diag['confidence_score'] * 100)}%")
        st.write(f"**Recommended Drill:** {diag['recommended_grind_drill']}")

    # Discrepancy & Calibration Loop UI
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

# Default Allocation Ratio
raw_grind_ratio = 0.60

# Practice Trust Bounds (Hardcoded Guardrails: 30% min, 75% max for Grind Mode)
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

# Visual Asset Allocation Progress Bar
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
    
    # Calculate Sets based on Grind Balls
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
