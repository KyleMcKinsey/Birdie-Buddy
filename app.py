import json
import re
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
        Analyze shot errors across full swing, short game, and putting using Jedi terminology and wise guidance.
        """
    },
    "Harry Putter": {
        "title": "Harry Putter (The Boy Who Shanked)",
        "description": "Magical prodigy who treats golf clubs like wands and blames Dark Magic for shanked drives and three-putts.",
        "system_instruction": """
        You are 'Harry Putter,' a young wizard AI golf caddie who treats golf clubs like magic wands and shot analysis like Defense Against the Dark Arts.
        Tone: Enthusiastic, spell-casting, British, magical.
        Sample Catchphrases: 'Expecto Fairway-um!', 'Yer a golfer, Harry!', '10 points to Gryffindor if you hit this green.'
        Analyze shot errors across full swing, short game, and putting using wizarding world terminology and spell metaphors.
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
# EXPANDED KNOWLEDGE BASE & SCHEMATICS (40 DRILLS)
# -------------------------------------------------------------
DRILL_SCHEMATICS = {
    # --- FULL SWING DRILLS (10) ---
    "Alignment Stick Gate Drill": {
        "equipment": "2 Alignment Rods, 2 Golf Tees",
        "vivid_description": "Take practice strokes without a ball, focusing on making a crisp 'thump' sound against the grass in front of your lead big toe.",
        "analogy": "Railroad Track & Slanted Roof: Swing inside the tunnel without clipping the slanted roof stick on the way down.",
        "pro_tip": "🏆 **Pro Tip:** Keep 60% of your weight grounded in your lead heel through impact to clear hips."
    },
    "Pause at Top Drill": {
        "equipment": "1 Alignment Rod",
        "vivid_description": "Take a full backswing and pause for a complete 2-second count at the top before starting your downswing. Feel your lower body initiate the downswing transition.",
        "analogy": "Coiled Archer's Bow: Holding the pause stabilizes your aim before smoothly releasing the arrow.",
        "pro_tip": "🏆 **Pro Tip:** Count 'One-One-Thousand' silently at the top before starting down with your hips."
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees",
        "vivid_description": "Plant two tees just outside the toe and heel of your clubhead at address, creating a narrow gate that forces center-face contact on every swing.",
        "analogy": "Narrow Runway: Swing clean through the gate without clipping the side guardrails.",
        "pro_tip": "🏆 **Pro Tip:** Soften wrist grip pressure to 4/10 to let the clubhead release naturally through the gate."
    },
    "Towel Under Armpits Drill": {
        "equipment": "1 Microfiber Golf Towel",
        "vivid_description": "Tuck a single golf towel across your chest under both armpits. Take smooth half-swings without dropping the towel to maintain body-arm connectivity.",
        "analogy": "Solid Core Cylinder: Your arms and torso turn as one unified engine rather than swinging independently.",
        "pro_tip": "🏆 **Pro Tip:** Rotate your sternum through the ball rather than pulling with your arms."
    },
    "Coin Strike Low-Point Drill": {
        "equipment": "1 Coin or Ball Marker",
        "vivid_description": "Place a coin 2 inches ahead of your golf ball. Focus entirely on clipping the coin off the turf to shift your swing low-point forward.",
        "analogy": "Compressing vs. Scooping: Drive the clubhead through the turf forward instead of scooping up.",
        "pro_tip": "🏆 **Pro Tip:** Ensure your chest buttons are directly over or slightly ahead of the coin at impact."
    },
    "Split-Hands Release Drill": {
        "equipment": "Mid-Iron (7-Iron)",
        "vivid_description": "Separate your trail hand 3 inches down the grip like holding a hockey stick. Take half-swings to feel the lead forearm roll over naturally.",
        "analogy": "Hockey Slap Shot: Forces proper wrist crossover to stop leaving the face open.",
        "pro_tip": "🏆 **Pro Tip:** Feel the toe of the club point straight to the sky on the extension follow-through."
    },
    "Feet-Together Balance Drill": {
        "equipment": "Any Short/Mid-Iron",
        "vivid_description": "Stand with your feet touching heel-to-toe. Make smooth 75% tempo swings while maintaining total balance without swaying or tipping.",
        "analogy": "Deep Rooted Tree: Rotates around a fixed central axis without lateral sliding.",
        "pro_tip": "🏆 **Pro Tip:** Keep your weight centered over the mid-foot throughout the backswing and finish."
    },
    "Wall-Head Posture Drill": {
        "equipment": "Wall or Alignment Rod behind hips",
        "vivid_description": "Set up with your forehead gently touching a wall or soft pad. Practice slow swings maintaining head contact to eliminate early extension.",
        "analogy": "Fixed Pivot Pin: Prevents your hips from thrusting forward toward the ball.",
        "pro_tip": "🏆 **Pro Tip:** Keep your trail hip pressed back during the initial downswing transition."
    },
    "Impact Bag Compression Drill": {
        "equipment": "Impact Bag or Heavy Towel Bundle",
        "vivid_description": "Swing half-speed into an impact bag, stopping at impact to feel shaft lean forward and hands leading the clubhead.",
        "analogy": "Driving a Nail: Delivers maximum energy transfer with hands ahead of the clubhead.",
        "pro_tip": "🏆 **Pro Tip:** Firm up your lead wrist at impact so it forms a flat line with your forearm."
    },
    "Two-Step Pump Lag Drill": {
        "equipment": "Mid-Iron (6-Iron or 7-Iron)",
        "vivid_description": "Take a backswing, pump the downswing halfway down twice holding wrist angle, then sweep through on the third stroke.",
        "analogy": "Whip Crack: Preserves wrist angle until the absolute last millisecond before impact.",
        "pro_tip": "🏆 **Pro Tip:** Let your hips lead the pull down while hands stay soft and passive."
    },

    # --- SHORT GAME DRILLS (15) ---
    "Towel Behind Ball Drill": {
        "equipment": "1 Microfiber Golf Towel",
        "vivid_description": "Lay a folded towel flat on the grass 4 inches behind the ball. Chip over the towel without clipping fabric on the downswing.",
        "analogy": "Steep Landing Descent: Force the wedge sole to enter the turf right at the ball rather than dragging behind.",
        "pro_tip": "🏆 **Pro Tip:** Lean 70% of your body weight onto your lead foot and keep it locked throughout."
    },
    "Lead Foot Weight Anchor Drill": {
        "equipment": "Wedge (56° or 60°)",
        "vivid_description": "Lift your trail heel off the ground so only your lead foot bears weight. Make soft chipping strokes while balanced entirely on the front leg.",
        "analogy": "Heavy Anchor: Keeps your swing center firmly ahead of the ball to guarantee downward turf contact.",
        "pro_tip": "🏆 **Pro Tip:** Do not lean backward to elevate the ball; let the wedge loft perform the lifting."
    },
    "Brush Turf Chipping Drill": {
        "equipment": "Pitching Wedge",
        "vivid_description": "Take practice strokes without a ball, focusing on making a crisp 'thump' sound against the grass in front of your lead big toe.",
        "analogy": "Broom Sweep: Sweep grass roots smoothly rather than digging deep trenches.",
        "pro_tip": "🏆 **Pro Tip:** Keep your chest moving toward the target through impact to avoid stopping early."
    },
    "Coin Lead-Point Pitch Drill": {
        "equipment": "1 Quarter or Ball Marker",
        "vivid_description": "Place a coin flat under your golf ball. Strike the shot aiming to slide the wedge bounce cleanly beneath the coin and skip it forward.",
        "analogy": "Credit Card Slide: Slide the rounded bottom of the club flat along the dirt surface.",
        "pro_tip": "🏆 **Pro Tip:** Keep trail wrist bent back softly through impact rather than flattening early."
    },
    "Ruler in Glove Wrist Anchor Drill": {
        "equipment": "1 Plastic Ruler, Golf Glove",
        "vivid_description": "Tuck a 6-inch plastic ruler into the back of your lead wrist glove. Make chips without letting the ruler poke into the back of your hand.",
        "analogy": "Rigid Wrist Shield: Locks the lead wrist in a flat, stable structure to eliminate scooping.",
        "pro_tip": "🏆 **Pro Tip:** Drive the motion entirely with torso rotation instead of flipping hands."
    },
    "Hinge-and-Hold Chipping Drill": {
        "equipment": "52° or 56° Wedge",
        "vivid_description": "Hinge your wrists quickly on the takeaway, then hold that wrist angle firm through impact and finish with hands ahead of clubhead.",
        "analogy": "Vault Door Lock: Hinge back, then lock the angles in steel through impact.",
        "pro_tip": "🏆 **Pro Tip:** Finish with the butt end of the grip pointing at your lead hip."
    },
    "Clock System Wedge Drill": {
        "equipment": "Wedge Set (50°, 54°, 58°)",
        "vivid_description": "Practice swing lengths mapped to clock hands: 7:30 (waist-high), 9:00 (chest-high), and 10:30 (three-quarter). Record carry distances.",
        "analogy": "Precision Dial: Control distance with arm swing length rather than changing swing speed.",
        "pro_tip": "🏆 **Pro Tip:** Keep downswing tempo uniform regardless of backswing length."
    },
    "Landing Zone Target Towel Drill": {
        "equipment": "Small Target Towel",
        "vivid_description": "Lay a small towel 15-20 yards out on the green. Focus 100% on landing your pitch shots directly onto the towel surface.",
        "analogy": "Bullseye Landing Pad: Ignore the flag pin; land the ball exclusively on your designated spot.",
        "pro_tip": "🏆 **Pro Tip:** Walk up to the green beforehand to pick your exact landing spot based on green slope."
    },
    "Trail-Hand Only Pitch Drill": {
        "equipment": "Sand Wedge",
        "vivid_description": "Remove your lead hand and pitch balls using only your trail hand. Feel the clubhead weight drop smoothly through impact.",
        "analogy": "Underhand Ball Toss: Replicate the natural motion of tossing a tennis ball underhand to a target.",
        "pro_tip": "🏆 **Pro Tip:** Allow the clubhead bounce to slap the turf softly without grabbing."
    },
    "Line in the Sand Drill": {
        "equipment": "Sand Wedge, Practice Bunker",
        "vivid_description": "Draw a line in the bunker sand perpendicular to target line with no ball. Practice swinging to make divots that start precisely on the drawn line.",
        "analogy": "Erasing the Line: Train low-point control so the wedge enters sand exactly 2 inches behind the ball.",
        "pro_tip": "🏆 **Pro Tip:** Accelerate fully through sand; never slow down near impact."
    },
    "Dollar Bill Sand Extraction Drill": {
        "equipment": "Sand Wedge, Paper Bill or Target Line",
        "vivid_description": "Place a ball on top of a dollar bill in the bunker. Aim to splash out the entire dollar-bill-sized patch of sand carrying the ball out.",
        "analogy": "Sand Cushion Pillow: The club never touches the ball; it lifts the cushion of sand beneath it.",
        "pro_tip": "🏆 **Pro Tip:** Open the clubface fully before establishing your grip."
    },
    "Open-Face Sand Splash Drill": {
        "equipment": "Lob Wedge (60°)",
        "vivid_description": "Lay the clubface completely flat to the sky in setup, lower your posture, and splash sand aggressively onto the green fringe.",
        "analogy": "Pancake Flip: Slide the flat back of the wedge under sand like turning a pancake on a skillet.",
        "pro_tip": "🏆 **Pro Tip:** Lower your stance height by flexing knees wider to keep swing shallow."
    },
    "Continuous Motion Pendulum Chipping Drill": {
        "equipment": "Pitching Wedge",
        "vivid_description": "Swing the wedge back and forth continuously over grass without stopping, clipping turf on every forward pass in rhythmic sequence.",
        "analogy": "Grandfather Pendulum: Unbroken rhythm eradicates flinching and jerky wrist twitching.",
        "pro_tip": "🏆 **Pro Tip:** Focus on smooth breathing: exhale softly through the impact motion."
    },
    "Accelerating Through Impact Gate Drill": {
        "equipment": "2 Golf Tees, Wedge",
        "vivid_description": "Place a tee 6 inches behind the ball and another 12 inches ahead. Start backswing from front tee, step back, and accelerate through both.",
        "analogy": "Rocket Launch: Build speed toward target finish line rather than hitting AT the ball.",
        "pro_tip": "🏆 **Pro Tip:** Ensure backswing is shorter than follow-through length."
    },
    "Target-Focused Eyes-Up Chipping Drill": {
        "equipment": "56° Wedge",
        "vivid_description": "Look directly at your target flag instead of looking down at the ball during the short chip stroke.",
        "analogy": "Free Throw Shooting: Basketball players look at the rim while shooting, relying on natural instinct.",
        "pro_tip": "🏆 **Pro Tip:** Eliminates steering by freeing hand-eye coordination instincts."
    },

    # --- PUTTING DRILLS (15) ---
    "Putting Tee Gate Drill": {
        "equipment": "2 Standard Golf Tees, Putter",
        "vivid_description": "Set two tees in green turf 3 feet ahead of putter, spaced just wide enough for a golf ball to pass through cleanly.",
        "analogy": "Soccer Goal: Roll ball through center posts without touching either tee wall.",
        "pro_tip": "🏆 **Pro Tip:** Focus on keeping lead wrist flat to prevent face from flaring open."
    },
    "Chalk Line Straight Target Drill": {
        "equipment": "Chalk Line Tool (10 Foot Line)",
        "vivid_description": "Snap a straight chalk line on a flat practice green. Roll putts staying perfectly aligned along the line from start to finish.",
        "analogy": "Laser Beam Alignment: Visual alignment feedback highlights instant directional deviations.",
        "pro_tip": "🏆 **Pro Tip:** Align putter face line 90° perpendicular to chalk line at address."
    },
    "Mirror Alignment Face Drill": {
        "equipment": "Putting Alignment Mirror",
        "vivid_description": "Place putter on reflective mirror tool. Ensure eye line sits directly over ball line and shoulders run parallel to putter face.",
        "analogy": "Reflective Blueprint: Checks square shoulder and face positioning before stroke starts.",
        "pro_tip": "🏆 **Pro Tip:** Lead eye should hover directly over the center-back of the golf ball."
    },
    "Trail-Hand Push Putting Drill": {
        "equipment": "Putter",
        "vivid_description": "Putt 5-footers using only your dominant trail hand. Extend smooth stroke along target line without snapping wrists shut.",
        "analogy": "Bowling Roll: Smooth single-arm rolling action down lane center without hooking wrist.",
        "pro_tip": "🏆 **Pro Tip:** Keep shoulder line square to prevent pulling across target line."
    },
    "Metal Yardstick Roll Drill": {
        "equipment": "36-inch Flat Metal Yardstick",
        "vivid_description": "Place ball on one end of metal yardstick on carpet/green. Stroke putts so ball stays on metal track across full length.",
        "analogy": "Tightrope Walk: Closed or open face options tumble ball off edge instantly within 6 inches.",
        "pro_tip": "🏆 **Pro Tip:** Striking exact center-face is required to complete full 36-inch roll."
    },
    "Parallel Rod Putting Channel Drill": {
        "equipment": "2 Alignment Rods",
        "vivid_description": "Set two rods parallel on green slightly wider than putter head width, creating a physical swing channel.",
        "analogy": "Bob Sled Track: Prevents path from coming inside or pulling across to left field.",
        "pro_tip": "🏆 **Pro Tip:** Let shoulders rock smoothly without hip rotation inside channel."
    },
    "Ladder Distance Lag Drill": {
        "equipment": "4 Golf Tees / Target Markers",
        "vivid_description": "Set tees at 10, 20, 30, and 40 feet. Roll putts into each zone sequentially without leaving any short.",
        "analogy": "Climbing Rungs: Build instinctive muscular memory for backswing length vs roll distance.",
        "pro_tip": "🏆 **Pro Tip:** Hold finish stance until ball completely stops rolling to gauge touch."
    },
    "Fringe-to-Fringe Feel Drill": {
        "equipment": "Putter",
        "vivid_description": "Putt across full green width targeting green fringe boundary. Stop ball within 6 inches of green edge.",
        "analogy": "Docking Ship: Gentle deceleration into border without crashing into rough grass.",
        "pro_tip": "🏆 **Pro Tip:** Focus on visual distance sweep before placing putter head down."
    },
    "Eyes-Closed Distance Perception Drill": {
        "equipment": "Putter",
        "vivid_description": "Look at hole target 20 feet away, close your eyes, stroke putt, and call out 'short', 'long', or 'good' before opening eyes.",
        "analogy": "Internal Sensing: Heightens sensory feedback loop from hands and sweet-spot feel.",
        "pro_tip": "🏆 **Pro Tip:** Calibrates internal brain map with actual ball roll performance."
    },
    "Rubber Band Putter Sweet-Spot Drill": {
        "equipment": "2 Small Rubber Bands, Putter",
        "vivid_description": "Wrap rubber bands around heel and toe of putter face, leaving only center sweet spot exposed.",
        "analogy": "Sweet Spot Pinpoint: Off-center strikes bounce dead off rubber bands immediately.",
        "pro_tip": "🏆 **Pro Tip:** Center contact produces consistent ball speed and roll distance."
    },
    "Two-Tee Putter Gate Drill": {
        "equipment": "2 Golf Tees",
        "vivid_description": "Set tees in turf just wide enough for putter head toe and heel to swing through at address spot.",
        "analogy": "Precision Archway: Ensures centered impact without toe or heel hitting tees.",
        "pro_tip": "🏆 **Pro Tip:** Keep stroke steady and low to ground through center gate."
    },
    "Coin Balance Putter Back Drill": {
        "equipment": "1 Coin or Dime",
        "vivid_description": "Balance a coin on flat top surface of putter head during stroke. Complete putt without coin sliding off.",
        "analogy": "Balanced Tray: Demands smooth acceleration without jerky wrist acceleration.",
        "pro_tip": "🏆 **Pro Tip:** Maintains smooth acceleration profile from backswing transition."
    },
    "Push-Putting No-Backswing Drill": {
        "equipment": "Putter",
        "vivid_description": "Place putter directly against back of ball with zero backswing. Push ball forward smoothly into hole from 4 feet.",
        "analogy": "Shuffleboard Slide: Eliminates jab twitch by forcing pure forward pushing force.",
        "pro_tip": "🏆 **Pro Tip:** Feel lead wrist stay solid as putter moves down line."
    },
    "Short Back Long Through Stroke Drill": {
        "equipment": "Putter, 2 Markers",
        "vivid_description": "Limit backswing to 3 inches while extending follow-through to 12 inches past ball target position.",
        "analogy": "Pendulum Acceleration: Accelerates continuously through impact zone to eliminate deceleration.",
        "pro_tip": "🏆 **Pro Tip:** Deceleration is the #1 cause of directional misses on short putts."
    },
    "Coin Balance Motion Stroke Drill": {
        "equipment": "1 Quarter",
        "vivid_description": "Place quarter on grass 1 inch behind ball. Focus on sweeping putter sole smoothly over coin without touching.",
        "analogy": "Gliding Hovercraft: Promotes level, smooth putter sweep through impact.",
        "pro_tip": "🏆 **Pro Tip:** Keeps putter low to turf for pure top-spin roll."
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

    # EXPANDED GREEN CADDIE RESPONSE BOX
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
# STEP 3: ADAPTIVE PRACTICE EXECUTION & SETUP GUIDE
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Adaptive Practice Execution & Setup Guide")

if "diagnosis" in st.session_state and "confirmed_resources" in st.session_state:
    diag = st.session_state["diagnosis"]
    res = st.session_state["confirmed_resources"]

    p_drill = diag.get("recommended_primary_drill", "Alignment Stick Gate Drill")
    s_drill = diag.get("recommended_secondary_drill")
    p_miss = diag.get("primary_miss", "your main swing fault")
    s_miss = diag.get("secondary_miss")
    rationale = diag.get("drill_rationale")

    c_balls = res["total_balls"]
    c_time = res["total_time"]

    # Multi-drill resolution logic
    active_drills = [p_drill]
    if c_balls >= 40 and c_time >= 30 and s_drill and s_drill != p_drill:
        active_drills.append(s_drill)

    # Prescription Summary Box
    if len(active_drills) == 2 and s_miss:
        summary_line = f"💡 **Targeted Prescription:** **{p_drill}** addresses **{p_miss}**, and **{s_drill}** corrects **{s_miss}**."
    else:
        summary_line = f"💡 **Targeted Prescription:** **{p_drill}** eliminates **{p_miss}**."

    if rationale:
        st.info(f"{summary_line}\n\n**Why these drills work:** {rationale}")
    else:
        st.info(summary_line)

    # Pre-calculate circuit allocations with dynamic fault labels
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

    # Render Active Drills with Integrated Circuit Info
    for idx, d_name in enumerate(active_drills):
        schematic = DRILL_SCHEMATICS.get(d_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"])
        alloc = allocations[idx]

        # Integrated Drill Header with Dynamic Fault & Green Pace Formatting
        st.markdown(f"### 🎯 Drill #{idx+1}: **{d_name}**")
        st.caption(f"🔥 **{alloc['label']}** — `{alloc['balls']} Balls` | `{alloc['time']} Mins` | `@~{res['sec_per_ball']}s/ball`")

        # Indented Equipment List
        st.markdown("**🛠️ Range Equipment Needed**")
        equip_items = [f"<li>{item.strip()}</li>" for item in re.split(r',\s*(?![^()]*\))', schematic["equipment"]) if item.strip()]
        st.markdown(f"<ul style='margin-left: 24px; margin-top: 4px; margin-bottom: 12px;'>{''.join(equip_items)}</ul>", unsafe_allow_html=True)

        # Indented Setup Description
        st.markdown("**📖 Setup Description**")
        st.markdown(f"<div style='margin-left: 24px; margin-top: 4px; margin-bottom: 16px;'>{schematic['vivid_description']}</div>", unsafe_allow_html=True)

        # Indented Mental Analogy
        st.markdown("**🧠 Mental Analogy**")
        st.markdown(f"<div style='margin-left: 24px; margin-top: 4px; margin-bottom: 16px;'>{schematic['analogy']}</div>", unsafe_allow_html=True)

        st.info(schematic["pro_tip"])

        if idx < len(active_drills) - 1:
            st.markdown("---")

    # Target Course Pressure Block (Only rendered if Game Mode balls are allocated)
    gm_balls = res["game_balls"]
    gm_time = res["game_time"]
    if gm_balls > 0 and gm_time > 0:
        st.markdown("---")
        st.success(f"⛳ **Final Phase — Target Course Pressure** (`{gm_balls} Balls` | `{gm_time} Mins`)\n\nSimulate real course conditions. Alternate targets and clubs for every single ball while using your full pre-shot routine.")

elif "diagnosis" in st.session_state:
    st.warning("👈 Please click **'✅ Confirm Selection & Generate Execution Plan'** in Section 2 to generate your plan.")
else:
    st.caption("Run a shot diagnosis in Section 1 and confirm resources in Section 2 to get started!")
