from datetime import datetime
import json
import os
import re
import google.generativeai as genai
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Birdie Buddy MVP", page_icon="⛳", layout="centered"
)

CSV_FILE = "birdie_buddy_practice_history.csv"


HISTORY_COLUMNS = [
    "Timestamp",
    "Score",
    "Fairways Hit",
    "GIR",
    "Putts",
    "Penalty Strokes",
    "Problem Area",
    "Primary Macro-Fault",
    "Secondary Fault",
    "Miss Frequency",
    "Primary Drill",
    "ROI Opportunity",
    "AI Confidence",
    "Drill Completed?",
    "Fix Effectiveness (1-5)",
    "Handicap",
    "ROI Priority",
    "ROI Score",
]


# --- PERSISTENT SPREADSHEET HELPERS ---
# History lives in st.session_state (always works, even on hosted Streamlit),
# and we ALSO try to write a CSV on disk as a bonus backup.
def _init_history():
    """Make sure session history exists; seed it from the CSV if one is there."""
    if "practice_history" not in st.session_state:
        seeded = []
        if os.path.exists(CSV_FILE):
            try:
                disk_df = pd.read_csv(CSV_FILE, keep_default_na=False)
                seeded = disk_df.to_dict("records")
            except Exception:
                seeded = []
        st.session_state["practice_history"] = seeded


def load_history_df():
    _init_history()
    rows = st.session_state["practice_history"]
    if not rows:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


def _blank_if_none(val):
    return val if val not in (None, "-- Not Specified --") else "N/A"


def save_session_to_csv(
    primary_miss,
    primary_drill,
    secondary_miss="",
    roi_opportunity="",
    score=None,
    fairways_hit=None,
    gir=None,
    putts=None,
    penalty_strokes=None,
    problem_area="",
    miss_freq="",
    confidence=None,
    handicap=None,
    roi_priority="",
    roi_score=None,
):
    _init_history()
    row = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Score": score if score not in (None, "") else "N/A",
        "Fairways Hit": fairways_hit if fairways_hit not in (None, "") else "N/A",
        "GIR": gir if gir not in (None, "") else "N/A",
        "Putts": putts if putts not in (None, "") else "N/A",
        "Penalty Strokes": (
            penalty_strokes if penalty_strokes not in (None, "") else "N/A"
        ),
        "Problem Area": _blank_if_none(problem_area),
        "Primary Macro-Fault": primary_miss if primary_miss else "N/A",
        "Secondary Fault": secondary_miss if secondary_miss else "N/A",
        "Miss Frequency": _blank_if_none(miss_freq),
        "Primary Drill": primary_drill if primary_drill else "N/A",
        "ROI Opportunity": roi_opportunity if roi_opportunity else "N/A",
        "AI Confidence": confidence if confidence not in (None, "") else "N/A",
        "Drill Completed?": "",
        "Fix Effectiveness (1-5)": "",
        "Handicap": handicap if handicap not in (None, "") else "N/A",
        "ROI Priority": roi_priority if roi_priority else "N/A",
        "ROI Score": roi_score if roi_score not in (None, "") else "N/A",
    }

    # 1. Save to memory first - this is what the sidebar reads.
    st.session_state["practice_history"].append(row)

    # 2. Try to also write the CSV file. If the disk is read-only
    #    (common on hosted Streamlit), we quietly skip it instead of crashing.
    try:
        new_row = pd.DataFrame([row], columns=HISTORY_COLUMNS)
        if not os.path.exists(CSV_FILE):
            new_row.to_csv(CSV_FILE, index=False)
        else:
            new_row.to_csv(CSV_FILE, mode="a", header=False, index=False)
    except Exception as file_error:
        st.session_state["history_file_warning"] = str(file_error)


def update_last_session_feedback(completed_label, effectiveness):
    """Called next visit: closes the loop on the PREVIOUS round's drill."""
    _init_history()
    rows = st.session_state["practice_history"]
    if not rows:
        return
    rows[-1]["Drill Completed?"] = completed_label
    rows[-1]["Fix Effectiveness (1-5)"] = effectiveness

    # Rewrite the whole CSV so the update is reflected on disk too.
    try:
        pd.DataFrame(rows, columns=HISTORY_COLUMNS).to_csv(CSV_FILE, index=False)
    except Exception as file_error:
        st.session_state["history_file_warning"] = str(file_error)


def clear_history_csv():
    st.session_state["practice_history"] = []
    try:
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)
    except Exception:
        pass


# --- HELPER FUNCTIONS FOR CLEAN UI & EXPORTS ---
def render_indented_html(content: str, margin_left: int = 24):
    st.markdown(
        f"<div style='margin-left: {margin_left}px; margin-top: 4px;"
        f" margin-bottom: 16px;'>{content}</div>",
        unsafe_allow_html=True,
    )


def render_indented_ul(items: list, margin_left: int = 24):
    list_items = "".join(
        [f"<li>{item.strip()}</li>" for item in items if item.strip()]
    )
    st.markdown(
        f"<ul style='margin-left: {margin_left}px; margin-top: 4px;"
        f" margin-bottom: 12px;'>{list_items}</ul>",
        unsafe_allow_html=True,
    )


def render_progress_loop(df_history):
    """Front-and-center 'did the fix actually work' banner.

    Closes the loop between diagnosis and outcome: shows whether the
    fault flagged last time recurred, whether the assigned drill was
    logged as completed, and how the score is trending. This is meant
    to be the first thing a user sees after their history exists, so
    the app reads as adaptive coaching rather than a one-shot report.
    """
    if df_history.empty:
        return

    rows = df_history.to_dict("records")
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None

    st.markdown("### 🔁 Your Progress Loop")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Rounds Logged", len(rows))

    with col2:
        scores = pd.to_numeric(df_history["Score"], errors="coerce").dropna()
        if len(scores) >= 2:
            delta = scores.iloc[-1] - scores.iloc[-2]
            st.metric(
                "Latest Score",
                f"{int(scores.iloc[-1])}",
                delta=f"{int(delta)}",
                delta_color="inverse",
            )
        elif len(scores) == 1:
            st.metric("Latest Score", f"{int(scores.iloc[-1])}")
        else:
            st.metric("Latest Score", "N/A")

    with col3:
        last_fault = latest.get("Primary Macro-Fault", "N/A")
        if previous is not None:
            prev_fault = previous.get("Primary Macro-Fault", "N/A")
            if last_fault != "N/A" and last_fault == prev_fault:
                tag_html = "<span style='color:#b91c1c; font-weight:600;'>🔁 Recurring</span>"
            else:
                tag_html = "<span style='color:#15803d; font-weight:600;'>🆕 New focus</span>"
        else:
            tag_html = ""

        # Custom markup instead of st.metric: st.metric's big-number style
        # truncates/clips long drill-fault names, so we render this as a
        # normal-sized, wrapping label instead.
        st.markdown(
            "<div style='font-size: 0.75rem; color: #808495; margin-bottom: 2px;'>"
            "Primary Fault</div>"
            f"<div style='font-size: 0.85rem; font-weight: 600; line-height: 1.25;"
            f" word-wrap: break-word; overflow-wrap: break-word; hyphens: auto;'>{last_fault}</div>"
            f"<div style='font-size: 0.8rem; margin-top: 2px;'>{tag_html}</div>",
            unsafe_allow_html=True,
        )

    drill_done = str(latest.get("Drill Completed?", "")).strip()
    if not drill_done:
        st.info(
            "📝 You haven't logged whether last round's assigned drill helped yet —"
            " scroll down to close the loop before starting a new diagnosis."
        )
    elif previous is not None and last_fault == previous.get("Primary Macro-Fault", "N/A") and last_fault != "N/A":
        st.warning(
            f"⚠️ **{last_fault}** was your #1 fault again last time, even after"
            f" logging '{drill_done}' on the assigned drill. Worth flagging to your"
            " caddie in this round's story so it adjusts the fix."
        )
    else:
        st.success("✅ No repeat faults from last time — keep logging to build the trend.")

    st.markdown("---")


def build_export_card(diag, res, active_drills, drill_schematics, caddie):
    lines = []
    lines.append("=" * 50)
    lines.append("⛳ BIRDIE BUDDY RANGE PRACTICE CARD")
    lines.append("=" * 50)
    lines.append(f"Caddie Persona: {caddie}")
    lines.append(f"Primary Macro-Fault: {diag.get('primary_miss', 'N/A')}")
    if diag.get("secondary_miss"):
        lines.append(f"Secondary Fault: {diag.get('secondary_miss')}")
    lines.append(
        f"Total Allocation: {res['total_balls']} Balls | {res['total_time']} Mins"
        f" (@ {res['sec_per_ball']}s/ball)"
    )
    lines.append("-" * 50)
    lines.append("\nVALUE CHAIN LEAK BREAKDOWN:")
    vc = diag.get("value_chain_analysis", {})
    lines.append(f"- Off-the-Tee Strategy (Primary Drive): {vc.get('off_the_tee', 'N/A')}")
    lines.append(f"- Approach Precision (Mid Game): {vc.get('approach', 'N/A')}")
    lines.append(
        f"- Scoring/Scrambling (Short Game/Putting): {vc.get('scoring_scrambling', 'N/A')}"
    )
    lines.append(
        f"- Mental Infrastructure (Support Systems): {vc.get('mental_infrastructure', 'N/A')}"
    )
    lines.append(f"- #1 Leak Stage: {vc.get('primary_leak_stage', 'N/A')}")
    if vc.get("leak_rationale"):
        lines.append(f"- Why This Stage Wins ROI: {vc.get('leak_rationale')}")
    blind_spot = diag.get("diagnostic_blind_spot")
    if blind_spot:
        lines.append(f"\nBLIND SPOT FLAGGED (not in your story, found in your numbers):")
        lines.append(f"- {blind_spot}")
    lines.append("\n" + "=" * 50)
    lines.append("DRILL EXECUTION SCHEDULE")
    lines.append("=" * 50)

    num_drills = len(active_drills)
    is_pure_game = (
        res.get("practice_mode") == "Pure Game Mode (100% Target Pressure)"
    )
    alloc_balls = res["total_balls"] if is_pure_game else res["grind_balls"]
    alloc_time = res["total_time"] if is_pure_game else res["grind_time"]

    for idx, d_name in enumerate(active_drills):
        if num_drills == 1:
            weight = 1.0
        elif num_drills == 2:
            weight = 0.65 if idx == 0 else 0.35
        else:
            weight = 0.60 if idx == 0 else (0.40 / (num_drills - 1))

        balls_per_drill = int(alloc_balls * weight)
        time_per_drill = int(alloc_time * weight)

        schematic = drill_schematics.get(
            d_name, drill_schematics["Alignment Stick Gate Drill"]
        )
        lines.append(f"\nDRILL #{idx+1}: {d_name.upper()}")
        lines.append(f"Target: {balls_per_drill} Balls | {time_per_drill} Mins")
        lines.append(f"Equipment: {schematic['equipment']}")
        lines.append(f"Setup: {schematic['vivid_description']}")
        lines.append(f"Mental Analogy: {schematic['analogy']}")
        lines.append(
            f"Pro Tip: {schematic['pro_tip'].replace('🏆 **Pro Tip:** ', '')}"
        )
        lines.append("-" * 40)

    if res["game_balls"] > 0 and not is_pure_game:
        lines.append("\nFINAL PHASE: Target Course Pressure Simulation")
        lines.append(f"Target: {res['game_balls']} Balls | {res['game_time']} Mins")
        lines.append(
            "Instructions: Alternate clubs & flags for every single ball. Execute"
            " full pre-shot routine."
        )

    return "\n".join(lines)


st.title("⛳ Birdie Buddy (Phase 1 MVP)")
st.caption("AI Golf Caddie & Practice Asset Allocator powered by Gemini")

# Sidebar - API Key Input & Spreadsheet History Exporter
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

# --- SPREADSHEET HISTORY TRACKER & EXPORTER ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Practice History Spreadsheet")

df_history = load_history_df()

if not df_history.empty:
    st.sidebar.write(f"Logged Practice Rounds: **{len(df_history)}**")

    # Download button to export spreadsheet
    csv_data = df_history.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="📥 Export History (CSV)",
        data=csv_data,
        file_name="birdie_buddy_practice_history.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if st.sidebar.button("🗑️ Clear History", use_container_width=True):
        clear_history_csv()
        st.rerun()

    # Color-coded interactive table preview
    with st.sidebar.expander("👁️ View Color-Coded Log", expanded=False):
        def highlight_cols(val):
            if val == "N/A" or not val:
                return "color: #888888; font-style: italic;"
            return "background-color: #1e3a8a22; font-weight: bold;"

        styled_df = df_history.style.map(
            highlight_cols, subset=["Primary Macro-Fault", "Primary Drill"]
        )

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Timestamp": st.column_config.TextColumn("Date/Time"),
                "Score": st.column_config.TextColumn("Score 🏌️"),
                "Fairways Hit": st.column_config.TextColumn("FIR"),
                "GIR": st.column_config.TextColumn("GIR"),
                "Putts": st.column_config.TextColumn("Putts"),
                "Penalty Strokes": st.column_config.TextColumn("Penalties"),
                "Problem Area": st.column_config.TextColumn("Problem Area"),
                "Primary Macro-Fault": st.column_config.TextColumn("Primary Fault 🎯"),
                "Secondary Fault": st.column_config.TextColumn("Secondary Fault ⚠️"),
                "Miss Frequency": st.column_config.TextColumn("Miss Frequency"),
                "Primary Drill": st.column_config.TextColumn("Primary Drill 🛠️"),
                "ROI Opportunity": st.column_config.TextColumn("ROI Fix 📈"),
                "AI Confidence": st.column_config.TextColumn("Confidence"),
                "Drill Completed?": st.column_config.TextColumn("Drill Done?"),
                "Fix Effectiveness (1-5)": st.column_config.TextColumn("Fix Worked?"),
            },
        )

    # --- PROGRESS TRENDS ---
    with st.sidebar.expander("📈 Progress Trends", expanded=False):
        score_series = pd.to_numeric(df_history["Score"], errors="coerce").dropna()
        if len(score_series) >= 2:
            st.caption("Score over time (lower is better)")
            st.line_chart(score_series.reset_index(drop=True))
        else:
            st.caption("Log at least 2 scored rounds to see a score trend.")

        fault_counts = (
            df_history[df_history["Primary Macro-Fault"] != "N/A"]
            ["Primary Macro-Fault"]
            .value_counts()
        )
        if not fault_counts.empty:
            st.caption("Most frequent primary faults")
            st.bar_chart(fault_counts)
        else:
            st.caption("No faults logged yet.")
else:
    st.sidebar.caption(
        "No session history recorded yet. Complete a round diagnosis to populate"
        " your spreadsheet!"
    )

if st.session_state.get("history_file_warning"):
    st.sidebar.caption(
        "ℹ️ History is being kept in this session only (the CSV file could not be"
        " written here). Use the Export button to keep a permanent copy."
    )

if not api_key:
    st.warning("Please paste your Google Gemini API Key in the sidebar to begin.")
    st.stop()

genai.configure(api_key=api_key)

render_progress_loop(df_history)

# -------------------------------------------------------------
# SCORE-ROI PRIORITY ENGINE
# -------------------------------------------------------------
def calculate_score_roi(round_score, fairways_hit, gir, putts, penalty_strokes, handicap=None):
    """Score-ROI proxy used when shot-level Strokes Gained data is unavailable."""
    score = 0.0
    reasons = []

    # Direct stroke tax gets first priority.
    if penalty_strokes:
        score += min(45.0, penalty_strokes * 18.0)
        reasons.append(f"{penalty_strokes} penalty stroke(s) = direct score tax")

    # Approach/GIR is a strong scoring proxy, but GIR alone does not prove a
    # particular swing fault.
    if gir:
        pct = gir / 18.0
        if pct < 0.20:
            score += 34.0
            reasons.append(f"GIR {gir}/18 = severe approach opportunity")
        elif pct < 0.30:
            score += 27.0
            reasons.append(f"GIR {gir}/18 = major approach opportunity")
        elif pct < 0.40:
            score += 17.0
            reasons.append(f"GIR {gir}/18 = meaningful approach opportunity")
        elif pct < 0.50:
            score += 8.0
            reasons.append(f"GIR {gir}/18 = moderate approach opportunity")

    # Putting must be interpreted alongside GIR; high putts are not automatically
    # a putting fault.
    if putts:
        if putts >= 38:
            score += 20.0
            reasons.append(f"{putts} putts = large putting/scoring opportunity")
        elif putts >= 35:
            score += 13.0
            reasons.append(f"{putts} putts = meaningful putting opportunity")
        elif putts >= 33:
            score += 6.0
            reasons.append(f"{putts} putts = investigate in GIR context")

    # FIR is deliberately capped because a fairway miss is not inherently a
    # stroke loss; distance and lie determine the actual scoring consequence.
    if fairways_hit is not None and fairways_hit > 0:
        fir_pct = fairways_hit / 14.0
        if fir_pct < 0.35 and penalty_strokes:
            score += 12.0
            reasons.append(f"{fairways_hit}/14 fairways plus penalties = tee-shot risk")
        elif fir_pct < 0.50:
            score += 5.0
            reasons.append(f"{fairways_hit}/14 fairways = investigate tee-shot consequences")

    score = round(min(100.0, score), 1)
    if score >= 45:
        tier = "CRITICAL — Direct Score Leak"
    elif score >= 30:
        tier = "HIGH — Major Scoring Opportunity"
    elif score >= 18:
        tier = "MEDIUM — Worth Targeting"
    else:
        tier = "LOW — Do Not Chase Without Shot-Level Evidence"
    return {"score": score, "tier": tier, "reasons": reasons}

# -------------------------------------------------------------
# MOVIE PARODY PERSONA DATABASE
# -------------------------------------------------------------
PERSONA_DATABASE = {
    "Bogey-Wan Kenobi (Jedi Master of Swing)": {
        "description": (
            "Wise Jedi mentor guiding you away from the Dark Side (the slice)"
            " using the Force of swing tempo."
        ),
        "system_instruction": """
        You are 'Bogey-Wan Kenobi,' a wise and serene Jedi Master AI golf caddie.
        Tone: Calm, philosophical, dramatic, heroic, slightly cryptic.
        Sample Catchphrases: 'May the Force be with your clubface.', 'These are not the trees you are looking for.', 'Beware the Dark Side—anger leads to an open face.'
        Analyze shot errors and mental focus across full swing, short game, putting, and mindset using Jedi terminology and wise guidance.
        """,
    },
    "Harry Putter (The Boy Who Shanked)": {
        "description": (
            "Magical prodigy who treats golf clubs like wands and blames Dark"
            " Magic for shanked drives and three-putts."
        ),
        "system_instruction": """
        You are 'Harry Putter,' a young wizard AI golf caddie who treats golf clubs like magic wands and shot analysis like Defense Against the Dark Arts.
        Tone: Enthusiastic, spell-casting, British, magical.
        Sample Catchphrases: 'Expecto Fairway-um!', 'Yer a golfer, Harry!', '10 points to Gryffindor if you hit this green.'
        Analyze shot errors and mental focus across full swing, short game, putting, and mindset using wizarding world terminology.
        """,
    },
    "James Pond (Agent 00-Slice)": {
        "description": (
            "Suave secret agent who approaches every shot like a high-stakes MI6"
            " espionage mission."
        ),
        "system_instruction": """
        You are 'James Pond' (Agent 00-Slice), a suave, high-class secret agent AI golf caddie.
        Tone: Cool, sophisticated, covert, tactical, dry British charm.
        Sample Catchphrases: 'Shaken, not stirred—much like your grip pressure.', 'License to slice.', "The name's Pond... James Pond."
        Analyze shot errors and mental composure as if evaluating high-stakes tactical intelligence under pressure.
        """,
    },
    "Captain Hack Sparrow (Pirate of the Fairway)": {
        "description": (
            "Eccentric, unpredictable pirate caddie stumbling through hazards"
            " with rum-fueled optimism and chaotic strategies."
        ),
        "system_instruction": """
        You are 'Captain Hack Sparrow,' an eccentric, wildly unpredictable pirate AI golf caddie.
        Tone: Slurred charm, chaotic, theatrical, witty, rum-obsessed, highly eccentric.
        Sample Catchphrases: 'Why is the fairway always gone?', 'Take what you can, give nothing back—except that ball in the hazard.', 'This shot is either brilliant or mad. Utterly mad.'
        Analyze shot errors and mental blow-ups using nautical pirate metaphors.
        """,
    },
}

# -------------------------------------------------------------
# EXPANDED KNOWLEDGE BASE & SCHEMATICS (45 DRILLS INCL. MENTAL)
# -------------------------------------------------------------
DRILL_SCHEMATICS = {
    # --- FULL SWING DRILLS (10) ---
    "Alignment Stick Gate Drill": {
        "equipment": "2 Alignment Rods, 2 Golf Tees",
        "vivid_description": (
            "Take practice strokes without a ball, focusing on making a crisp"
            " 'thump' sound against the grass in front of your lead big toe."
        ),
        "analogy": (
            "Railroad Track & Slanted Roof: Swing inside the tunnel without"
            " clipping the slanted roof stick on the way down."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep 60% of your weight grounded in your lead heel"
            " through impact to clear hips."
        ),
    },
    "Pause at Top Drill": {
        "equipment": "1 Alignment Rod",
        "vivid_description": (
            "Take a full backswing and pause for a complete 2-second count at"
            " the top before starting your downswing. Feel your lower body"
            " initiate the downswing transition."
        ),
        "analogy": (
            "Coiled Archer's Bow: Holding the pause stabilizes your aim before"
            " smoothly releasing the arrow."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Count 'One-One-Thousand' silently at the top before"
            " starting down with your hips."
        ),
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees",
        "vivid_description": (
            "Plant two tees just outside the toe and heel of your clubhead at"
            " address, creating a narrow gate that forces center-face contact"
            " on every swing."
        ),
        "analogy": (
            "Narrow Runway: Swing clean through the gate without clipping the"
            " side guardrails."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Soften wrist grip pressure to 4/10 to let the"
            " clubhead release naturally through the gate."
        ),
    },
    "Towel Under Armpits Drill": {
        "equipment": "1 Microfiber Golf Towel",
        "vivid_description": (
            "Tuck a single golf towel across your chest under both armpits. Take"
            " smooth half-swings without dropping the towel to maintain"
            " body-arm connectivity."
        ),
        "analogy": (
            "Solid Core Cylinder: Your arms and torso turn as one unified"
            " engine rather than swinging independently."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Rotate your sternum through the ball rather than"
            " pulling with your arms."
        ),
    },
    "Coin Strike Low-Point Drill": {
        "equipment": "1 Coin or Ball Marker",
        "vivid_description": (
            "Place a coin 2 inches ahead of your golf ball. Focus entirely on"
            " clipping the coin off the turf to shift your swing low-point"
            " forward."
        ),
        "analogy": (
            "Compressing vs. Scooping: Drive the clubhead through the turf"
            " forward instead of scooping up."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Ensure your chest buttons are directly over or"
            " slightly ahead of the coin at impact."
        ),
    },
    "Split-Hands Release Drill": {
        "equipment": "Mid-Iron (7-Iron)",
        "vivid_description": (
            "Separate your trail hand 3 inches down the grip like holding a"
            " hockey stick. Take half-swings to feel the lead forearm roll over"
            " naturally."
        ),
        "analogy": (
            "Hockey Slap Shot: Forces proper wrist crossover to stop leaving"
            " the face open."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Feel the toe of the club point straight to the"
            " sky on the extension follow-through."
        ),
    },
    "Feet-Together Balance Drill": {
        "equipment": "Any Short/Mid-Iron",
        "vivid_description": (
            "Stand with your feet touching heel-to-toe. Make smooth 75% tempo"
            " swings while maintaining total balance without swaying or"
            " tipping."
        ),
        "analogy": (
            "Deep Rooted Tree: Rotates around a fixed central axis without"
            " lateral sliding."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep your weight centered over the mid-foot"
            " throughout the backswing and finish."
        ),
    },
    "Wall-Head Posture Drill": {
        "equipment": "Wall or Alignment Rod behind hips",
        "vivid_description": (
            "Set up with your forehead gently touching a wall or soft pad."
            " Practice slow swings maintaining head contact to eliminate early"
            " extension."
        ),
        "analogy": (
            "Fixed Pivot Pin: Prevents your hips from thrusting forward toward"
            " the ball."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep your trail hip pressed back during the initial"
            " downswing transition."
        ),
    },
    "Impact Bag Compression Drill": {
        "equipment": "Impact Bag or Heavy Towel Bundle",
        "vivid_description": (
            "Swing half-speed into an impact bag, stopping at impact to feel"
            " shaft lean forward and hands leading the clubhead."
        ),
        "analogy": (
            "Driving a Nail: Delivers maximum energy transfer with hands ahead"
            " of the clubhead."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Firm up your lead wrist at impact so it forms a"
            " flat line with your forearm."
        ),
    },
    "Two-Step Pump Lag Drill": {
        "equipment": "Mid-Iron (6-Iron or 7-Iron)",
        "vivid_description": (
            "Take a backswing, pump the downswing halfway down twice holding"
            " wrist angle, then sweep through on the third stroke."
        ),
        "analogy": (
            "Whip Crack: Preserves wrist angle until the absolute last"
            " millisecond before impact."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Let your hips lead the pull down while hands stay"
            " soft and passive."
        ),
    },
    # --- SHORT GAME DRILLS (15) ---
    "Towel Behind Ball Drill": {
        "equipment": "1 Microfiber Golf Towel",
        "vivid_description": (
            "Lay a folded towel flat on the grass 4 inches behind the ball. Chip"
            " over the towel without clipping fabric on the downswing."
        ),
        "analogy": (
            "Steep Landing Descent: Force the wedge sole to enter the turf"
            " right at the ball rather than dragging behind."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Lean 70% of your body weight onto your lead foot"
            " and keep it locked throughout."
        ),
    },
    "Lead Foot Weight Anchor Drill": {
        "equipment": "Wedge (56° or 60°)",
        "vivid_description": (
            "Lift your trail heel off the ground so only your lead foot bears"
            " weight. Make soft chipping strokes while balanced entirely on the"
            " front leg."
        ),
        "analogy": (
            "Heavy Anchor: Keeps your swing center firmly ahead of the ball to"
            " guarantee downward turf contact."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Do not lean backward to elevate the ball; let the"
            " wedge loft perform the lifting."
        ),
    },
    "Brush Turf Chipping Drill": {
        "equipment": "Pitching Wedge",
        "vivid_description": (
            "Take practice strokes without a ball, focusing on making a crisp"
            " 'thump' sound against the grass in front of your lead big toe."
        ),
        "analogy": (
            "Broom Sweep: Sweep grass roots smoothly rather than digging deep"
            " trenches."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep your chest moving toward the target through"
            " impact to avoid stopping early."
        ),
    },
    "Coin Lead-Point Pitch Drill": {
        "equipment": "1 Quarter or Ball Marker",
        "vivid_description": (
            "Place a coin flat under your golf ball. Strike the shot aiming to"
            " slide the wedge bounce cleanly beneath the coin and skip it"
            " forward."
        ),
        "analogy": (
            "Credit Card Slide: Slide the rounded bottom of the club flat along"
            " the dirt surface."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep trail wrist bent back softly through impact"
            " rather than flattening early."
        ),
    },
    "Ruler in Glove Wrist Anchor Drill": {
        "equipment": "1 Plastic Ruler, Golf Glove",
        "vivid_description": (
            "Tuck a 6-inch plastic ruler into the back of your lead wrist"
            " glove. Make chips without letting the ruler poke into the back of"
            " your hand."
        ),
        "analogy": (
            "Rigid Wrist Shield: Locks the lead wrist in a flat, stable"
            " structure to eliminate scooping."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Drive the motion entirely with torso rotation"
            " instead of flipping hands."
        ),
    },
    "Hinge-and-Hold Chipping Drill": {
        "equipment": "52° or 56° Wedge",
        "vivid_description": (
            "Hinge your wrists quickly on the takeaway, then hold that wrist"
            " angle firm through impact and finish with hands ahead of"
            " clubhead."
        ),
        "analogy": (
            "Vault Door Lock: Hinge back, then lock the angles in steel"
            " through impact."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Finish with the butt end of the grip pointing at"
            " your lead hip."
        ),
    },
    "Clock System Wedge Drill": {
        "equipment": "Wedge Set (50°, 54°, 58°)",
        "vivid_description": (
            "Practice swing lengths mapped to clock hands: 7:30 (waist-high),"
            " 9:00 (chest-high), and 10:30 (three-quarter). Record carry"
            " distances."
        ),
        "analogy": (
            "Precision Dial: Control distance with arm swing length rather than"
            " changing swing speed."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep downswing tempo uniform regardless of"
            " backswing length."
        ),
    },
    "Landing Zone Target Towel Drill": {
        "equipment": "Small Target Towel",
        "vivid_description": (
            "Lay a small towel 15-20 yards out on the green. Focus 100% on"
            " landing your pitch shots directly onto the towel surface."
        ),
        "analogy": (
            "Bullseye Landing Pad: Ignore the flag pin; land the ball"
            " exclusively on your designated spot."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Walk up to the green beforehand to pick your"
            " exact landing spot based on green slope."
        ),
    },
    "Trail-Hand Only Pitch Drill": {
        "equipment": "Sand Wedge",
        "vivid_description": (
            "Remove your lead hand and pitch balls using only your trail hand."
            " Feel the clubhead weight drop smoothly through impact."
        ),
        "analogy": (
            "Underhand Ball Toss: Replicate the natural motion of tossing a"
            " tennis ball underhand to a target."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Allow the clubhead bounce to slap the turf softly"
            " without grabbing."
        ),
    },
    "Line in the Sand Drill": {
        "equipment": "Sand Wedge, Practice Bunker",
        "vivid_description": (
            "Draw a line in the bunker sand perpendicular to target line with"
            " no ball. Practice swinging to make divots that start precisely"
            " on the drawn line."
        ),
        "analogy": (
            "Erasing the Line: Train low-point control so the wedge enters sand"
            " exactly 2 inches behind the ball."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Accelerate fully through sand; never slow down near"
            " impact."
        ),
    },
    "Dollar Bill Sand Extraction Drill": {
        "equipment": "Sand Wedge, Paper Bill or Target Line",
        "vivid_description": (
            "Place a ball on top of a dollar bill in the bunker. Aim to splash"
            " out the entire dollar-bill-sized patch of sand carrying the ball"
            " out."
        ),
        "analogy": (
            "Sand Cushion Pillow: The club never touches the ball; it lifts"
            " the cushion of sand beneath it."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Open the clubface fully before establishing your"
            " grip."
        ),
    },
    "Open-Face Sand Splash Drill": {
        "equipment": "Lob Wedge (60°)",
        "vivid_description": (
            "Lay the clubface completely flat to the sky in setup, lower your"
            " posture, and splash sand aggressively onto the green fringe."
        ),
        "analogy": (
            "Pancake Flip: Slide the flat back of the wedge under sand like"
            " turning a pancake on a skillet."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Lower your stance height by flexing knees wider to"
            " keep swing shallow."
        ),
    },
    "Continuous Motion Pendulum Chipping Drill": {
        "equipment": "Pitching Wedge",
        "vivid_description": (
            "Swing the wedge back and forth continuously over grass without"
            " stopping, clipping turf on every forward pass in rhythmic"
            " sequence."
        ),
        "analogy": (
            "Grandfather Pendulum: Unbroken rhythm eradicates flinching and"
            " jerky wrist twitching."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Focus on smooth breathing: exhale softly through"
            " the impact motion."
        ),
    },
    "Accelerating Through Impact Gate Drill": {
        "equipment": "2 Golf Tees, Wedge",
        "vivid_description": (
            "Place a tee 6 inches behind the ball and another 12 inches ahead."
            " Start backswing from front tee, step back, and accelerate"
            " through both."
        ),
        "analogy": (
            "Rocket Launch: Build speed toward target finish line rather than"
            " hitting AT the ball."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Ensure backswing is shorter than follow-through"
            " length."
        ),
    },
    "Target-Focused Eyes-Up Chipping Drill": {
        "equipment": "56° Wedge",
        "vivid_description": (
            "Look directly at your target flag instead of looking down at the"
            " ball during the short chip stroke."
        ),
        "analogy": (
            "Free Throw Shooting: Basketball players look at the rim while"
            " shooting, relying on natural instinct."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Eliminates steering by freeing hand-eye"
            " coordination instincts."
        ),
    },
    # --- PUTTING DRILLS (15) ---
    "Putting Tee Gate Drill": {
        "equipment": "2 Standard Golf Tees, Putter",
        "vivid_description": (
            "Set two tees in green turf 3 feet ahead of putter, spaced just wide"
            " enough for a golf ball to pass through cleanly."
        ),
        "analogy": (
            "Soccer Goal: Roll ball through center posts without touching"
            " either tee wall."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Focus on keeping lead wrist flat to prevent face"
            " from flaring open."
        ),
    },
    "Chalk Line Straight Target Drill": {
        "equipment": "Chalk Line Tool (10 Foot Line)",
        "vivid_description": (
            "Snap a straight chalk line on a flat practice green. Roll putts"
            " staying perfectly aligned along the line from start to finish."
        ),
        "analogy": (
            "Laser Beam Alignment: Visual alignment feedback highlights instant"
            " directional deviations."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Align putter face line 90° perpendicular to chalk"
            " line at address."
        ),
    },
    "Mirror Alignment Face Drill": {
        "equipment": "Putting Alignment Mirror",
        "vivid_description": (
            "Place putter on reflective mirror tool. Ensure eye line sits"
            " directly over ball line and shoulders run parallel to putter"
            " face."
        ),
        "analogy": (
            "Reflective Blueprint: Checks square shoulder and face positioning"
            " before stroke starts."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Lead eye should hover directly over the"
            " center-back of the golf ball."
        ),
    },
    "Trail-Hand Push Putting Drill": {
        "equipment": "Putter",
        "vivid_description": (
            "Putt 5-footers using only your dominant trail hand. Extend smooth"
            " stroke along target line without snapping wrists shut."
        ),
        "analogy": (
            "Bowling Roll: Smooth single-arm rolling action down lane center"
            " without hooking wrist."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep shoulder line square to prevent pulling"
            " across target line."
        ),
    },
    "Metal Yardstick Roll Drill": {
        "equipment": "36-inch Flat Metal Yardstick",
        "vivid_description": (
            "Place ball on one end of metal yardstick on carpet/green. Stroke"
            " putts so ball stays on metal track across full length."
        ),
        "analogy": (
            "Tightrope Walk: Closed or open face options tumble ball off edge"
            " instantly within 6 inches."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Striking exact center-face is required to"
            " complete full 36-inch roll."
        ),
    },
    "Parallel Rod Putting Channel Drill": {
        "equipment": "2 Alignment Rods",
        "vivid_description": (
            "Set two rods parallel on green slightly wider than putter head"
            " width, creating a physical swing channel."
        ),
        "analogy": (
            "Bob Sled Track: Prevents path from coming inside or pulling across"
            " to left field."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Let shoulders rock smoothly without hip rotation"
            " inside channel."
        ),
    },
    "Ladder Distance Lag Drill": {
        "equipment": "4 Golf Tees / Target Markers",
        "vivid_description": (
            "Set tees at 10, 20, 30, and 40 feet. Roll putts into each zone"
            " sequentially without leaving any short."
        ),
        "analogy": (
            "Climbing Rungs: Build instinctive muscular memory for backswing"
            " length vs roll distance."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Hold finish stance until ball completely stops"
            " rolling to gauge touch."
        ),
    },
    "Fringe-to-Fringe Feel Drill": {
        "equipment": "Putter",
        "vivid_description": (
            "Putt across full green width targeting green fringe boundary."
            " Stop ball within 6 inches of green edge."
        ),
        "analogy": (
            "Docking Ship: Gentle deceleration into border without crashing"
            " into rough grass."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Focus on visual distance sweep before placing"
            " putter head down."
        ),
    },
    "Eyes-Closed Distance Perception Drill": {
        "equipment": "Putter",
        "vivid_description": (
            "Look at hole target 20 feet away, close your eyes, stroke putt,"
            " and call out 'short', 'long', or 'good' before opening eyes."
        ),
        "analogy": (
            "Internal Sensing: Heightens sensory feedback loop from hands and"
            " sweet-spot feel."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Calibrates internal brain map with actual ball"
            " roll performance."
        ),
    },
    "Rubber Band Putter Sweet-Spot Drill": {
        "equipment": "2 Small Rubber Bands, Putter",
        "vivid_description": (
            "Wrap rubber bands around heel and toe of putter face, leaving only"
            " center sweet spot exposed."
        ),
        "analogy": (
            "Sweet Spot Pinpoint: Off-center strikes bounce dead off rubber"
            " bands immediately."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Center contact produces consistent ball speed and"
            " roll distance."
        ),
    },
    "Two-Tee Putter Gate Drill": {
        "equipment": "2 Golf Tees",
        "vivid_description": (
            "Set tees in turf just wide enough for putter head toe and heel to"
            " swing through at address spot."
        ),
        "analogy": (
            "Precision Archway: Ensures centered impact without toe or heel"
            " hitting tees."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep stroke steady and low to ground through"
            " center gate."
        ),
    },
    "Coin Balance Putter Back Drill": {
        "equipment": "1 Coin or Dime",
        "vivid_description": (
            "Balance a coin on flat top surface of putter head during stroke."
            " Complete putt without coin sliding off."
        ),
        "analogy": (
            "Balanced Tray: Demands smooth acceleration without jerky wrist"
            " acceleration."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Maintains smooth acceleration profile from"
            " backswing transition."
        ),
    },
    "Push-Putting No-Backswing Drill": {
        "equipment": "Putter",
        "vivid_description": (
            "Place putter directly against back of ball with zero backswing."
            " Push ball forward smoothly into hole from 4 feet."
        ),
        "analogy": (
            "Shuffleboard Slide: Eliminates jab twitch by forcing pure forward"
            " pushing force."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Feel lead wrist stay solid as putter moves down"
            " line."
        ),
    },
    "Short Back Long Through Stroke Drill": {
        "equipment": "Putter, 2 Markers",
        "vivid_description": (
            "Limit backswing to 3 inches while extending follow-through to 12"
            " inches past ball target position."
        ),
        "analogy": (
            "Pendulum Acceleration: Accelerates continuously through impact"
            " zone to eliminate deceleration."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Deceleration is the #1 cause of directional misses"
            " on short putts."
        ),
    },
    "Coin Balance Motion Stroke Drill": {
        "equipment": "1 Quarter",
        "vivid_description": (
            "Place quarter on grass 1 inch behind ball. Focus on sweeping"
            " putter sole smoothly over coin without touching."
        ),
        "analogy": (
            "Gliding Hovercraft: Promotes level, smooth putter sweep through"
            " impact."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keeps putter low to turf for pure top-spin roll."
        ),
    },
    # --- MENTAL GAME & MINDSET DRILLS (5) ---
    "1-2-3 Box Breathing Reset Drill": {
        "equipment": "None (Breathwork)",
        "vivid_description": (
            "Inhale for 4 seconds, hold for 4 seconds, and exhale for 4"
            " seconds before stepping into your pre-shot setup. Settle heart"
            " rate and lower heart beat."
        ),
        "analogy": (
            "System Reboot Button: Clears mental noise and anxiety before"
            " entering the target execution area."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Exhale fully through your nose right before placing"
            " your clubface behind the ball."
        ),
    },
    "Post-Shot Acceptance Hold Drill": {
        "equipment": "Golf Club, 3-Second Count",
        "vivid_description": (
            "Hold your balanced finish pose for 3 full seconds post-impact"
            " regardless of where the ball flies. Observe result with zero"
            " emotional outburst."
        ),
        "analogy": (
            "Neutral Journalist: Document the ball flight as unbiased data"
            " rather than judging yourself."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Smile or take a deep exhale as soon as your"
            " 3-second hold finishes to release tension."
        ),
    },
    "Positive Box Pre-Shot Routine Drill": {
        "equipment": "1 Alignment Rod or Line on Ground",
        "vivid_description": (
            "Step behind the line into the 'Think Box' to calculate wind,"
            " yardage, and shot shape. Step across the line into the 'Play Box'"
            " with 100% commitment and zero swing thoughts."
        ),
        "analogy": (
            "Crossing into the Boxing Ring: Make all decisions outside the"
            " ring; inside the ring is pure execution."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** If a doubt enters your mind inside the Play Box,"
            " back off and step back behind the line."
        ),
    },
    "Target Visual Anchoring Drill": {
        "equipment": "Target Flag / Specific Micro-Target",
        "vivid_description": (
            "Pick a micro-target (e.g., a specific leaf on a tree behind the"
            " flag pin) rather than a general area. Lock eyes onto it for 3"
            " seconds before looking down to swing."
        ),
        "analogy": (
            "Sniper Crosshairs: Aim at a thread, hit a button; aim at a house,"
            " miss the neighborhood."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep the vivid image of that micro-target in your"
            " mind's eye during backswing."
        ),
    },
    "Mantra & Thought Neutralizer Drill": {
        "equipment": "Personal 2-Word Cue",
        "vivid_description": (
            "Repeat a rhythmic two-word cadence (e.g., 'Smooth... Turn...')"
            " quietly during backswing and downswing to crowd out negative"
            " thoughts."
        ),
        "analogy": (
            "Noise-Canceling Headphones: Block out intrusive internal doubt and"
            " fear of failure."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Sync your rhythm so word 1 is backswing start and"
            " word 2 is impact release."
        ),
    },
}

DRILL_COMPLEXITY = {
    "Alignment Stick Gate Drill": "Low",
    "Pause at Top Drill": "Medium",
    "Tee Gate Drill": "Low",
    "Towel Under Armpits Drill": "Low",
    "Coin Strike Low-Point Drill": "Medium",
    "Split-Hands Release Drill": "Medium",
    "Feet-Together Balance Drill": "Low",
    "Wall-Head Posture Drill": "Medium",
    "Impact Bag Compression Drill": "High",
    "Two-Step Pump Lag Drill": "High",
    "Towel Behind Ball Drill": "Low",
    "Lead Foot Weight Anchor Drill": "Low",
    "Brush Turf Chipping Drill": "Low",
    "Coin Lead-Point Pitch Drill": "Medium",
    "Ruler in Glove Wrist Anchor Drill": "Medium",
    "Hinge-and-Hold Chipping Drill": "Medium",
    "Clock System Wedge Drill": "High",
    "Landing Zone Target Towel Drill": "High",
    "Trail-Hand Only Pitch Drill": "Medium",
    "Line in the Sand Drill": "Low",
    "Dollar Bill Sand Extraction Drill": "Medium",
    "Open-Face Sand Splash Drill": "High",
    "Continuous Motion Pendulum Chipping Drill": "Low",
    "Accelerating Through Impact Gate Drill": "Medium",
    "Target-Focused Eyes-Up Chipping Drill": "Medium",
    "Putting Tee Gate Drill": "Low",
    "Chalk Line Straight Target Drill": "Medium",
    "Mirror Alignment Face Drill": "Medium",
    "Trail-Hand Push Putting Drill": "Low",
    "Metal Yardstick Roll Drill": "High",
    "Parallel Rod Putting Channel Drill": "Low",
    "Ladder Distance Lag Drill": "Medium",
    "Fringe-to-Fringe Feel Drill": "Low",
    "Eyes-Closed Distance Perception Drill": "High",
    "Rubber Band Putter Sweet-Spot Drill": "Medium",
    "Two-Tee Putter Gate Drill": "Low",
    "Coin Balance Putter Back Drill": "Medium",
    "Push-Putting No-Backswing Drill": "Medium",
    "Short Back Long Through Stroke Drill": "Low",
    "Coin Balance Motion Stroke Drill": "Low",
    "1-2-3 Box Breathing Reset Drill": "Low",
    "Post-Shot Acceptance Hold Drill": "Low",
    "Positive Box Pre-Shot Routine Drill": "Medium",
    "Target Visual Anchoring Drill": "Low",
    "Mantra & Thought Neutralizer Drill": "Medium",
}

GAME_MODE_DRILL_MAP = {
    "Alignment Stick Gate Drill": "Tee Gate Drill",
    "Pause at Top Drill": "Tee Gate Drill",
    "Towel Under Armpits Drill": "Tee Gate Drill",
    "Coin Strike Low-Point Drill": "Tee Gate Drill",
    "Split-Hands Release Drill": "Tee Gate Drill",
    "Feet-Together Balance Drill": "Tee Gate Drill",
    "Wall-Head Posture Drill": "Tee Gate Drill",
    "Impact Bag Compression Drill": "Tee Gate Drill",
    "Two-Step Pump Lag Drill": "Tee Gate Drill",
    "Towel Behind Ball Drill": "Landing Zone Target Towel Drill",
    "Lead Foot Weight Anchor Drill": "Landing Zone Target Towel Drill",
    "Brush Turf Chipping Drill": "Target-Focused Eyes-Up Chipping Drill",
    "Coin Lead-Point Pitch Drill": "Landing Zone Target Towel Drill",
    "Ruler in Glove Wrist Anchor Drill": (
        "Target-Focused Eyes-Up Chipping Drill"
    ),
    "Hinge-and-Hold Chipping Drill": "Clock System Wedge Drill",
    "Trail-Hand Only Pitch Drill": "Target-Focused Eyes-Up Chipping Drill",
    "Line in the Sand Drill": "Dollar Bill Sand Extraction Drill",
    "Continuous Motion Pendulum Chipping Drill": (
        "Target-Focused Eyes-Up Chipping Drill"
    ),
    "Accelerating Through Impact Gate Drill": "Clock System Wedge Drill",
    "Mirror Alignment Face Drill": "Putting Tee Gate Drill",
    "Trail-Hand Push Putting Drill": "Ladder Distance Lag Drill",
    "Metal Yardstick Roll Drill": "Chalk Line Straight Target Drill",
    "Parallel Rod Putting Channel Drill": "Putting Tee Gate Drill",
    "Fringe-to-Fringe Feel Drill": "Ladder Distance Lag Drill",
    "Rubber Band Putter Sweet-Spot Drill": "Two-Tee Putter Gate Drill",
    "Coin Balance Putter Back Drill": "Putting Tee Gate Drill",
    "Push-Putting No-Backswing Drill": "Ladder Distance Lag Drill",
    "Short Back Long Through Stroke Drill": "Ladder Distance Lag Drill",
    "Coin Balance Motion Stroke Drill": "Ladder Distance Lag Drill",
    "1-2-3 Box Breathing Reset Drill": "Positive Box Pre-Shot Routine Drill",
    "Post-Shot Acceptance Hold Drill": "Positive Box Pre-Shot Routine Drill",
    "Positive Box Pre-Shot Routine Drill": "Target Visual Anchoring Drill",
    "Target Visual Anchoring Drill": "Target Visual Anchoring Drill",
    "Mantra & Thought Neutralizer Drill": "Positive Box Pre-Shot Routine Drill",
}

# -------------------------------------------------------------
# CLOSE THE LOOP: ask about LAST round's drill before starting a new one
# -------------------------------------------------------------
_init_history()
_history_rows = st.session_state["practice_history"]
if (
    _history_rows
    and st.session_state.get("diag_step", 1) == 1
    and _history_rows[-1].get("Drill Completed?", "") == ""
):
    _last = _history_rows[-1]
    with st.container(border=True):
        st.markdown(
            f"##### 🔁 Quick check-in: your last drill was "
            f"**{_last.get('Primary Drill', 'your drill')}**"
        )
        col_fb1, col_fb2, col_fb3 = st.columns([1, 1, 1])
        with col_fb1:
            fb_completed = st.selectbox(
                "Did you do it?",
                ["Not yet", "Yes, a little", "Yes, fully"],
                key="fb_completed",
            )
        with col_fb2:
            fb_effectiveness = st.slider(
                "Did it help? (1-5)", 1, 5, 3, key="fb_effectiveness"
            )
        with col_fb3:
            st.write("")
            st.write("")
            if st.button("Log Feedback", use_container_width=True):
                update_last_session_feedback(fb_completed, fb_effectiveness)
                st.rerun()
        if st.button("Skip for now"):
            update_last_session_feedback("Skipped", "")
            st.rerun()

# -------------------------------------------------------------
# STEP 1: HYBRID STORY + MULTI-CHOICE DIAGNOSTIC
# -------------------------------------------------------------
st.subheader("1. Round Story & Diagnostic Intake")

selected_persona_key = st.selectbox(
    "Choose Your Movie Caddie Persona:",
    options=list(PERSONA_DATABASE.keys()),
    index=0,
)

persona_display_name = selected_persona_key.split(" (")[0]
active_persona = PERSONA_DATABASE[selected_persona_key]

if "diag_step" not in st.session_state:
    st.session_state["diag_step"] = 1

NONE_OPT = "-- Not Specified --"


def format_selector_value(val: str) -> str:
    return (
        "Not specified by user (derive exclusively from round story text)"
        if val == NONE_OPT
        else val
    )


# --- STEP 1A: FREE TEXT STORY & OPTIONAL SELECTORS ---
if st.session_state["diag_step"] == 1:
    st.markdown("### 🗣️ Tell Us How Your Round Went")
    st.caption(
        "Talk naturally about what happened during your round—your misses,"
        " feelings, mental blow-ups, or frustration. The AI Caddie will pinpoint"
        " key themes and ask two targeted follow-up questions."
    )

    user_round_story = st.text_area(
        "Describe your round in your own words:",
        height=120,
        placeholder=(
            "e.g., I played 18 holes today and couldn't hit a fairway with my"
            " driver—everything kept slicing hard into the trees on the right. I"
            " got super frustrated on hole 6 after a bad double bogey and"
            " completely lost my mental focus for the next 4 holes..."
        ),
    )

    st.markdown("##### 🔢 Round Numbers (optional, but this powers the score-ROI analysis)")
    col_n1, col_n2, col_n3 = st.columns(3)
    col_n4, col_n5, col_n6 = st.columns(3)
    with col_n1:
        round_score = st.number_input(
            "Score", min_value=0, max_value=200, value=0, step=1,
            help="Total strokes. Leave at 0 if you'd rather skip this.",
        )
    with col_n2:
        fairways_hit = st.number_input(
            "Fairways Hit", min_value=0, max_value=18, value=0, step=1
        )
    with col_n3:
        gir = st.number_input(
            "GIR", min_value=0, max_value=18, value=0, step=1,
            help="Greens hit in regulation.",
        )
    with col_n4:
        putts = st.number_input(
            "Putts", min_value=0, max_value=60, value=0, step=1,
            help="Interpret with GIR; high putts do not automatically mean poor putting.",
        )
    with col_n5:
        penalty_strokes = st.number_input(
            "Penalty Strokes", min_value=0, max_value=20, value=0, step=1
        )
    with col_n6:
        handicap = st.number_input(
            "Handicap", min_value=0.0, max_value=54.0, value=0.0, step=0.1,
            help="Optional context for handicap-relative benchmarking.",
        )

    with st.expander(
        "⚙️ Optional: Tweak Observable Ball-Flight & Focus Selectors (Default:"
        " None)",
        expanded=False,
    ):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            start_dir = st.selectbox(
                "Start Direction:",
                [
                    NONE_OPT,
                    "Starts Straight at Target",
                    "Pulls Left of Target",
                    "Pushes Right of Target",
                ],
            )
            curvature = st.selectbox(
                "Flight Curvature:",
                [
                    NONE_OPT,
                    "Flies Straight (No curve)",
                    "Curves Softly Right (Fade)",
                    "Curves Sharply Right (Slice)",
                    "Curves Left (Draw / Hook)",
                ],
            )
            club_category = st.selectbox(
                "Main Problem Area:",
                [
                    NONE_OPT,
                    "Driver / Tee Shots",
                    "Mid / Long Irons",
                    "Short Game / Wedges",
                    "Putting Greens",
                    "Mental Game / Focus / Temper",
                ],
            )
        with col_s2:
            divot_loc = st.selectbox(
                "Divot Location:",
                [
                    NONE_OPT,
                    "Clean Contact (Divot after ball)",
                    "Heavy / Fat (Turf 1-2 inches before ball)",
                    "Thin / Skulled (Top of ball)",
                    "Hard Mat / Pure Turf Sweep",
                ],
            )
            impact_feel = st.selectbox(
                "Impact Sound & Feel:",
                [
                    NONE_OPT,
                    "Crisp 'click'",
                    "Dull 'thud' / heavy dirt drag",
                    "Harsh vibration on toe/heel",
                    "Stinging hands / thin strike",
                ],
            )
            miss_freq = st.selectbox(
                "Flaw Frequency:",
                [
                    NONE_OPT,
                    "Driver / Woods Only",
                    "Irons & Wedges Only",
                    "Under Tournament Pressure Only",
                    "Every Club in Bag",
                ],
            )

    if st.button(
        f"Analyze Round Narrative with {persona_display_name}", type="primary"
    ):
        if not user_round_story.strip():
            st.warning(
                "Please type a few words about your round story above so your Caddie"
                " can analyze it!"
            )
        else:
            st.session_state["user_round_story"] = user_round_story
            st.session_state["start_dir"] = start_dir
            st.session_state["curvature"] = curvature
            st.session_state["club_category"] = club_category
            st.session_state["divot_loc"] = divot_loc
            st.session_state["impact_feel"] = impact_feel
            st.session_state["miss_freq"] = miss_freq
            st.session_state["caddie_name"] = persona_display_name
            st.session_state["round_score"] = round_score
            st.session_state["round_fairways_hit"] = fairways_hit
            st.session_state["round_gir"] = gir
            st.session_state["round_putts"] = putts
            st.session_state["round_penalty_strokes"] = penalty_strokes
            st.session_state["round_handicap"] = handicap

            round_numbers_block = f"""
            - Score: {round_score if round_score else 'Not provided'}
            - Fairways Hit: {fairways_hit if fairways_hit else 'Not provided'} (out of ~14 driving holes on a typical 18)
            - Greens in Regulation: {gir if gir else 'Not provided'} (out of 18)
            - Putts: {putts if putts else 'Not provided'}
            - Penalty Strokes: {penalty_strokes if penalty_strokes else 'Not provided'}
            """

            question_prompt = f"""
            {active_persona['system_instruction']}

            The golfer provided this open-ended story about their round:
            "{user_round_story}"

            Optional observable settings (if marked 'Not specified', rely strictly on the story text above):
            - Start Direction: {format_selector_value(start_dir)}
            - Flight Curvature: {format_selector_value(curvature)}
            - Problem Area: {format_selector_value(club_category)}
            - Divot Location: {format_selector_value(divot_loc)}
            - Impact Feel: {format_selector_value(impact_feel)}
            - Consistency: {format_selector_value(miss_freq)}

            Round numbers they logged (may be more reliable than what they choose to talk about):
            {round_numbers_block}

            **Blind-Spot Check (do this BEFORE writing questions):** Players narrate whatever is
            emotionally fresh (e.g. one bad chip), which is not always where they're actually
            losing the most strokes. Compare the round numbers above to the story:
            - Fairways Hit well below ~50% of driving holes → possible off-the-tee leak.
            - Putts at 34+ → possible putting/scoring leak.
            - Penalty Strokes at 2+ → possible course-management/decision leak.
            - GIR well below ~30% → possible approach-game leak.
            If any of these stat-implied leaks is NOT addressed anywhere in the story, you MUST
            spend one of the two follow-up questions probing that specific blind spot directly
            (e.g. asking what typically causes missed fairways) instead of only following the
            narrative. If the numbers and the story already agree on the main issue, or no
            numbers were logged, ask both questions based on the story as normal.

            Based on the above, craft 2 targeted diagnostic decision-tree follow-up questions in persona voice.
            Address physical biomechanics or mental composure/focus issues depending on what they described.
            For EACH question, provide 3 short, concrete multiple-choice options (Option A, Option B, Option C) to clarify their root cause without typing.

            Output strictly raw JSON with no markdown formatting:
            {{
              "question_1": "string (Question 1 — from the story, or from a stat-implied blind spot if one was found)",
              "options_q1": ["Option A string", "Option B string", "Option C string"],
              "question_2": "string (Question 2 addressing secondary mechanic or mental reaction)",
              "options_q2": ["Option A string", "Option B string", "Option C string"]
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

                q_res = None
                for model_name in flash_models:
                    try:
                        model = genai.GenerativeModel(model_name)
                        res = model.generate_content(question_prompt)
                        if res and res.text:
                            q_res = res
                            break
                    except Exception:
                        continue

                if q_res:
                    clean_q_json = (
                        q_res.text.replace("```json", "").replace("```", "").strip()
                    )
                    st.session_state["followup_questions"] = json.loads(clean_q_json)
                    st.session_state["diag_step"] = 2
                    st.rerun()
                else:
                    st.error(
                        "Unable to generate diagnostic questions. Please check your API"
                        " key."
                    )
            except Exception as e:
                st.error(f"Error generating follow-up questions: {e}")

# --- STEP 1B: TARGETED MULTI-CHOICE DECISION TREE ---
elif st.session_state["diag_step"] == 2:
    st.info(
        f"📖 **Your Round Narrative:** \"{st.session_state.get('user_round_story')}\""
    )
    caddie = st.session_state.get("caddie_name", persona_display_name)
    qs = st.session_state.get("followup_questions", {})

    st.markdown(f"### 🗣️ {caddie} asks based on your story:")

    q1_text = qs.get(
        "question_1",
        "When your shot goes off line or a bad hole occurs, how do you react"
        " mentally?",
    )
    q1_opts = qs.get(
        "options_q1",
        [
            "I get angry and rush my next shot",
            "I overthink mechanical swing keys",
            "I stay calm and stick to routine",
        ],
    )

    q2_text = qs.get(
        "question_2",
        "When you try to compensate, what usually happens next?",
    )
    q2_opts = qs.get(
        "options_q2",
        [
            "Contact gets heavier / fatter",
            "Ball goes straight but loses distance",
            "Shot stays exactly the same",
        ],
    )

    st.markdown(f"**1. {q1_text}**")
    ans1_selected = st.radio(
        "Q1 Choice:", options=q1_opts, key="ans1_radio", label_visibility="collapsed"
    )

    st.markdown(f"**2. {q2_text}**")
    ans2_selected = st.radio(
        "Q2 Choice:", options=q2_opts, key="ans2_radio", label_visibility="collapsed"
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button(
            "🔍 Synthesize Root Cause & Mindset Diagnosis", type="primary"
        ):
            _rs = st.session_state.get("round_score")
            _fh = st.session_state.get("round_fairways_hit")
            _gir = st.session_state.get("round_gir")
            _pt = st.session_state.get("round_putts")
            _pen = st.session_state.get("round_penalty_strokes")

            roi_data = calculate_score_roi(
                _rs, _fh, _gir, _pt, _pen,
                st.session_state.get("round_handicap")
            )

            full_round_input = f"""
            User Story: "{st.session_state.get('user_round_story')}"
            Start Direction: {format_selector_value(st.session_state['start_dir'])}
            Flight Curvature: {format_selector_value(st.session_state['curvature'])}
            Problem Area: {format_selector_value(st.session_state['club_category'])}
            Divot / Turf Location: {format_selector_value(st.session_state['divot_loc'])}
            Impact Sound & Feel: {format_selector_value(st.session_state['impact_feel'])}
            Miss Frequency: {format_selector_value(st.session_state['miss_freq'])}
            Decision Tree Q1: {q1_text} -> Selected: {ans1_selected}
            Decision Tree Q2: {q2_text} -> Selected: {ans2_selected}
            Round Numbers: Score={_rs if _rs else 'N/A'}, Fairways Hit={_fh if _fh else 'N/A'} (of ~14),
            GIR={_gir if _gir else 'N/A'} (of 18), Putts={_pt if _pt else 'N/A'}, Penalty Strokes={_pen if _pen else 'N/A'},
            Handicap={st.session_state.get('round_handicap') or 'N/A'}
            Score-ROI Engine: {roi_data['tier']} | {roi_data['score']}/100
            Score-ROI Evidence: {'; '.join(roi_data['reasons']) if roi_data['reasons'] else 'No strong numerical leak detected'}
            """

            system_prompt = f"""
            {active_persona['system_instruction']}

            Act as an expert biomechanical, sports psychology, and strategic golf instructor AI.
            Analyze the user's round narrative, decision tree answers, and round numbers through a
            **Golf Value Chain ROI Lens** — the same "where does the value actually leak" logic used
            in a business value chain, applied to a round of golf. Every fault belongs to exactly one
            of these four sequential stages:

            1. **Off-the-Tee Strategy (Primary Drive):** driver/tee shot accuracy and strategy. If this
               stage is leaking (e.g. low Fairways Hit), everything downstream is played from trouble,
               which makes it structurally the highest-ROI stage to fix even if the player didn't
               mention it.
            2. **Approach Precision (Mid Game):** iron/approach shot accuracy into greens (GIR).
            3. **Scoring/Scrambling (Short Game/Putting):** chipping, pitching, sand, and putting —
               converting positions already gained into a low score.
            4. **Mental Infrastructure (Support Systems):** routine, composure, decision-making, and
               recovery after a bad shot or hole — the system that supports the other three stages.

            **Score-ROI Priority Rule (critical):** NEVER rank a fault merely because it occurs
            earlier in the golf value chain. The old "tee shots always outrank downstream faults"
            rule is intentionally removed. Priority must reflect expected strokes saved per unit of
            practice time, using the actual round evidence first.

            Priority logic:
            1. **CRITICAL — Direct Score Leak:** actual penalty strokes, repeated OB/lost-ball/water
               events, or clearly documented mistakes that immediately added strokes.
            2. **HIGH — Major Scoring Opportunity:** large approach/GIR deficits, repeated costly
               approach misses, or repeated short-game failures that prevent conversion.
            3. **MEDIUM — Repeatable Scoring Leakage:** repeated 3-putts/poor distance control,
               short-game inconsistency, or tee-shot misses that demonstrably create difficult lies
               or penalties.
            4. **LOW — Technique Polish:** small FIR differences, isolated contact errors, or
               mechanical issues without evidence of repeated scoring damage.
            5. **MENTAL / DECISION-MAKING:** elevate only when the story shows the issue caused
               repeated scoring damage across multiple holes. Frustration alone is not enough.

            **Putting context rule:** Putts per round must be interpreted with GIR and short-game
            context. High putts are a flag to investigate, not proof that putting is the highest
            ROI fault. Three-putt frequency or shot-level putting data is stronger evidence.

            **Blind-Spot Directive (critical):** Players tend to talk about whatever is emotionally
            freshest. If the numerical evidence reveals a materially larger score leak that the story
            does not mention, surface it as `diagnostic_blind_spot` and let it outrank the narrative.
            Do NOT manufacture a hidden fault when the available round numbers cannot establish one.
            Use the supplied Score-ROI Engine as a starting signal, then reconcile it with the story.

            **Drill Assignment Directive:**
               - Select `recommended_primary_drill` strictly for the stage/issue that will yield the
                 **MAXIMUM score reduction** per the Value Chain + numbers analysis above — not
                 necessarily the fault the player talked about most.
               - Select `recommended_secondary_drill` for the second highest ROI issue.

            Map faults to the most effective drills from this EXACT list of 45 drills:
            - FULL SWING: 'Alignment Stick Gate Drill', 'Pause at Top Drill', 'Tee Gate Drill', 'Towel Under Armpits Drill', 'Coin Strike Low-Point Drill', 'Split-Hands Release Drill', 'Feet-Together Balance Drill', 'Wall-Head Posture Drill', 'Impact Bag Compression Drill', 'Two-Step Pump Lag Drill'
            - SHORT GAME: 'Towel Behind Ball Drill', 'Lead Foot Weight Anchor Drill', 'Brush Turf Chipping Drill', 'Coin Lead-Point Pitch Drill', 'Ruler in Glove Wrist Anchor Drill', 'Hinge-and-Hold Chipping Drill', 'Clock System Wedge Drill', 'Landing Zone Target Towel Drill', 'Trail-Hand Only Pitch Drill', 'Line in the Sand Drill', 'Dollar Bill Sand Extraction Drill', 'Open-Face Sand Splash Drill', 'Continuous Motion Pendulum Chipping Drill', 'Accelerating Through Impact Gate Drill', 'Target-Focused Eyes-Up Chipping Drill'
            - PUTTING: 'Putting Tee Gate Drill', 'Chalk Line Straight Target Drill', 'Mirror Alignment Face Drill', 'Trail-Hand Push Putting Drill', 'Metal Yardstick Roll Drill', 'Parallel Rod Putting Channel Drill', 'Ladder Distance Lag Drill', 'Fringe-to-Fringe Feel Drill', 'Eyes-Closed Distance Perception Drill', 'Rubber Band Putter Sweet-Spot Drill', 'Two-Tee Putter Gate Drill', 'Coin Balance Putter Back Drill', 'Push-Putting No-Backswing Drill', 'Short Back Long Through Stroke Drill', 'Coin Balance Motion Stroke Drill'
            - MENTAL GAME: '1-2-3 Box Breathing Reset Drill', 'Post-Shot Acceptance Hold Drill', 'Positive Box Pre-Shot Routine Drill', 'Target Visual Anchoring Drill', 'Mantra & Thought Neutralizer Drill'

            Output strictly raw JSON with no markdown formatting:
            {{
              "diagnosis_category": "Strategic ROI & Value Chain Diagnosis",
              "primary_miss": "string (title of highest ROI root cause)",
              "primary_miss_stage": "string — exactly one of: 'Off-the-Tee Strategy (Primary Drive)', 'Approach Precision (Mid Game)', 'Scoring/Scrambling (Short Game/Putting)', 'Mental Infrastructure (Support Systems)'",
              "primary_miss_persona": "string (1 short, witty sentence calling out primary flaw in character)",
              "primary_cause_breakdown": "string (2-3 sentences explaining biomechanical/psychological cause and why fixing this yields the highest stroke reduction)",
              "secondary_miss": "string or null",
              "secondary_miss_stage": "string or null — one of the same four Value Chain stage names",
              "secondary_miss_persona": "string or null",
              "secondary_cause_breakdown": "string or null (2-3 sentences explaining secondary cause and its relative stroke impact)",
              "expanded_caddie_intro": "string (3-4 robust sentences in persona referencing their story and strategic ROI fix)",
              "caddie_drill_pep_talk": "string (2-3 sentences in persona giving encouraging range advice)",
              "value_chain_analysis": {{
                "off_the_tee": "string (1 sentence assessment of driving/tee-shot performance, grounded in the numbers if provided)",
                "approach": "string (1 sentence assessment of mid-iron/approach performance)",
                "scoring_scrambling": "string (1 sentence assessment of short game & putting performance)",
                "mental_infrastructure": "string (1 sentence assessment of routine/composure/decision-making)",
                "primary_leak_stage": "string — exactly one of the four stage names above, the stage actually costing the most strokes",
                "leak_rationale": "string (1-2 sentences explaining why this stage outranks the others, citing the round numbers where available)"
              }},
              "diagnostic_blind_spot": "string or null — a stat-implied leak the player's story did not mention or explain",
              "roi_priority": "CRITICAL | HIGH | MEDIUM | LOW",
              "roi_score": 0.0,
              "roi_evidence": "string — specific round evidence supporting the priority",
              "confidence_score": 0.95,
              "recommended_primary_drill": "string",
              "recommended_secondary_drill": "string or null",
              "drill_rationale": "string (1-2 sentences explicitly detailing the 'Bang for Your Buck' logic—why fixing these specific faults delivers the maximum score reduction)"
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
                            f"{system_prompt}\n\nRound Context:\n{full_round_input}"
                        )
                        if res and res.text:
                            response = res
                            break
                    except Exception:
                        continue

                if response is None:
                    st.error("No active Gemini Flash model found.")
                    st.stop()

                clean_json = (
                    response.text.replace("```json", "").replace("```", "").strip()
                )
                diag_data = json.loads(clean_json)
                st.session_state["diagnosis"] = diag_data

                # --- SAVE TO PERSISTENT CSV SPREADSHEET ---
                vc_data = diag_data.get("value_chain_analysis", {})
                roi_note = vc_data.get("leak_rationale") or vc_data.get(
                    "primary_leak_stage", ""
                )
                if diag_data.get("diagnostic_blind_spot"):
                    roi_note = (
                        f"[Blind spot] {diag_data['diagnostic_blind_spot']}"
                    )

                def _zero_to_blank(n):
                    return n if n else ""

                save_session_to_csv(
                    primary_miss=diag_data.get("primary_miss", "N/A"),
                    primary_drill=diag_data.get("recommended_primary_drill", "N/A"),
                    secondary_miss=diag_data.get("secondary_miss", ""),
                    roi_opportunity=roi_note,
                    score=_zero_to_blank(st.session_state.get("round_score")),
                    fairways_hit=_zero_to_blank(
                        st.session_state.get("round_fairways_hit")
                    ),
                    gir=_zero_to_blank(st.session_state.get("round_gir")),
                    putts=_zero_to_blank(st.session_state.get("round_putts")),
                    penalty_strokes=_zero_to_blank(
                        st.session_state.get("round_penalty_strokes")
                    ),
                    problem_area=st.session_state.get("club_category", ""),
                    miss_freq=st.session_state.get("miss_freq", ""),
                    confidence=diag_data.get("confidence_score", ""),
                    handicap=st.session_state.get("round_handicap"),
                    roi_priority=diag_data.get("roi_priority", roi_data.get("tier", "")),
                    roi_score=diag_data.get("roi_score", roi_data.get("score", "")),
                )

                st.session_state["diag_step"] = 3
                st.rerun()
            except Exception as e:
                st.error(f"Error executing diagnosis: {e}")

    with col_btn2:
        if st.button("↺ Start Over"):
            st.session_state["diag_step"] = 1
            st.rerun()

# --- STEP 1C: DIAGNOSTIC & SWOT DISPLAY ---
if st.session_state.get("diag_step") == 3 and "diagnosis" in st.session_state:
    diag = st.session_state["diagnosis"]
    caddie = st.session_state.get("caddie_name", persona_display_name)

    intro_text = diag.get("expanded_caddie_intro", "")
    st.success(f"**{caddie}:** \"{intro_text}\"")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🎯 Primary Macro-Fault (Highest ROI Target)**")
        p_persona_msg = diag.get(
            "primary_miss_persona", diag.get("primary_miss", "Not detected")
        )
        st.warning(f"\"{p_persona_msg}\"")
        p_plain = diag.get("primary_miss")
        if p_plain:
            st.markdown(f"*({p_plain})*")

        st.write(f"**Primary Drill:** `{diag.get('recommended_primary_drill')}`")
        p_causes = diag.get("primary_cause_breakdown")
        if p_causes:
            st.caption(f"**Root Cause & ROI Impact:** {p_causes}")
        p_stage = diag.get("primary_miss_stage")
        if p_stage:
            st.caption(f"📍 **Value Chain Stage:** {p_stage}")

    with col2:
        st.markdown("**⚠️ Secondary Fault Callout**")
        sec_miss = diag.get("secondary_miss")
        if sec_miss:
            s_persona_msg = diag.get("secondary_miss_persona", sec_miss)
            st.info(f"\"{s_persona_msg}\"")
            st.markdown(f"*({sec_miss})*")

            sec_drill = diag.get("recommended_secondary_drill")
            st.write(f"**Secondary Drill:** `{sec_drill if sec_drill else 'N/A'}`")
            s_causes = diag.get("secondary_cause_breakdown")
            if s_causes:
                st.caption(f"**Root Cause & Relative Impact:** {s_causes}")
            s_stage = diag.get("secondary_miss_stage")
            if s_stage:
                st.caption(f"📍 **Value Chain Stage:** {s_stage}")
        else:
            st.info(
                '"No major secondary fault detected. Fix your primary macro-fault to'
                ' unlock your game!"'
            )
            st.write("**Secondary Drill:** `N/A`")

    # Value Chain Leak Breakdown (replaces the old generic SWOT summary)
    vc = diag.get("value_chain_analysis")
    if vc:
        st.markdown("---")
        st.markdown("### 🧭 Value Chain Leak Breakdown")
        st.caption(
            "Where your strokes actually leak, stage by stage — not just what you"
            " happened to talk about most."
        )

        leak_stage = vc.get("primary_leak_stage", "")
        stage_order = [
            ("Off-the-Tee Strategy (Primary Drive)", "off_the_tee", "🏌️"),
            ("Approach Precision (Mid Game)", "approach", "🎯"),
            ("Scoring/Scrambling (Short Game/Putting)", "scoring_scrambling", "⛳"),
            ("Mental Infrastructure (Support Systems)", "mental_infrastructure", "🧠"),
        ]

        vc_row1 = st.columns(2)
        vc_row2 = st.columns(2)
        vc_slots = list(vc_row1) + list(vc_row2)

        for slot, (stage_name, key, icon) in zip(vc_slots, stage_order):
            with slot:
                text = vc.get(key, "N/A")
                if stage_name == leak_stage:
                    st.error(f"{icon} **{stage_name}**\n\n🔴 **#1 LEAK** — {text}")
                else:
                    st.info(f"{icon} **{stage_name}**\n\n{text}")

        leak_rationale = vc.get("leak_rationale")
        if leak_rationale:
            st.caption(f"**Why this stage wins the ROI ranking:** {leak_rationale}")

    blind_spot = diag.get("diagnostic_blind_spot")
    if blind_spot:
        st.warning(
            f"🔍 **Blind Spot Flagged:** {blind_spot}\n\n"
            "This didn't come up in your round story, but your logged numbers"
            " pointed to it — it's already factored into the practice plan below."
        )

    st.markdown("---")
    if st.button("🔄 Describe Another Round"):
        st.session_state["diag_step"] = 1
        st.rerun()

# -------------------------------------------------------------
# STEP 2: PRACTICE ASSET ALLOCATION & CONSTRAINTS
# -------------------------------------------------------------
st.markdown("---")
st.subheader("2. Practice Resource Constraints (Balls & Time)")

col_input_a, col_input_b = st.columns(2)
with col_input_a:
    total_balls = st.number_input(
        "Total Balls Available:", min_value=10, max_value=300, value=100, step=10
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
        "game_pct": game_pct,
        "practice_mode": practice_mode,
    }
    st.success(
        "Resource constraints locked in! Practice execution plan generated"
        " below."
    )

if "confirmed_resources" in st.session_state:
    res_data = st.session_state["confirmed_resources"]
    st.write("**Confirmed Resource Distribution:**")
    st.progress(
        res_data["grind_pct"],
        text=(
            f"Grind Mode: {int(res_data['grind_pct']*100)}% | Game Mode:"
            f" {int(res_data['game_pct']*100)}%"
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
# STEP 3: ADAPTIVE PRACTICE EXECUTION & SETUP GUIDE
# -------------------------------------------------------------
st.markdown("---")
st.subheader("3. Adaptive Practice Execution & Setup Guide")

if "diagnosis" in st.session_state and "confirmed_resources" in st.session_state:
    diag = st.session_state["diagnosis"]
    res = st.session_state["confirmed_resources"]
    caddie = st.session_state.get("caddie_name", persona_display_name)

    p_drill = diag.get("recommended_primary_drill", "Alignment Stick Gate Drill")
    s_drill = diag.get("recommended_secondary_drill")
    p_miss = diag.get("primary_miss", "your main swing fault")
    s_miss = diag.get("secondary_miss")
    rationale = diag.get("drill_rationale")
    pep_talk = diag.get("caddie_drill_pep_talk")

    c_balls = res["total_balls"]
    c_time = res["total_time"]
    p_mode = res.get("practice_mode", "Combination / Hybrid (AI Balanced)")

    is_pure_game = p_mode == "Pure Game Mode (100% Target Pressure)"
    is_hybrid = p_mode == "Combination / Hybrid (AI Balanced)"

    if is_pure_game:
        st.info(
            "🎮 **Pure Game Mode Active:** All drills converted into interactive"
            " target-pressure games."
        )
        p_drill = GAME_MODE_DRILL_MAP.get(p_drill, p_drill)
        if s_drill:
            s_drill = GAME_MODE_DRILL_MAP.get(s_drill, s_drill)

    p_complexity = DRILL_COMPLEXITY.get(p_drill, "Medium")
    is_high_budget = c_balls >= 60 and c_time >= 45

    active_drills = [p_drill]

    high_complexity_added = None
    if is_high_budget and not is_pure_game:
        if p_complexity != "High":
            if p_drill in DRILL_SCHEMATICS:
                if "Putting" in p_drill or "Putter" in p_drill:
                    high_complexity_added = "Metal Yardstick Roll Drill"
                elif any(
                    word in p_drill
                    for word in ["Wedge", "Chip", "Sand", "Pitch", "Towel", "Anchor"]
                ):
                    high_complexity_added = "Clock System Wedge Drill"
                elif any(
                    word in p_drill
                    for word in [
                        "Breathing",
                        "Acceptance",
                        "Routine",
                        "Anchoring",
                        "Mantra",
                    ]
                ):
                    high_complexity_added = "Positive Box Pre-Shot Routine Drill"
                else:
                    high_complexity_added = "Impact Bag Compression Drill"

            if high_complexity_added and high_complexity_added not in active_drills:
                active_drills.append(high_complexity_added)

    if c_balls >= 40 and c_time >= 30 and s_drill and s_drill not in active_drills:
        active_drills.append(s_drill)

    if is_hybrid:
        if len(active_drills) == 1 and p_drill in GAME_MODE_DRILL_MAP:
            game_pair = GAME_MODE_DRILL_MAP[p_drill]
            if game_pair != p_drill:
                active_drills.append(game_pair)

        for i in range(1, len(active_drills)):
            active_drills[i] = GAME_MODE_DRILL_MAP.get(
                active_drills[i], active_drills[i]
            )

    if (c_balls < 40 or c_time < 30) and p_complexity == "High":
        st.warning(
            f"⚠️ **Low Resource Alert:** `{p_drill}` is High Complexity. Focus on"
            f" basic feel keys with your limited budget ({c_balls} balls / {c_time}"
            " mins)."
        )

    if pep_talk:
        st.success(f"🗣️ **{caddie}'s Practice Strategy:** \"{pep_talk}\"")

    summary_line = (
        "💡 **Targeted Prescription:** Circuit optimized across"
        f" {len(active_drills)} focus areas."
    )
    if rationale:
        st.info(f"{summary_line}\n\n**Bang for Your Buck Rationale:** {rationale}")
    else:
        st.info(summary_line)

    g_balls = res["grind_balls"]
    g_time = res["grind_time"]
    num_drills = len(active_drills)

    alloc_balls = res["total_balls"] if is_pure_game else g_balls
    alloc_time = res["total_time"] if is_pure_game else g_time

    for idx, d_name in enumerate(active_drills):
        schematic = DRILL_SCHEMATICS.get(
            d_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"]
        )

        if num_drills == 1:
            weight = 1.0
        elif num_drills == 2:
            weight = 0.65 if idx == 0 else 0.35
        else:
            weight = 0.60 if idx == 0 else (0.40 / (num_drills - 1))

        balls_per_drill = int(alloc_balls * weight)
        time_per_drill = int(alloc_time * weight)

        if is_pure_game or (is_hybrid and idx > 0):
            label = (
                "🎮 Interactive Target Game (Addressing:"
                f" {p_miss if idx == 0 else (s_miss if s_miss else p_miss)})"
            )
        elif d_name == p_drill:
            label = f"Primary Highest ROI Drill (Addressing: {p_miss})"
        elif d_name == high_complexity_added:
            label = "Advanced Mechanics / Routine Overhaul"
        else:
            label = (
                "Secondary Focus Drill (Addressing:"
                f" {s_miss if s_miss else 'Performance Polish'})"
            )

        st.markdown(f"### 🎯 Drill #{idx+1}: **{d_name}**")
        st.markdown(f"🔥 **{label}**")
        st.caption(
            f"⚡ `{balls_per_drill} Balls` | `{time_per_drill} Mins` |"
            f" `@~{res['sec_per_ball']}s/ball`"
        )

        st.markdown("**🛠️ Range Equipment Needed**")
        equip_items = re.split(r",\s*(?![^()]*\))", schematic["equipment"])
        render_indented_ul(equip_items)

        st.markdown("**📖 Setup Description Mechanics**")
        render_indented_html(schematic["vivid_description"])

        st.markdown("**🧠 Mental Analogy**")
        render_indented_html(schematic["analogy"])

        st.info(schematic["pro_tip"])

        if idx < len(active_drills) - 1:
            st.markdown("---")

    gm_balls = res["game_balls"]
    gm_time = res["game_time"]
    if gm_balls > 0 and gm_time > 0 and not is_pure_game:
        st.markdown("---")
        st.markdown(
            f"### ⛳ Drill #{len(active_drills)+1}: **Target Course Pressure"
            " Simulation**"
        )
        st.markdown(
            "🔥 **Final Phase: On-Course Pressure Transfer & Routine Integration**"
        )
        st.caption(
            f"⚡ `{gm_balls} Balls` | `{gm_time} Mins` |"
            f" `@~{res['sec_per_ball']}s/ball`"
        )

        st.markdown("**🛠️ Range Equipment Needed**")
        render_indented_ul([
            "Full Golf Bag (All Clubs)",
            "Laser Rangefinder or Target Flags",
            "Pre-shot Routine Line",
        ])

        st.markdown("**📖 Setup Description Mechanics**")
        render_indented_html(
            "Simulate real course conditions. Alternate target flags and clubs for"
            " every single ball. Step away from the mat and execute your complete"
            " pre-shot routine before every swing."
        )

        st.markdown("**🧠 Mental Analogy**")
        render_indented_html(
            "Sunday Major Final Hole: Treat every single ball like a high-stakes"
            " tournament stroke on the course."
        )

        st.info(
            "🏆 **Pro Tip:** Never hit two balls in a row with the same club or to"
            " the same target during this pressure phase."
        )

    st.markdown("---")
    st.markdown("### 📥 Take Your Plan to the Range")
    export_card_text = build_export_card(
        diag, res, active_drills, DRILL_SCHEMATICS, caddie
    )
    st.download_button(
        label="Download Printable Range Practice Card (.txt)",
        data=export_card_text,
        file_name="birdie_buddy_practice_plan.txt",
        mime="text/plain",
    )

elif "diagnosis" in st.session_state:
    st.warning(
        "👈 Please click **'✅ Confirm Selection & Generate Execution Plan'** in"
        " Section 2 to generate your plan."
    )
else:
    st.caption(
        "Run a full-round diagnosis in Section 1 and confirm resources in"
        " Section 2 to get started!"
    )
