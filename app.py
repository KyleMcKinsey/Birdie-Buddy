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
        "equipment": "2 Alignment Rods, 2 Golf Tees, Target Alignment Flag",
        "image_url": "https://images.unsplash.com/photo-1587174486073-ae5e5cff23aa?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Imagine laying down a pristine set of parallel railroad tracks on"
            " the green grass pointing directly down your target line. Stick #1"
            " sits on the turf 1 foot outside the ball, acting as your visual"
            " track line. Stick #2 is stuck vertically into the turf 2 feet"
            " behind the ball, angled up at 45° like a slanted fence. If your"
            " backswing loop swings too far outside or 'over-the-top', your club"
            " shaft will immediately sound the alarm by tapping this stick."
            " Finally, two tees are pushed into the grass 2 inches ahead of your"
            " ball, leaving just enough clearance for your iron's sweet spot to"
            " glide through."
        ),
        "analogy": (
            "🚂 **The Railroad Track & Slanted Roof:** Think of your swing as a"
            " bullet train moving through a narrow glass tunnel. If you swing"
            " over-the-top, you shatter the glass on the upper slanted roof"
            " (Stick #2). You must stay beneath the roof and glide straight"
            " through the center of the tracks."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Keep 60% of your weight grounded in your"
            " lead heel during impact. Do not fight to hit the ball—focus purely"
            " on sweeping the turf between the two tee gates while keeping your"
            " eyes fixed on the front edge of the golf ball."
        ),
    },
    "Pause at Top Drill": {
        "equipment": "1 Alignment Rod, Target Line Marker",
        "image_url": "https://images.unsplash.com/photo-1592919505780-303950717480?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Picture coiled tension inside a grand pendulum clock. You coil your"
            " torso fully into your trail hip on the backswing, reaching the"
            " top of your arc. Instead of rushing down with your hands, you freeze"
            " completely in place for 2 full seconds. Your torso remains fully"
            " loaded, chest pointed away from the target, hands held high over"
            " your right shoulder. You take a brief breath to audit your wrist"
            " flatness, then initiate the downswing strictly by shifting your"
            " lead knee toward the target line."
        ),
        "analogy": (
            "🏹 **The Coiled Archer's Bow:** Pulling the bowstring back is your"
            " backswing. Holding the pause at the top is holding your aim"
            " steady before release. If you rush the drop, the arrow flies off"
            " course. The pause forces your lower body to fire first while the"
            " arms simply follow."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Count 'One-One-Thousand' silently at the"
            " top before starting down. Feel as though your lead hip slides 2"
            " inches toward the target while your chest remains pointed behind"
            " you."
        ),
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees",
        "image_url": "https://images.unsplash.com/photo-1593111774601-dfbce3206564?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Step up to the ball on the turf and press two tees flush into the"
            " ground just 1/4 inch beyond the toe and heel of your clubhead."
            " Then, move 3 inches down the target line and plant two more tees"
            " spaced exactly one ball-width apart to create a tight exit"
            " corridor. Your objective is surgical precision: strike the ball"
            " cleanly, pass through the front corridor, and avoid clipping any of"
            " the four surrounding tees."
        ),
        "analogy": (
            "🛩️ **Threading the Needle / Aircraft Runway:** Your clubhead is an"
            " airplane landing on a narrow runway. If your club path drifts in"
            " or out, you clip the runway guardrails (the tees). You must keep"
            " the wings level and flush through impact."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Soften your tension in both wrists to a 4"
            " out of 10. Let the weight of the clubhead drop through the gate organically"
            " rather than steering it with your hands."
        ),
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
    st.write(f"**Base Recommended Drill:** {diag['recommended_grind_drill']}")

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

# Confirmation Button to lock in constraint inputs
if st.button("✅ Confirm Selection & Generate Execution Plan", type="primary"):
  st.session_state["confirmed_resources"] = {
      "total_balls": total_balls,
      "total_time": total_time,
      "grind_balls": grind_balls,
      "game_balls": game_balls,
      "grind_time": grind_time,
      "game_time": game_time,
      "sec_per_ball": sec_per_ball,
      "grind_pct": grind_pct,
      "game_pct": game_pct,
  }
  st.success("Resource constraints locked in! Drill execution plan generated below.")

# Display confirmed metric preview if available
if "confirmed_resources" in st.session_state:
  res_data = st.session_state["confirmed_resources"]
  st.write("**Confirmed Resource Distribution:**")
  st.progress(
      res_data["grind_pct"],
      text=(
          f"Grind Mode: {int(res_data['grind_pct'] * 100)}% | Game Mode:"
          f" {int(res_data['game_pct'] * 100)}%"
      ),
  )

  col_a, col_b, col_c = st.columns(3)
  with col_a:
    st.metric(
        "Grind Mode Split",
        f"{res_data['grind_balls']} balls",
        f"{res_data['grind_time']} mins",
    )
  with col_b:
    st.metric(
        "Game Mode Split",
        f"{res_data['game_balls']} balls",
        f"{res_data['game_time']} mins",
    )
  with col_c:
    st.metric(
        "Target Pace",
        f"{res_data['sec_per_ball']} sec/ball",
        "Recommended Tempo",
    )

# -------------------------------------------------------------
# STEP 3: ADAPTIVE PRACTICE EXECUTION & MULTI-DRILL RESOLUTION
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Adaptive Practice Execution & Visual Setup Guide")

if "diagnosis" in st.session_state and "confirmed_resources" in st.session_state:
  diag = st.session_state["diagnosis"]
  res = st.session_state["confirmed_resources"]

  base_drill = diag.get("recommended_grind_drill", "Alignment Stick Gate Drill")
  c_balls = res["total_balls"]
  c_time = res["total_time"]

  # MULTI-DRILL RESOLUTION LOGIC based on constraint volume
  if c_balls < 40 or c_time < 30:
    active_drills = ["Tee Gate Drill"]
    session_tier = "⚡ Express Micro-Session (Single Drill)"
    adaptation_reason = (
        f"Confirmed constraints are focused ({c_balls} balls / {c_time} mins)."
        " Assigned a rapid-setup single drill for maximum efficiency."
    )
  elif c_balls > 110 or c_time > 75:
    # Extended range session: multi-drill combination!
    secondary_drill = (
        "Pause at Top Drill"
        if base_drill != "Pause at Top Drill"
        else "Alignment Stick Gate Drill"
    )
    active_drills = [base_drill, secondary_drill]
    session_tier = "🔥 Master Extended Multi-Drill Session"
    adaptation_reason = (
        f"Extended resources available ({c_balls} balls / {c_time} mins)."
        " Assigned a **2-Drill Circuit** combining primary swing path control"
        " with secondary tempo & transition calibration."
    )
  else:
    active_drills = [base_drill]
    session_tier = "🎯 Standard Dual-Block Session (Single Primary Drill)"
    adaptation_reason = (
        "Balanced resources. Executing standard AI-diagnosed primary drill."
    )

  st.info(f"**{session_tier}:** {adaptation_reason}")

  # Display all active resolved drills
  for idx, d_name in enumerate(active_drills, 1):
    schematic = DRILL_SCHEMATICS.get(
        d_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"]
    )

    st.markdown(f"### 🎯 Drill #{idx}: **{d_name}**")

    # Image Visual
    st.image(
        schematic["image_url"],
        caption=f"Visual Setup Blueprint — {d_name}",
        use_container_width=True,
    )

    # Equipment & Vivid Description
    st.markdown(f"**🛠️ Range Equipment Needed:** {schematic['equipment']}")
    st.markdown("#### 📖 Vivid Visual Setup Description")
    st.write(schematic["vivid_description"])

    st.markdown("#### 🧠 Mental Analogy")
    st.markdown(schematic["analogy"])

    st.markdown("#### 💡 PGA Tour Pro Tip")
    st.info(schematic["pro_tip"])

    if idx < len(active_drills):
      st.markdown("---")

  st.markdown("---")

  # Dynamic Constraint Execution Protocol using confirmed split values
  g_balls = res["grind_balls"]
  gm_balls = res["game_balls"]
  g_time = res["grind_time"]
  gm_time = res["game_time"]
  spb = res["sec_per_ball"]

  if c_balls < 40 or c_time < 30:
    st.warning("⚡ **Express Micro-Session Execution Plan**")
    st.markdown(f"""
        * **Block 1 Technical Grind ({g_balls} Balls | {g_time} Mins):** Execute rapid reps using *{active_drills[0]}*. Focus strictly on impact feel and clean path execution.
        * **Block 2 Target Pressure ({gm_balls} Balls | {gm_time} Mins):** Single target gate challenge. Must hit {min(gm_balls, 3)} consecutive fairways to complete session.
        """)
  elif c_balls > 110 or c_time > 75:
    st.success("🔥 **Master Multi-Drill Progressive Execution Plan**")
    d1_balls = g_balls // 2
    d2_balls = g_balls - d1_balls
    d1_time = g_time // 2
    d2_time = g_time - d1_time

    st.markdown(f"""
        * **Stage 1 Primary Mechanical Grind ({d1_balls} Balls | {d1_time} Mins):** Execute *{active_drills[0]}*. Focus on eliminating your missed swing path.
        * **Stage 2 Secondary Transition & Tempo ({d2_balls} Balls | {d2_time} Mins):** Transition to *{active_drills[1]}*. Hold a 3-second finish pose on every shot.
        * **Stage 3 Full Target Course Simulation ({gm_balls} Balls | {gm_time} Mins):** 9-hole simulated range round. Execute full 45s pre-shot routine per ball, alternating targets and clubs.
        """)
  else:
    st.info("🎯 **Standard Dual-Block Plan**")
    st.markdown(f"""
        * **Block 1 Technical Grind ({g_balls} Balls | {g_time} Mins):** {g_balls // 10 if g_balls >= 10 else 1} sets using *{active_drills[0]}*. Paced at ~{spb}s per shot.
        * **Block 2 Game Simulation ({gm_balls} Balls | {gm_time} Mins):** Alternate targets and clubs on every single rep.
        """)
elif "diagnosis" in st.session_state:
  st.warning("👈 Please click **'✅ Confirm Selection & Generate Execution Plan'** in Section 2 to generate your drill execution setup.")
else:
  st.caption("Run a shot diagnosis in Section 1 and confirm your resources in Section 2 to generate your drill routine!")
