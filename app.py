import json
import google.generativeai as genai
import streamlit as st

st.set_page_config(
    page_title="Birdie Buddy MVP", page_icon="⛳", layout="centered"
)

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
# DETAILED DRILL & VISUAL SCHEMATIC DATABASE
# -------------------------------------------------------------
DRILL_SCHEMATICS = {
    "Alignment Stick Gate Drill": {
        "equipment": "2 Alignment Sticks, 2 Tees, Target Flag",
        "setup_steps": [
            "Lay Stick #1 parallel to target line 1 foot outside the golf ball.",
            (
                "Plant Stick #2 vertically into turf 2 feet behind ball, angled"
                " 45° along outer backswing path."
            ),
            (
                "Push 2 Tees into turf 2 inches ahead of ball, just wider than"
                " clubhead width."
            ),
        ],
        "diagram_html": """
        <div style="background-color: #0f172a; padding: 16px; border-radius: 10px; border: 1px solid #334155; font-family: monospace; color: #f8fafc;">
            <div style="text-align: center; color: #38bdf8; font-weight: bold; margin-bottom: 10px;">⛳ RANGE VISUAL SCHEMATIC: ALIGNMENT STICK GATE</div>
            <pre style="color: #4ade80; font-size: 13px; line-height: 1.3; margin: 0; text-align: center;">
🎯 Target Line Flag ---------------------------------------------------->
         
               \  (Stick #2: Outer Path Barrier @ 45°)
                \
          [Tee 1] 🟢 Ball [Tee 2]   <-- Impact Gate (+1" Clubhead Width)
         =========================  <-- Stick #1: Target Line Guide
               👣 [Golfer Stance]
            </pre>
        </div>
        """,
        "pro_cue": (
            "Swing cleanly through the tee gate without touching either stick"
            " or clipping the outer barrier stick on takeaway."
        ),
    },
    "Pause at Top Drill": {
        "equipment": "1 Alignment Stick, Target Flag",
        "setup_steps": [
            "Lay 1 Alignment Stick across toe line for stance alignment.",
            "Take normal backswing to top position and hold for 2 full seconds.",
            "Audit clubface angle (parallel to lead forearm) before initiating downswing."
        ],
        "diagram_html": """
        <div style="background-color: #0f172a; padding: 16px; border-radius: 10px; border: 1px solid #334155; font-family: monospace; color: #f8fafc;">
            <div style="text-align: center; color: #38bdf8; font-weight: bold; margin-bottom: 10px;">⛳ RANGE VISUAL SCHEMATIC: PAUSE AT TOP DRILL</div>
            <pre style="color: #38bdf8; font-size: 13px; line-height: 1.3; margin: 0; text-align: center;">
                          [ TOP OF SWING ]
                        ⏸️ 2-Sec Audit Pause
                                |
                                v
 🎯 Target Line ----------> 🟢 Ball
                        ==================  <-- Feet Alignment Stick
                              👣 [Stance]
            </pre>
        </div>
        """,
        "pro_cue": "Feel body weight shift to lead side BEFORE hands begin downswing motion.",
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees",
        "setup_steps": [
            "Place ball in center.",
            "Press Tee #1 and Tee #2 into ground 0.5 inches inside and outside toe/heel.",
            "Press Tee #3 and Tee #4 into ground 3 inches ahead of ball to form exit corridor."
        ],
        "diagram_html": """
        <div style="background-color: #0f172a; padding: 16px; border-radius: 10px; border: 1px solid #334155; font-family: monospace; color: #f8fafc;">
            <div style="text-align: center; color: #38bdf8; font-weight: bold; margin-bottom: 10px;">⛳ RANGE VISUAL SCHEMATIC: TEE GATE CORRIDOR</div>
            <pre style="color: #facc15; font-size: 13px; line-height: 1.3; margin: 0; text-align: center;">
🎯 Target Flag ----> [Tee 3]   [Tee 4]   <-- Exit Corridor Gate
                          \     /
                           \   /
                      [Tee 1]🟢[Tee 2]   <-- Entry Gate at Ball Position
                           👣 [Stance]
            </pre>
        </div>
        """,
        "pro_cue": "Sweep ball cleanly without disturbing entry or exit tees.",
    }
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
    system_prompt = f"""
        {active_persona['system_instruction']}

        Analyze the user's input regarding a missed shot. Strictly evaluate errors against the 'Path/Face' domain (club path relative to target line, face angle relative to path). 
        Output strictly raw JSON matching this structure with no markdown formatting:
        {{
          "diagnosis_category": "Path/Face",
          "detected_miss": "string",
          "tom_shanks_response": "string (1-2 sentences max, matching your assigned movie character persona)",
          "confidence_score": 0.95,
          "recommended_grind_drill": "string (MUST select one of: 'Alignment Stick Gate Drill', 'Pause at Top Drill', 'Tee Gate Drill')"
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
elif practice_mode == "Pure Game Mode (100% Target Pressure)":
  grind_pct = 0.0
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
  else:
    grind_pct = bounded_grind_ratio

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
# STEP 3: ADAPTIVE PGA EXECUTION & VISUAL SETUP SCHEMATIC
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Adaptive Practice Execution & Visual Setup")

if "diagnosis" in st.session_state:
  diag = st.session_state["diagnosis"]
  drill_name = diag.get("recommended_grind_drill", "Alignment Stick Gate Drill")

  # Fetch schematic details or default
  schematic = DRILL_SCHEMATICS.get(
      drill_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"]
  )

  st.info(f"🎯 **Primary Technical Drill:** {drill_name}")

  # Display Visual HTML Diagram
  st.markdown(schematic["diagram_html"], unsafe_allow_html=True)

  # Display Setup & Equipment
  st.markdown(
      f"**Required Range Equipment:** {schematic['equipment']}"
  )
  st.write("**Step-by-Step Physical Setup:**")
  for step in schematic["setup_steps"]:
    st.write(f"* {step}")

  st.caption(f"💡 **PGA Tour Coaching Cue:** {schematic['pro_cue']}")

  st.markdown("---")

  # Dynamic Constraint Execution Protocol
  if total_balls < 40 or total_time < 30:
    st.warning("⚡ **Express Micro-Session Execution Plan**")
    st.markdown(f"""
        * **Block 1 Grind ({grind_balls} Balls | {grind_time} Mins):** Execute rapid-fire reps using *{drill_name}*. Focus strictly on impact feel.
        * **Block 2 Pressure ({game_balls} Balls | {game_time} Mins):** Single target gate challenge. Must hit {min(game_balls, 3)} consecutive fairways to complete session.
        """)
  elif total_balls > 110 or total_time > 75:
    st.success("🔥 **Master Progressive Calibration Session Plan**")
    p1_balls, p2_balls = grind_balls // 2, grind_balls - (grind_balls // 2)
    st.markdown(f"""
        * **Stage 1 Mechanical Exaggeration ({p1_balls} Balls | {grind_time // 2} Mins):** Deliberately over-correct your missed swing path using the visual setup above.
        * **Stage 2 Precision Tolerance ({p2_balls} Balls | {grind_time // 2} Mins):** Tighten gate width. Hold 3-second finish pose on every shot.
        * **Stage 3 Full Course Simulation ({game_balls} Balls | {game_time} Mins):** 9-hole range simulation. Full 45s pre-shot routine per ball.
        """)
  else:
    st.info("🎯 **Standard Dual-Block Plan**")
    st.markdown(f"""
        * **Block 1 Technical Grind ({grind_balls} Balls | {grind_time} Mins):** {grind_balls // 10} sets of 10 balls. Paced at ~{sec_per_ball}s per shot.
        * **Block 2 Game Simulation ({game_balls} Balls | {game_time} Mins):** Alternate targets and clubs on every single rep.
        """)
else:
  st.caption("Run a shot diagnosis above to generate your customized drill routine and setup schematics!")
