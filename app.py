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
        "description": "Wise Jedi mentor guiding you away from the Dark Side (the slice) using the Force of swing tempo.",
        "system_instruction": """
        You are 'Obi-Wan Kenbogey,' a wise and serene Jedi Master AI golf caddie.
        Tone: Calm, philosophical, dramatic, heroic, slightly cryptic.
        Sample Catchphrases: 'May the Force be with your clubface.', 'These are not the trees you are looking for.', 'Beware the Dark Side—anger leads to an open face.'
        Analyze shot errors using Jedi terminology and wise guidance.
        """
    },
    "Harry Putter": {
        "title": "Harry Putter (The Boy Who Shanked)",
        "description": "Magical prodigy who treats golf clubs like wands and blames Dark Magic for shanked drives.",
        "system_instruction": """
        You are 'Harry Putter,' a young wizard AI golf caddie who treats golf clubs like magic wands and shot analysis like Defense Against the Dark Arts.
        Tone: Enthusiastic, spell-casting, British, magical.
        Sample Catchphrases: 'Expecto Fairway-um!', 'Yer a golfer, Harry!', '10 points to Gryffindor if you hit this green.'
        Analyze shot errors using wizarding world terminology and spell metaphors.
        """
    },
    "James Pond": {
        "title": "James Pond (Agent 00-Slice)",
        "description": "Suave secret agent who approaches every shot like a high-stakes MI6 espionage mission.",
        "system_instruction": """
        You are 'James Pond' (Agent 00-Slice), a suave, high-class secret agent AI golf caddie.
        Tone: Cool, sophisticated, covert, tactical, dry British charm.
        Sample Catchphrases: 'Shaken, not stirred—much like your grip pressure.', 'License to slice.', "The name's Pond... James Pond."
        Analyze shot errors as if evaluating high-stakes tactical intelligence.
        """
    },
    "Captain Hack Sparrow": {
        "title": "Captain Hack Sparrow (Pirate of the Fairway)",
        "description": "Eccentric, unpredictable pirate caddie stumbling through hazards with rum-fueled optimism and chaotic strategies.",
        "system_instruction": """
        You are 'Captain Hack Sparrow,' an eccentric, wildly unpredictable pirate AI golf caddie.
        Tone: Slurred charm, chaotic, theatrical, witty, rum-obsessed, highly eccentric.
        Sample Catchphrases: 'Why is the fairway always gone?', 'Take what you can, give nothing back—except that ball in the hazard.', 'This shot is either brilliant or mad. Utterly mad.'
        Analyze shot errors using nautical pirate metaphors.
        """
    }
}

# -------------------------------------------------------------
# EXPANDED PGA TOUR KNOWLEDGE BASE & SCHEMATICS (10 DRILLS)
# -------------------------------------------------------------
DRILL_SCHEMATICS = {
    "Alignment Stick Gate Drill": {
        "equipment": "2 Alignment Rods, 2 Golf Tees",
        "image_url": "https://images.unsplash.com/photo-1587174486073-ae5e5cff23aa?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Lay down parallel alignment rods along your target line. Stick a second rod into the turf 2 feet behind the ball at a 45° angle along your target path to force an inside-out delivery.",
        "analogy": "🚂 **Railroad Track & Slanted Roof:** Swing inside the tunnel without clipping the slanted roof stick on the way down.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Keep 60% of your weight grounded in your lead heel through impact to clear hips."
    },
    "Pause at Top Drill": {
        "equipment": "1 Alignment Rod",
        "image_url": "https://images.unsplash.com/photo-1592919505780-303950717480?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Take a full backswing and pause for a complete 2-second count at the top before starting your downswing. Feel your lower body initiate the downswing transition.",
        "analogy": "🏹 **Coiled Archer's Bow:** Holding the pause stabilizes your aim before smoothly releasing the arrow.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Count 'One-One-Thousand' silently at the top before starting down with your hips."
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees",
        "image_url": "https://images.unsplash.com/photo-1593111774601-dfbce3206564?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Plant two tees just outside the toe and heel of your clubhead at address, creating a narrow gate that forces center-face contact on every swing.",
        "analogy": "🛩️ **Narrow Runway:** Swing clean through the gate without clipping the side guardrails.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Soften wrist grip pressure to 4/10 to let the clubhead release naturally through the gate."
    },
    "Towel Under Armpits Drill": {
        "equipment": "1 Microfiber Golf Towel",
        "image_url": "https://images.unsplash.com/photo-1535131749006-b7f58c99034b?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Tuck a single golf towel across your chest under both armpits. Take smooth half-swings without dropping the towel to maintain body-arm connectivity.",
        "analogy": "📦 **Solid Core Cylinder:** Your arms and torso turn as one unified engine rather than swinging independently.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Rotate your sternum through the ball rather than pulling with your arms."
    },
    "Coin Strike Low-Point Drill": {
        "equipment": "1 Coin or Ball Marker",
        "image_url": "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Place a coin 2 inches ahead of your golf ball. Focus entirely on clipping the coin off the turf to shift your swing low-point forward.",
        "analogy": "🔪 **Compressing vs. Scooping:** Drive the clubhead through the turf forward instead of scooping up.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Ensure your chest buttons are directly over or slightly ahead of the coin at impact."
    },
    "Split-Hands Release Drill": {
        "equipment": "Mid-Iron (7-Iron)",
        "image_url": "https://images.unsplash.com/photo-1592919505780-303950717480?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Separate your trail hand 3 inches down the grip like holding a hockey stick. Take half-swings to feel the lead forearm roll over naturally.",
        "analogy": "🏒 **Hockey Slap Shot:** Forces proper wrist crossover to stop leaving the face open.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Feel the toe of the club point straight to the sky on the extension follow-through."
    },
    "Feet-Together Balance Drill": {
        "equipment": "Any Short/Mid-Iron",
        "image_url": "https://images.unsplash.com/photo-1587174486073-ae5e5cff23aa?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Stand with your feet touching heel-to-toe. Make smooth 75% tempo swings while maintaining total balance without swaying or tipping.",
        "analogy": "🌳 **Deep Rooted Tree:** Rotates around a fixed central axis without lateral sliding.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Keep your weight centered over the mid-foot throughout the backswing and finish."
    },
    "Wall-Head Posture Drill": {
        "equipment": "Wall or Alignment Rod behind hips",
        "image_url": "https://images.unsplash.com/photo-1592919505780-303950717480?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Set up with your forehead gently touching a wall or soft pad. Practice slow swings maintaining head contact to eliminate early extension.",
        "analogy": "🎯 **Fixed Pivot Pin:** Prevents your hips from thrusting forward toward the ball.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Keep your trail hip pressed back during the initial downswing transition."
    },
    "Impact Bag Compression Drill": {
        "equipment": "Impact Bag or Heavy Towel Bundle",
        "image_url": "https://images.unsplash.com/photo-1593111774601-dfbce3206564?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Swing half-speed into an impact bag, stopping at impact to feel shaft lean forward and hands leading the clubhead.",
        "analogy": "🔨 **Driving a Nail:** Delivers maximum energy transfer with hands ahead of the clubhead.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Firm up your lead wrist at impact so it forms a flat line with your forearm."
    },
    "Two-Step Pump Lag Drill": {
        "equipment": "Mid-Iron (6-Iron or 7-Iron)",
        "image_url": "https://images.unsplash.com/photo-1535131749006-b7f58c99034b?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": "Take a backswing, pump the downswing halfway down twice holding wrist angle, then sweep through on the third stroke.",
        "analogy": "🎣 **Whip Crack:** Preserves wrist angle until the absolute last millisecond before impact.",
        "pro_tip": "🏆 **PGA Tour Pro Tip:** Let your hips lead the pull down while hands stay soft and passive."
    }
}

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
    "Describe your missed shot(s) in detail:",
    placeholder="e.g., I swung hard out to right field and sliced it, plus I hit it thin and missed the sweet spot..."
)

if st.button(f"Analyze Shot with {selected_persona_key}"):
    if shot_transcript:
        system_prompt = f"""
        {active_persona['system_instruction']}

        Analyze the user's input regarding their missed shot. Identify up to TWO swing mechanics issues:
        1. Primary Miss / Fault (Required)
        2. Secondary Miss / Fault (Optional, set to null if only one clear fault exists)

        Map both faults to the most effective drills from this EXACT list:
        - 'Alignment Stick Gate Drill' (Best for: Over-the-top, outside-in path, slicing)
        - 'Pause at Top Drill' (Best for: Rushing downswing, poor sequencing, casting)
        - 'Tee Gate Drill' (Best for: Heel/Toe off-center impact, unstable clubface)
        - 'Towel Under Armpits Drill' (Best for: Flying elbow, chicken-winging, loss of body connection)
        - 'Coin Strike Low-Point Drill' (Best for: Fat shots, thin shots, scooping/flipping at ball)
        - 'Split-Hands Release Drill' (Best for: Open clubface, hanging back, push-slice)
        - 'Feet-Together Balance Drill' (Best for: Swaying, lateral sliding, loss of balance)
        - 'Wall-Head Posture Drill' (Best for: Early extension, posture loss, standing up at impact)
        - 'Impact Bag Compression Drill' (Best for: Flipping wrists, weak shaft lean, loss of distance)
        - 'Two-Step Pump Lag Drill' (Best for: Casting early, losing wrist lag, casting off top)

        Output strictly raw JSON matching this structure with no markdown formatting:
        {{
          "diagnosis_category": "Multi-Fault Path/Face",
          "primary_miss": "string",
          "secondary_miss": "string or null",
          "tom_shanks_response": "string (1-2 sentences max, matching your character persona)",
          "confidence_score": 0.95,
          "recommended_primary_drill": "string",
          "recommended_secondary_drill": "string or null"
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

    st.success(f"**{caddie}:** \"{diag['tom_shanks_response']}\"")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🎯 Primary Issue**")
        st.warning(diag.get("primary_miss", "Not detected"))
        st.write(f"**Primary Drill:** `{diag.get('recommended_primary_drill')}`")
    with col2:
        st.markdown("**⚠️ Secondary Issue**")
        sec_miss = diag.get("secondary_miss")
        if sec_miss:
            st.info(sec_miss)
        else:
            st.info("None Detected")
        sec_drill = diag.get("recommended_secondary_drill")
        st.write(f"**Secondary Drill:** `{sec_drill if sec_drill else 'N/A'}`")

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
# STEP 2: PRACTICE ASSET ALLOCATION & CONSTRAINTS
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
        "game_pct": game_pct
    }
    st.success("Resource constraints locked in! Drill execution plan generated below.")

if "confirmed_resources" in st.session_state:
    res_data = st.session_state["confirmed_resources"]
    st.write("**Confirmed Resource Distribution:**")
    st.progress(res_data["grind_pct"], text=f"Grind Mode: {int(res_data['grind_pct']*100)}% | Game Mode: {int(res_data['game_pct']*100)}%")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Grind Mode Split", f"{res_data['grind_balls']} balls", f"{res_data['grind_time']} mins")
    with col_b:
        st.metric("Game Mode Split", f"{res_data['game_balls']} balls", f"{res_data['game_time']} mins")
    with col_c:
        st.metric("Target Pace", f"{res_data['sec_per_ball']} sec/ball", "Recommended Tempo")

# -------------------------------------------------------------
# STEP 3: ADAPTIVE PRACTICE EXECUTION & MULTI-DRILL RESOLUTION
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Adaptive Practice Execution & Visual Setup Guide")

if "diagnosis" in st.session_state and "confirmed_resources" in st.session_state:
    diag = st.session_state["diagnosis"]
    res = st.session_state["confirmed_resources"]

    p_drill = diag.get("recommended_primary_drill", "Alignment Stick Gate Drill")
    s_drill = diag.get("recommended_secondary_drill")

    c_balls = res["total_balls"]
    c_time = res["total_time"]

    # MULTI-DRILL RESOLUTION LOGIC
    active_drills = [p_drill]

    if c_balls < 40 or c_time < 30:
        session_tier = "⚡ Express Micro-Session (Focus Drill)"
        adaptation_reason = f"Micro-session detected ({c_balls} balls / {c_time} mins). Prioritizing Primary Drill ({p_drill}) only."
    else:
        if s_drill and s_drill != p_drill:
            active_drills.append(s_drill)
            session_tier = "🔥 Multi-Fault Correction Circuit"
            adaptation_reason = f"Sufficient resources ({c_balls} balls / {c_time} mins). Addressing Primary ({p_drill}) and Secondary ({s_drill}) swing issues."
        else:
            session_tier = "🎯 Deep Focus Primary Calibration"
            adaptation_reason = f"Single clear fault detected. Allocating full grind duration to primary drill ({p_drill})."

    st.info(f"**{session_tier}:** {adaptation_reason}")

    # Render Active Drills
    for idx, d_name in enumerate(active_drills, 1):
        schematic = DRILL_SCHEMATICS.get(d_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"])

        st.markdown(f"### 🎯 Drill #{idx}: **{d_name}**")

        st.image(schematic["image_url"], caption=f"Visual Setup Blueprint — {d_name}", use_container_width=True)

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

    # Dynamic Execution Protocol
    g_balls = res["grind_balls"]
    gm_balls = res["game_balls"]
    g_time = res["grind_time"]
    gm_time = res["game_time"]
    spb = res["sec_per_ball"]

    if len(active_drills) == 2:
        d1_balls = g_balls // 2
        d2_balls = g_balls - d1_balls
        d1_time = g_time // 2
        d2_time = g_time - d1_time

        st.success("🔥 **Dual-Fault Circuit Plan**")

        plan_text = f"* **Block 1 Primary Fault Correction ({d1_balls} Balls | {d1_time} Mins):** Execute *{active_drills[0]}*. Fix primary swing error.\n* **Block 2 Secondary Fault Correction ({d2_balls} Balls | {d2_time} Mins):** Execute *{active_drills[1]}*. Address secondary mechanic."

        # Only display Block 3 if resources are allocated to Game/Target mode
        if gm_balls > 0 and gm_time > 0:
            plan_text += f"\n* **Block 3 Target Course Pressure ({gm_balls} Balls | {gm_time} Mins):** 9-hole target range simulation. Full pre-shot routine per ball."

        st.markdown(plan_text)

    else:
        st.info("🎯 **Single Drill Focus Plan**")

        plan_text = f"* **Block 1 Technical Grind ({g_balls} Balls | {g_time} Mins):** Paced reps using *{active_drills[0]}* at ~{spb}s per shot."

        # Only display Block 2 if resources are allocated to Game/Target mode
        if gm_balls > 0 and gm_time > 0:
            plan_text += f"\n* **Block 2 Target Pressure ({gm_balls} Balls | {gm_time} Mins):** Alternate target flags and clubs on every rep."

        st.markdown(plan_text)

elif "diagnosis" in st.session_state:
    st.warning("👈 Please click **'✅ Confirm Selection & Generate Execution Plan'** in Section 2 to generate your plan.")
else:
    st.caption("Run a shot diagnosis in Section 1 and confirm resources in Section 2 to get started!")
