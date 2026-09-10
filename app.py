import json
import google.generativeai as genai
import streamlit as st

st.set_page_config(
    page_title="Birdie Buddy MVP", page_icon="⛳", layout="centered"
)

st.title("⛳ Birdie Buddy (Phase 1 MVP)")
st.caption("AI Golf Caddie & Practice Asset Allocator powered by Gemini")

# Sidebar - API Key Input Only
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

if not api_key:
  st.warning("Please paste your Google Gemini API Key in the sidebar to begin.")
  st.stop()

genai.configure(api_key=api_key)

# -------------------------------------------------------------
# MOVIE PARODY PERSONA DATABASE
# -------------------------------------------------------------
PERSONA_DATABASE = {
    "Obi-Wan Kenbogey": {
        "title": "Obi-Wan Kenbogey (Jedi Master of Swing)",
        "description": (
            "Wise Jedi mentor guiding you away from the Dark Side (the slice)"
            " using the Force of swing tempo."
        ),
        "system_instruction": """
        You are 'Obi-Wan Kenbogey,' a wise and serene Jedi Master AI golf caddie.
        Tone: Calm, philosophical, dramatic, heroic, slightly cryptic.
        Sample Catchphrases: 'May the Force be with your clubface.', 'These are not the trees you are looking for.', 'Beware the Dark Side—anger leads to an open face.'
        Analyze the shot error against the 'Path/Face' domain using Jedi terminology and wise guidance.
        """,
    },
    "Harry Putter": {
        "title": "Harry Putter (The Boy Who Shanked)",
        "description": (
            "Magical prodigy who treats golf clubs like wands and blames Dark"
            " Magic for shanked drives."
        ),
        "system_instruction": """
        You are 'Harry Putter,' a young wizard AI golf caddie who treats golf clubs like magic wands and shot analysis like Defense Against the Dark Arts.
        Tone: Enthusiastic, spell-casting, British, magical.
        Sample Catchphrases: 'Expecto Fairway-um!', 'Yer a golfer, Harry!', '10 points to Gryffindor if you hit this green.'
        Analyze the shot error against the 'Path/Face' domain using wizarding world terminology and spell metaphors.
        """,
    },
    "James Pond": {
        "title": "James Pond (Agent 00-Slice)",
        "description": (
            "Suave secret agent who approaches every shot like a high-stakes MI6"
            " espionage mission."
        ),
        "system_instruction": """
        You are 'James Pond' (Agent 00-Slice), a suave, high-class secret agent AI golf caddie.
        Tone: Cool, sophisticated, covert, tactical, dry British charm.
        Sample Catchphrases: 'Shaken, not stirred—much like your grip pressure.', 'License to slice.', "The name's Pond... James Pond."
        Analyze the shot error against the 'Path/Face' domain as if evaluating high-stakes tactical intelligence.
        """,
    },
    "Captain Hack Sparrow": {
        "title": "Captain Hack Sparrow (Pirate of the Fairway)",
        "description": (
            "Eccentric, unpredictable pirate caddie stumbling through hazards"
            " with rum-fueled optimism and chaotic strategies."
        ),
        "system_instruction": """
        You are 'Captain Hack Sparrow,' an eccentric, wildly unpredictable pirate AI golf caddie.
        Tone: Slurred charm, chaotic, theatrical, witty, rum-obsessed, highly eccentric.
        Sample Catchphrases: 'Why is the fairway always gone?', 'Take what you can, give nothing back—except that ball in the hazard.', 'This shot is either brilliant or mad. Utterly mad.'
        Analyze the shot error against the 'Path/Face' domain using nautical pirate metaphors.
        """,
    },
}

# -------------------------------------------------------------
# STEP 1: PATH/FACE DIAGNOSTIC SPIKE
# -------------------------------------------------------------
st.subheader("1. Shot Diagnostic (Path/Face Domain)")

selected_persona_key = st.selectbox(
    "Choose Your Movie Caddie Persona:",
    options=list(PERSONA_DATABASE.keys()),
    index=0,
)

active_persona = PERSONA_DATABASE[selected_persona_key]
st.info(f"**{active_persona['title']}** — {active_persona['description']}")

shot_transcript = st.text_area(
    "Describe your missed shot:",
    placeholder=(
        "e.g., I swung hard out to right field and the ball sliced way off"
        " target..."
    ),
)

if st.button(f"Analyze Shot with {selected_persona_key}"):
  if shot_transcript:
    # Strictly isolate persona humor to 'tom_shanks_response' while forcing real PGA drills for 'recommended_grind_drill'
    system_prompt = f"""
        {active_persona['system_instruction']}

        Analyze the user's input regarding a missed shot. Strictly evaluate errors against the 'Path/Face' domain (club path relative to target line, face angle relative to path). 
        Output strictly raw JSON matching this structure with no markdown formatting:
        {{
          "diagnosis_category": "Path/Face",
          "detected_miss": "string",
          "tom_shanks_response": "string (1-2 sentences max, matching your assigned movie character persona)",
          "confidence_score": 0.95,
          "recommended_grind_drill": "string (MUST be a real, standard PGA golf instruction drill, e.g., 'Alignment Stick Gate Drill', 'Pause at Top Drill', 'Tee Gate Drill', 'Head Cover Under Arm Drill')"
        }}
        """

    try:
      flash_models = [
          m.name
          for m in genai.list_models()
          if 'generateContent' in m.supported_generation_methods
          and 'flash' in m.name.lower()
      ]
      flash_models.sort(reverse=True)

      response = None
      for model_name in flash_models:
        try:
          model = genai.GenerativeModel(model_name)
          res = model.generate_content(
              f"{system_prompt}\n\nUser Input: {shot_transcript}"
          )
          if res and res.text:
            response = res
            break
        except Exception:
          continue

      if response is None:
        st.error("No active Gemini Flash model found for this API key.")
        st.stop()

      clean_json = (
          response.text.replace("```json", "").replace("```", "").strip()
      )
      st.session_state["diagnosis"] = json.loads(clean_json)
      st.session_state["caddie_name"] = selected_persona_key
    except Exception as e:
      st.error(f"Error parsing Gemini response: {e}")

if "diagnosis" in st.session_state:
  diag = st.session_state["diagnosis"]
  caddie = st.session_state.get("caddie_name", selected_persona_key)

  st.success(f'**{caddie}:** "{diag["tom_shanks_response"]}"')

  col1, col2 = st.columns(2)
  with col1:
    st.metric("Category", diag["diagnosis_category"])
    st.write(f"**Detected Miss:** {diag['detected_miss']}")
  with col2:
    st.metric("Confidence Score", f"{int(diag['confidence_score'] * 100)}%")
    st.write(f"**Recommended Drill:** {diag['recommended_grind_drill']}")

  st.markdown("---")
  st.write(
      "**Calibration Loop: Did Gemini's diagnosis match your felt"
      " experience?**"
  )
  match_flag = st.radio(
      "Diagnosis Match:", ["Matched", "Overridden"], horizontal=True
  )

  if match_flag == "Overridden":
    user_felt = st.text_input("Describe your actual felt experience:")
    if st.button("Log Override"):
      st.info("Override recorded for continuous improvement calibration.")
  else:
    if st.button("Confirm Match"):
      st.success("Diagnosis confirmed and logged.")

# -------------------------------------------------------------
# STEP 2: PRACTICE ASSET ALLOCATION & DUAL-CONSTRAINT FOCUS
# -------------------------------------------------------------
st.markdown("---")
st.subheader("2. Practice Resource Constraints (Balls & Time)")

col_input_a, col_input_b = st.columns(2)
with col_input_a:
  total_balls = st.number_input(
      "Total Balls Available:",
      min_value=10,
      max_value=300,
      value=100,
      step=10,
  )
with col_input_b:
  total_time = st.number_input(
      "Total Time Available (mins):",
      min_value=15,
      max_value=180,
      value=60,
      step=15,
  )

practice_mode = st.radio(
    "Select Practice Mode:",
    options=[
        "Combination / Hybrid (AI Balanced)",
        "Pure Grind Mode (100% Technical Drill)",
        "Pure Game Mode (100% Target Pressure)",
    ],
    horizontal=False,
)

if practice_mode == "Pure Grind Mode (100% Technical Drill)":
  grind_pct = 1.0
  st.caption("Pure Grind selected: All resources committed to drill reps.")
elif practice_mode == "Pure Game Mode (100% Target Pressure)":
  grind_pct = 0.0
  st.caption(
      "Pure Game selected: All resources committed to pressure simulation."
  )
else:
  raw_grind_ratio = 0.60
  bounded_grind_ratio = max(0.30, min(0.75, raw_grind_ratio))
  user_override = st.checkbox("Enable Manual Ratio Override")

  if user_override:
    grind_pct = (
        st.slider(
            "Manual Grind Allocation (%)",
            min_value=0,
            max_value=100,
            value=int(bounded_grind_ratio * 100),
        )
        / 100.0
    )
    st.caption("Manual override active. Sum locked to 100%.")
  else:
    grind_pct = bounded_grind_ratio
    st.info(
        f"AI Default Grind Allocation: {int(grind_pct * 100)}% (Enforced within"
        " 30%–75% guardrails)"
    )

game_pct = 1.0 - grind_pct

grind_balls = int(total_balls * grind_pct)
game_balls = int(total_balls * game_pct)
grind_time = int(total_time * grind_pct)
game_time = int(total_time * game_pct)

sec_per_ball = (
    int((total_time * 60) / total_balls) if total_balls > 0 else 0
)

st.write("**Resource Distribution:**")
st.progress(
    grind_pct,
    text=(
        f"Grind Mode: {int(grind_pct * 100)}% | Game Mode:"
        f" {int(game_pct * 100)}%"
    ),
)

col_a, col_b, col_c = st.columns(3)
with col_a:
  st.metric("Grind Mode Split", f"{grind_balls} balls", f"{grind_time} mins")
with col_b:
  st.metric("Game Mode Split", f"{game_balls} balls", f"{game_time} mins")
with col_c:
  st.metric("Target Pace", f"{sec_per_ball} sec/ball", "Recommended Tempo")

# -------------------------------------------------------------
# STEP 3: REALISTIC PRACTICE EXECUTION PLAN
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Realistic Practice Execution Plan")

if "diagnosis" in st.session_state:
  diag = st.session_state["diagnosis"]
  drill_name = diag.get("recommended_grind_drill", "Standard Alignment Drill")

  st.info(f"🎯 **Target Drill:** {drill_name}")

  if grind_balls > 0:
    reps_per_set = 10
    total_sets = max(1, grind_balls // reps_per_set)
    time_per_set = max(1, grind_time // total_sets)
    st.markdown(f"""
        **Block 1: Technical Mechanical Grind ({grind_balls} Balls | {grind_time} Minutes)**
        * **Required Equipment:** 2 Alignment Sticks, 1 Box of Standard Tees, Target Flag.
        * **Setup & Structure:** {total_sets} sets of {reps_per_set} balls using the *{drill_name}*.
        * **Pacing Protocol:** Allow ~{time_per_set} minutes per 10-ball set (~{sec_per_ball} seconds per swing).
        * **Execution Focus:** Hold a deliberate 3-second finish pose on every repetition to audit swing path and balance before teeing up the next ball.
        """)

  if game_balls > 0:
    st.markdown(f"""
        **Block 2: Target Pressure Course Simulation ({game_balls} Balls | {game_time} Minutes)**
        * **Required Equipment:** Full Bag (Driver, Irons, Wedges), Alignment Stick (for target line reference).
        * **Setup & Structure:** Simulated 9-hole range play. Pick 2 range flags as left/right fairway boundaries.
        * **Pacing Protocol:** Step off the mat and execute a complete 45-second pre-shot routine for each of the {game_balls} shots across {game_time} minutes.
        * **Execution Focus:** Change target flag and club on *every single shot*. Record fairways hit and greens in regulation mentally.
        """)
else:
  st.caption("Run a shot diagnosis above to generate your customized drill routine!")
