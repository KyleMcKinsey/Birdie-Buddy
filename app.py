from datetime import datetime
import base64
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
import google.generativeai as genai
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

st.set_page_config(
    page_title="Birdie Buddy", page_icon="⛳", layout="centered"
)

CSV_FILE = "birdie_buddy_practice_history.csv"


HISTORY_COLUMNS = [
    "Timestamp",
    "Score",
    "Fairways Hit",
    "GIR",
    "Putts",
    "Penalty Strokes",
    "OB/Lost Balls",
    "3-Putts",
    "Failed Up-and-Downs",
    "Scrambling Opportunities",
    "Problem Area",
    "Primary Macro-Fault",
    "Primary Value Chain Stage",
    "Course Mgmt Subtype",
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
    "Estimated Excess Strokes",
    "Holes Played",
    "Fairway Opportunities",
    "GIR Opportunities",
    "Observed Direct Score Cost",
    "Handicap-Relative Peer Gap",
    "Decision Quality",
    "Mechanical Evidence Level",
    "Practice Environment",
    "Available Equipment",
    "Practice Allocation",
    "Baseline KPI (10)",
    "Post KPI (10)",
    "Objective Gain",
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
    return pd.DataFrame(rows, columns=HISTORY_COLUMNS).fillna("N/A")


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
    ob_lost_balls=None,
    three_putts=None,
    failed_up_downs=None,
    scrambling_opportunities=None,
    problem_area="",
    primary_stage="",
    course_management_subtype="",
    miss_freq="",
    confidence=None,
    handicap=None,
    roi_priority="",
    roi_score=None,
    estimated_excess_strokes="",
    holes_played=None,
    fairway_opportunities=None,
    gir_opportunities=None,
    observed_direct_score_cost="",
    handicap_relative_peer_gap="",
    decision_quality="",
    mechanical_evidence_level="",
    practice_environment="",
    available_equipment="",
    practice_allocation="",
    baseline_kpi="",
    post_kpi="",
    objective_gain="",
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
        "OB/Lost Balls": ob_lost_balls if ob_lost_balls not in (None, "") else "N/A",
        "3-Putts": three_putts if three_putts not in (None, "") else "N/A",
        "Failed Up-and-Downs": failed_up_downs if failed_up_downs not in (None, "") else "N/A",
        "Scrambling Opportunities": scrambling_opportunities if scrambling_opportunities not in (None, "") else "N/A",
        "Problem Area": _blank_if_none(problem_area),
        "Primary Macro-Fault": primary_miss if primary_miss else "N/A",
        "Primary Value Chain Stage": primary_stage if primary_stage else "N/A",
        "Course Mgmt Subtype": course_management_subtype if course_management_subtype else "N/A",
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
        "Estimated Excess Strokes": estimated_excess_strokes if estimated_excess_strokes not in (None, "") else "N/A",
        "Holes Played": holes_played if holes_played not in (None, "") else "N/A",
        "Fairway Opportunities": fairway_opportunities if fairway_opportunities not in (None, "") else "N/A",
        "GIR Opportunities": gir_opportunities if gir_opportunities not in (None, "") else "N/A",
        "Observed Direct Score Cost": observed_direct_score_cost if observed_direct_score_cost not in (None, "") else "N/A",
        "Handicap-Relative Peer Gap": handicap_relative_peer_gap if handicap_relative_peer_gap not in (None, "") else "N/A",
        "Decision Quality": decision_quality if decision_quality not in (None, "") else "N/A",
        "Mechanical Evidence Level": mechanical_evidence_level if mechanical_evidence_level not in (None, "") else "N/A",
        "Practice Environment": practice_environment if practice_environment not in (None, "") else "N/A",
        "Available Equipment": available_equipment if available_equipment not in (None, "") else "N/A",
        "Practice Allocation": practice_allocation if practice_allocation not in (None, "") else "N/A",
        "Baseline KPI (10)": baseline_kpi if baseline_kpi not in (None, "") else "N/A",
        "Post KPI (10)": post_kpi if post_kpi not in (None, "") else "N/A",
        "Objective Gain": objective_gain if objective_gain not in (None, "") else "N/A",
    }

    # 1. Save to memory first - this is what the sidebar reads.
    st.session_state["practice_history"].append(row)

    # 2. Try to also write the CSV file. If the disk is read-only
    #    (common on hosted Streamlit), we quietly skip it instead of crashing.
    try:
        pd.DataFrame(
            st.session_state["practice_history"], columns=HISTORY_COLUMNS
        ).to_csv(CSV_FILE, index=False)
    except Exception as file_error:
        st.session_state["history_file_warning"] = str(file_error)


def update_last_session_feedback(
    completed_label,
    effectiveness,
    baseline_kpi=None,
    post_kpi=None,
    practice_environment="",
    available_equipment="",
    practice_allocation="",
    actual_primary_drill="",
):
    """Close the loop on the latest prescribed practice session."""
    _init_history()
    rows = st.session_state["practice_history"]
    if not rows:
        return

    row = rows[-1]
    row["Drill Completed?"] = completed_label
    row["Fix Effectiveness (1-5)"] = effectiveness

    if baseline_kpi not in (None, ""):
        row["Baseline KPI (10)"] = int(baseline_kpi)
    if post_kpi not in (None, ""):
        row["Post KPI (10)"] = int(post_kpi)
    if baseline_kpi not in (None, "") and post_kpi not in (None, ""):
        row["Objective Gain"] = int(post_kpi) - int(baseline_kpi)

    if practice_environment:
        row["Practice Environment"] = practice_environment
    if available_equipment:
        row["Available Equipment"] = available_equipment
    if practice_allocation:
        row["Practice Allocation"] = practice_allocation
    if actual_primary_drill:
        row["Primary Drill"] = actual_primary_drill

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


def _drill_category(drill_name: str) -> str:
    """Return a coaching category used to add drill-specific instruction depth."""
    full_swing = {
        "Alignment Stick Gate Drill", "Pause at Top Drill", "Tee Gate Drill",
        "Towel Under Armpits Drill", "Coin Strike Low-Point Drill",
        "Split-Hands Release Drill", "Feet-Together Balance Drill",
        "Wall-Head Posture Drill", "Impact Bag Compression Drill",
        "Two-Step Pump Lag Drill",
    }
    bunker = {
        "Line in the Sand Drill", "Dollar Bill Sand Extraction Drill",
        "Open-Face Sand Splash Drill",
    }
    short_game = {
        "Towel Behind Ball Drill", "Lead Foot Weight Anchor Drill",
        "Brush Turf Chipping Drill", "Coin Lead-Point Pitch Drill",
        "Ruler in Glove Wrist Anchor Drill", "Hinge-and-Hold Chipping Drill",
        "Clock System Wedge Drill", "Landing Zone Target Towel Drill",
        "Trail-Hand Only Pitch Drill", "Continuous Motion Pendulum Chipping Drill",
        "Accelerating Through Impact Gate Drill", "Target-Focused Eyes-Up Chipping Drill",
    }
    putting = {
        "Putting Tee Gate Drill", "Chalk Line Straight Target Drill",
        "Mirror Alignment Face Drill", "Trail-Hand Push Putting Drill",
        "Metal Yardstick Roll Drill", "Parallel Rod Putting Channel Drill",
        "Ladder Distance Lag Drill", "Fringe-to-Fringe Feel Drill",
        "Eyes-Closed Distance Perception Drill", "Rubber Band Putter Sweet-Spot Drill",
        "Two-Tee Putter Gate Drill", "Coin Balance Putter Back Drill",
        "Push-Putting No-Backswing Drill", "Short Back Long Through Stroke Drill",
        "Coin Balance Motion Stroke Drill",
    }
    mental = {
        "1-2-3 Box Breathing Reset Drill", "Post-Shot Acceptance Hold Drill",
        "Positive Box Pre-Shot Routine Drill", "Target Visual Anchoring Drill",
        "Mantra & Thought Neutralizer Drill",
    }
    if drill_name in full_swing:
        return "full_swing"
    if drill_name in bunker:
        return "bunker"
    if drill_name in short_game:
        return "short_game"
    if drill_name in putting:
        return "putting"
    if drill_name in mental:
        return "mental"
    return "general"


def _format_stroke_estimate(value, include_word=True):
    """Display heuristic stroke estimates as ranges/rounded values, not false precision."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v <= 0:
        return "0 strokes" if include_word else "0"
    if v < 0.5:
        return "<0.5 stroke" if include_word else "<0.5"
    lower = int(v * 2) / 2.0
    upper = (int(v * 2 + 0.999999)) / 2.0
    if lower <= 0:
        lower = 0.5
    if abs(upper - lower) < 1e-9:
        amount = f"{lower:g}"
    else:
        amount = f"{lower:g}–{upper:g}"
    if not include_word:
        return f"≈{amount}"
    suffix = "stroke" if amount == "1" else "strokes"
    return f"≈{amount} {suffix}"


PRACTICE_AREA_OPTIONS = [
    "Driving Range / Full-Swing Bay",
    "Short-Game / Chipping Area",
    "Putting Green",
    "Practice Bunker",
    "Indoor Net / Simulator",
    "Home / Indoor Putting Mat",
    "On-Course / Practice Hole",
]

EQUIPMENT_OPTIONS = [
    "Alignment Sticks",
    "Tees",
    "Towel",
    "Coins / Ball Marker",
    "Putting Mirror",
    "Yardstick / Straightedge",
    "Chalk / String Line",
    "Impact Bag",
    "Ruler / Flat Wrist Aid",
    "Rubber Bands",
    "Rangefinder",
]

CATEGORY_DRILL_CANDIDATES = {
    "full_swing": [
        "Alignment Stick Gate Drill", "Pause at Top Drill", "Tee Gate Drill",
        "Towel Under Armpits Drill", "Coin Strike Low-Point Drill",
        "Split-Hands Release Drill", "Feet-Together Balance Drill",
        "Wall-Head Posture Drill", "Impact Bag Compression Drill",
        "Two-Step Pump Lag Drill",
    ],
    "short_game": [
        "Towel Behind Ball Drill", "Lead Foot Weight Anchor Drill",
        "Brush Turf Chipping Drill", "Coin Lead-Point Pitch Drill",
        "Ruler in Glove Wrist Anchor Drill", "Hinge-and-Hold Chipping Drill",
        "Clock System Wedge Drill", "Landing Zone Target Towel Drill",
        "Trail-Hand Only Pitch Drill", "Continuous Motion Pendulum Chipping Drill",
        "Accelerating Through Impact Gate Drill", "Target-Focused Eyes-Up Chipping Drill",
    ],
    "bunker": [
        "Line in the Sand Drill", "Dollar Bill Sand Extraction Drill",
        "Open-Face Sand Splash Drill",
    ],
    "putting": [
        "Putting Tee Gate Drill", "Chalk Line Straight Target Drill",
        "Mirror Alignment Face Drill", "Trail-Hand Push Putting Drill",
        "Metal Yardstick Roll Drill", "Parallel Rod Putting Channel Drill",
        "Ladder Distance Lag Drill", "Fringe-to-Fringe Feel Drill",
        "Eyes-Closed Distance Perception Drill", "Rubber Band Putter Sweet-Spot Drill",
        "Two-Tee Putter Gate Drill", "Coin Balance Putter Back Drill",
        "Push-Putting No-Backswing Drill", "Short Back Long Through Stroke Drill",
        "Coin Balance Motion Stroke Drill",
    ],
    "mental": [
        "1-2-3 Box Breathing Reset Drill", "Post-Shot Acceptance Hold Drill",
        "Positive Box Pre-Shot Routine Drill", "Target Visual Anchoring Drill",
        "Mantra & Thought Neutralizer Drill",
    ],
}


def _required_equipment_for_drill(drill_name):
    requirements = {
        "Alignment Stick Gate Drill": {"Alignment Sticks"},
        "Parallel Rod Putting Channel Drill": {"Alignment Sticks"},
        "Tee Gate Drill": {"Tees"},
        "Putting Tee Gate Drill": {"Tees"},
        "Two-Tee Putter Gate Drill": {"Tees"},
        "Towel Under Armpits Drill": {"Towel"},
        "Towel Behind Ball Drill": {"Towel"},
        "Landing Zone Target Towel Drill": {"Towel"},
        "Coin Strike Low-Point Drill": {"Coins / Ball Marker"},
        "Coin Lead-Point Pitch Drill": {"Coins / Ball Marker"},
        "Coin Balance Putter Back Drill": {"Coins / Ball Marker"},
        "Coin Balance Motion Stroke Drill": {"Coins / Ball Marker"},
        "Mirror Alignment Face Drill": {"Putting Mirror"},
        "Metal Yardstick Roll Drill": {"Yardstick / Straightedge"},
        "Chalk Line Straight Target Drill": {"Chalk / String Line"},
        "Impact Bag Compression Drill": {"Impact Bag"},
        "Ruler in Glove Wrist Anchor Drill": {"Ruler / Flat Wrist Aid"},
        "Rubber Band Putter Sweet-Spot Drill": {"Rubber Bands"},
    }
    return requirements.get(drill_name, set())


def _drill_supported(drill_name, practice_areas, equipment):
    """Return whether the drill is realistically executable in today's environment."""
    areas = set(practice_areas or [])
    gear = set(equipment or [])
    category = _drill_category(drill_name)
    if category == "full_swing":
        area_ok = bool(areas & {
            "Driving Range / Full-Swing Bay", "Indoor Net / Simulator",
            "On-Course / Practice Hole",
        })
    elif category == "putting":
        area_ok = bool(areas & {
            "Putting Green", "Home / Indoor Putting Mat", "On-Course / Practice Hole",
        })
    elif category == "short_game":
        area_ok = bool(areas & {
            "Short-Game / Chipping Area", "On-Course / Practice Hole",
        })
    elif category == "bunker":
        area_ok = bool(areas & {"Practice Bunker", "On-Course / Practice Hole"})
    else:
        area_ok = bool(areas)
    return area_ok and _required_equipment_for_drill(drill_name).issubset(gear)


def _resolve_drill_for_environment(drill_name, practice_areas, equipment):
    """Preserve the same coaching category when substituting for unavailable gear/facilities."""
    if not drill_name:
        return None, None
    if _drill_supported(drill_name, practice_areas, equipment):
        return drill_name, None
    category = _drill_category(drill_name)
    for candidate in CATEGORY_DRILL_CANDIDATES.get(category, []):
        if candidate != drill_name and _drill_supported(candidate, practice_areas, equipment):
            return candidate, f"{drill_name} → {candidate}"
    return None, f"{drill_name} is not executable with the selected practice area/equipment."


def _adaptive_hybrid_split(diag):
    """Return an evidence/history-aware controlled-work vs transfer split."""
    stage = str((diag or {}).get("primary_miss_stage") or "")
    base_by_stage = {
        "Off-the-Tee Performance (Primary Drive)": 0.60,
        "Approach Precision (Mid Game)": 0.65,
        "Scoring/Scrambling (Short Game/Putting)": 0.55,
        "Course Management / Strategic Decision-Making": 0.35,
        "Mental Infrastructure (Support Systems)": 0.35,
    }
    grind = base_by_stage.get(stage, 0.55)
    reasons = [f"Base split reflects the primary stage ({_short_progress_stage(stage) or 'general performance'})."]

    mech = str((diag or {}).get("mechanical_evidence_level") or "")
    if mech == "Supported by golfer observations":
        grind += 0.08
        reasons.append("Supported mechanical evidence favors more controlled skill acquisition.")
    elif mech == "Hypothesis to test":
        grind += 0.03
        reasons.append("A mechanical hypothesis gets a modest controlled-rep bias while it is tested.")
    elif mech == "Performance pattern only":
        grind -= 0.05
        reasons.append("A performance pattern without proven mechanics favors more transfer/feedback work.")

    decision_quality = str((diag or {}).get("decision_quality") or "")
    if stage == "Course Management / Strategic Decision-Making" and decision_quality in {
        "Poor decision / reasonable execution", "Both contributed"
    }:
        grind -= 0.08
        reasons.append("Decision-quality problems are trained more effectively through scenario/transfer reps than blocked mechanics.")

    df = load_history_df()
    if not df.empty and stage:
        same_stage = df[df["Primary Value Chain Stage"].astype(str) == stage].tail(3)
        if not same_stage.empty:
            last = same_stage.iloc[-1]
            completed = str(last.get("Drill Completed?", "")).lower()
            try:
                effectiveness = float(last.get("Fix Effectiveness (1-5)", ""))
            except Exception:
                effectiveness = None
            try:
                objective_gain = float(last.get("Objective Gain", ""))
            except Exception:
                objective_gain = None
            actually_completed = ("partial" in completed) or ("fully" in completed) or completed.startswith("yes")
            if actually_completed and objective_gain is not None:
                if objective_gain >= 2:
                    grind -= 0.15
                    reasons.append("The prior objective test improved by at least 2/10, so more time shifts to transfer/pressure instead of more blocked repetition.")
                elif objective_gain <= 0:
                    grind += 0.05
                    reasons.append("The prior objective test did not improve, so the new intervention gets slightly more controlled learning time.")
            elif actually_completed and effectiveness is not None and effectiveness >= 4:
                grind -= 0.15
                reasons.append("The prior drill was completed and rated effective, so more time shifts to transfer/pressure instead of repeating blocked work.")
            elif actually_completed and effectiveness is not None and effectiveness <= 2:
                grind += 0.05
                reasons.append("The prior completed drill rated poorly, so the new intervention gets a little more controlled learning time.")
            elif not actually_completed:
                reasons.append("Prior work was not completed, so Birdie Buddy does not treat the intervention as failed.")

    grind = max(0.30, min(0.75, grind))
    return round(grind, 2), " ".join(reasons)


def _practice_drill_weights(diag, active_drills):
    """Allocate controlled-work time by the relative importance of the selected drills."""
    n = len(active_drills)
    if n <= 1:
        return [1.0] if n == 1 else []
    secondary_priority = str((diag or {}).get("secondary_roi_priority") or "").upper()
    if secondary_priority in {"CRITICAL", "HIGH"}:
        primary = 0.60
    elif secondary_priority == "MEDIUM":
        primary = 0.70
    else:
        primary = 0.80
    try:
        conf = float((diag or {}).get("confidence_score"))
    except Exception:
        conf = 1.0
    if conf < 0.65:
        primary = min(primary, 0.65)
    if n == 2:
        return [primary, 1.0 - primary]
    remaining = 1.0 - primary
    return [primary] + [remaining / (n - 1)] * (n - 1)


def _allocate_integer(total, weights):
    if not weights:
        return []
    raw = [total * w for w in weights]
    base = [int(x) for x in raw]
    remainder = int(total) - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:max(0, remainder)]:
        base[i] += 1
    return base


def get_drill_kpi(drill_name):
    """Objective 10-rep pre/post test tied to the skill the drill is meant to train."""
    lag_putting = {"Ladder Distance Lag Drill", "Fringe-to-Fringe Feel Drill", "Eyes-Closed Distance Perception Drill", "Trail-Hand Push Putting Drill", "Short Back Long Through Stroke Drill", "Push-Putting No-Backswing Drill"}
    start_line_putting = {"Putting Tee Gate Drill", "Chalk Line Straight Target Drill", "Mirror Alignment Face Drill", "Metal Yardstick Roll Drill", "Parallel Rod Putting Channel Drill", "Two-Tee Putter Gate Drill"}
    strike_putting = {"Rubber Band Putter Sweet-Spot Drill", "Coin Balance Putter Back Drill", "Coin Balance Motion Stroke Drill"}
    distance_short_game = {"Clock System Wedge Drill", "Landing Zone Target Towel Drill", "Target-Focused Eyes-Up Chipping Drill", "Trail-Hand Only Pitch Drill"}
    contact_short_game = {"Towel Behind Ball Drill", "Lead Foot Weight Anchor Drill", "Brush Turf Chipping Drill", "Coin Lead-Point Pitch Drill", "Ruler in Glove Wrist Anchor Drill", "Hinge-and-Hold Chipping Drill", "Continuous Motion Pendulum Chipping Drill", "Accelerating Through Impact Gate Drill"}
    if drill_name in lag_putting:
        return {"name": "Lag-putt proximity", "test": "Hit 10 putts from roughly 30–40 feet to one target.", "success": "A success finishes inside a 3-foot radius without racing more than 3 feet past.", "target": 7}
    if drill_name in start_line_putting:
        return {"name": "Start-line control", "test": "Hit 10 straight putts from 6–8 feet through the drill's intended start-line gate/reference.", "success": "A success starts through the gate/on the reference line with centered contact.", "target": 8}
    if drill_name in strike_putting:
        return {"name": "Centered putter contact", "test": "Hit 10 putts from 6–10 feet using the strike constraint.", "success": "A success contacts the intended center of the face and starts on the chosen line.", "target": 8}
    if drill_name in distance_short_game:
        return {"name": "Landing-zone control", "test": "Hit 10 chips/pitches to one landing zone, then let the ball release normally.", "success": "A success lands inside a roughly 3-foot landing-zone circle and produces the intended trajectory.", "target": 7}
    if drill_name in contact_short_game:
        return {"name": "Short-game contact", "test": "Hit 10 chips/pitches from the same lie using the drill constraint.", "success": "A success produces the intended turf/ball contact and a predictable launch—judge strike before final proximity.", "target": 7}
    if _drill_category(drill_name) == "bunker":
        return {"name": "Bunker entry & escape", "test": "Hit 10 bunker shots from one consistent lie to a defined landing zone.", "success": "A success enters the sand at the intended spot, exits the bunker, and finishes in a playable target zone.", "target": 7}
    if _drill_category(drill_name) == "full_swing":
        return {"name": "Playable full-swing reps", "test": "Hit 10 balls to one clearly defined target corridor using the drill constraint.", "success": "A success satisfies the drill checkpoint, produces functional contact, and finishes in the chosen playable corridor.", "target": 7}
    if _drill_category(drill_name) == "mental":
        return {"name": "Process completion", "test": "Hit 10 one-ball reps with a full reset and pre-shot process before each shot.", "success": "A success completes the intended routine/decision cue and commits before the swing, regardless of whether the result is perfect.", "target": 8}
    return {"name": "Quality reps", "test": "Complete 10 scored reps using the drill exactly as written.", "success": "A success meets the drill's stated SUCCESS checkpoint without changing the setup to make the rep easier.", "target": 7}


DRILL_PURPOSES = {
    "Alignment Stick Gate Drill": "Build a repeatable target line, body alignment, and club delivery so setup errors do not masquerade as swing faults.",
    "Pause at Top Drill": "Improve transition sequence and tempo by separating the completed backswing from the start of the downswing.",
    "Tee Gate Drill": "Train center-face contact and a more predictable clubhead path through the impact zone.",
    "Towel Under Armpits Drill": "Improve arm-and-torso connection so the swing is driven by coordinated rotation instead of independent arm action.",
    "Coin Strike Low-Point Drill": "Move the low point of the iron swing forward so contact occurs ball-first, then turf.",
    "Split-Hands Release Drill": "Teach the clubface to release and square through impact without a late hand flip or blocked face.",
    "Feet-Together Balance Drill": "Improve balance, centered rotation, and contact by removing the ability to rely on excessive lateral motion.",
    "Wall-Head Posture Drill": "Reduce early extension and loss of posture by giving the body a physical reference during the downswing.",
    "Impact Bag Compression Drill": "Rehearse a stable impact position with forward pressure, shaft lean, and a supported lead wrist.",
    "Two-Step Pump Lag Drill": "Improve transition patience and sequencing while reducing an early cast from the top.",
    "Towel Behind Ball Drill": "Train a forward low point on chips so the club contacts the ball before the ground behind it.",
    "Lead Foot Weight Anchor Drill": "Stabilize the low point in chipping by keeping pressure forward throughout the motion.",
    "Brush Turf Chipping Drill": "Develop consistent turf interaction and a predictable bottom of the chipping arc.",
    "Coin Lead-Point Pitch Drill": "Teach the wedge to use its bounce and slide through the turf instead of digging with the leading edge.",
    "Ruler in Glove Wrist Anchor Drill": "Reduce excessive lead-wrist breakdown and scooping through short-game impact.",
    "Hinge-and-Hold Chipping Drill": "Build a simple, predictable chip motion with a stable wrist structure through impact.",
    "Clock System Wedge Drill": "Create repeatable carry distances by pairing specific swing lengths with each wedge.",
    "Landing Zone Target Towel Drill": "Shift short-game focus from the flag to the exact landing point that controls rollout.",
    "Trail-Hand Only Pitch Drill": "Improve awareness of clubhead weight, soft acceleration, and proper use of wedge bounce.",
    "Line in the Sand Drill": "Make bunker entry point predictable so the club enters the sand in the same place on every shot.",
    "Dollar Bill Sand Extraction Drill": "Control both sand-entry and sand-exit points to create a consistent splash pattern around the ball.",
    "Open-Face Sand Splash Drill": "Build confidence using an open clubface and the bounce to produce a high, soft bunker shot.",
    "Continuous Motion Pendulum Chipping Drill": "Remove stop-start hand action and develop a smooth, uninterrupted chipping rhythm.",
    "Accelerating Through Impact Gate Drill": "Train positive acceleration through the strike so chips are not decelerated or stabbed at impact.",
    "Target-Focused Eyes-Up Chipping Drill": "Improve external focus and distance feel by shifting attention from mechanics to the landing target.",
    "Putting Tee Gate Drill": "Train centered putter-face contact and consistent delivery through a narrow impact gate.",
    "Chalk Line Straight Target Drill": "Improve start-line control by giving the eyes and putter a precise straight-line reference.",
    "Mirror Alignment Face Drill": "Calibrate eye position, shoulder alignment, and putter-face aim at address.",
    "Trail-Hand Push Putting Drill": "Develop a smoother release and better pace awareness by simplifying the stroke to the trail hand.",
    "Metal Yardstick Roll Drill": "Test and train precise start direction by keeping the ball rolling along a very narrow straight path.",
    "Parallel Rod Putting Channel Drill": "Improve putter-path consistency while keeping setup and stroke direction organized around the target line.",
    "Ladder Distance Lag Drill": "Build long-putt speed control by learning to stop balls at progressively different distances.",
    "Fringe-to-Fringe Feel Drill": "Develop adaptable pace control without becoming overly dependent on a single target distance.",
    "Eyes-Closed Distance Perception Drill": "Strengthen internal speed awareness by predicting distance before seeing the result.",
    "Rubber Band Putter Sweet-Spot Drill": "Make off-center contact obvious and train the center of the putter face.",
    "Two-Tee Putter Gate Drill": "Build a repeatable impact path and face delivery through a constrained gate.",
    "Coin Balance Putter Back Drill": "Smooth the transition and reduce jerky acceleration by requiring a stable putter during the stroke.",
    "Push-Putting No-Backswing Drill": "Teach the sensation of accelerating the putter through the ball rather than hitting with a long, hesitant backswing.",
    "Short Back Long Through Stroke Drill": "Reduce deceleration by creating a committed through-stroke that is longer than the backswing.",
    "Coin Balance Motion Stroke Drill": "Keep the putter moving level through impact instead of lifting, digging, or changing height abruptly.",
    "1-2-3 Box Breathing Reset Drill": "Lower physical arousal and create a repeatable reset routine after frustration, pressure, or a bad hole.",
    "Post-Shot Acceptance Hold Drill": "Shorten emotional recovery time by turning the immediate post-shot reaction into neutral observation.",
    "Positive Box Pre-Shot Routine Drill": "Separate decision-making from execution so the golfer commits fully before stepping over the ball.",
    "Target Visual Anchoring Drill": "Improve commitment and start-line intention by locking attention onto a specific external target.",
    "Mantra & Thought Neutralizer Drill": "Reduce last-second mechanical thoughts by replacing them with one simple rhythmic process cue.",
}


CATEGORY_INSTRUCTION_ADDONS = {
    "full_swing": {
        "SETUP": "Before the first ball, choose one clear target and make 2–3 slow rehearsals so the training aid is positioned correctly. Start with a mid-iron unless the drill specifically calls for another club. Use a comfortable, athletic setup and verify that the aid changes the intended movement—not your normal ball position just to make the drill easier.",
        "EXECUTION": "Treat each ball as a separate rep. Begin at roughly 50–60% speed, then build toward 70–80% only after the movement is repeatable. Step away briefly between reps, rehearse the feel once, then hit the next ball. Work in small blocks of 3–5 balls rather than raking balls continuously.",
        "SUCCESS": "Score the movement before judging the ball flight. A good rep should satisfy the physical checkpoint of the drill and produce centered or improving contact. As a practical benchmark, look for about 7 of 10 reps meeting the drill goal before adding speed or changing clubs.",
        "AVOID": "Do not manipulate the hands or change your normal setup simply to avoid touching the training aid. If you miss the constraint three reps in a row, reduce speed, shorten the swing, and rebuild the motion rather than forcing a full-speed correction.",
    },
    "short_game": {
        "SETUP": "Choose a specific landing spot and a realistic finish zone before beginning. Start from one predictable lie so you can learn the motion, then vary the lie only after contact becomes stable. Place several balls nearby, but reset your stance and target picture before every rep instead of hitting them rapid-fire.",
        "EXECUTION": "Make 1–2 rehearsals beside the ball, then reproduce the same motion with the ball present. Keep the first set at a controlled pace and hold the finish long enough to check balance, face orientation, and where the club brushed the turf. Once the strike is stable, vary carry distance or landing spot without changing the core technique.",
        "SUCCESS": "Judge both contact and outcome. A successful rep should produce the intended strike first, then land near the chosen spot with predictable rollout. Try to achieve the drill checkpoint on roughly 7 of 10 balls before making the lie, target, or trajectory more difficult.",
        "AVOID": "Do not judge the drill only by whether the ball finishes close to the hole—a mishit can occasionally finish well. If contact deteriorates, return to a shorter motion and the original lie rather than adding hand action or extra speed to rescue the shot.",
    },
    "bunker": {
        "SETUP": "Use a practice bunker with enough room to swing safely and rake the area before starting so each lie is comparable. Pick a landing zone on the green, draw or identify the intended sand-entry point, and establish your normal bunker setup before placing the ball into the exercise.",
        "EXECUTION": "Begin with several no-ball rehearsals so you can see exactly where the club enters and exits the sand. Then add balls while keeping the same entry intention and committed acceleration. Re-rake the hitting area every few shots so changing sand conditions do not hide the pattern you are trying to learn.",
        "SUCCESS": "The first success measure is a repeatable splash pattern, not proximity to the hole. When the club enters the sand in the intended location and the ball exits on a predictable trajectory for most reps, begin scoring how often the ball finishes inside a chosen circle around the target.",
        "AVOID": "Do not slow the club because you are afraid of hitting the ball too far. Also avoid changing several variables at once—face angle, stance, entry point, and speed. If the ball repeatedly stays in the bunker, return to no-ball splash rehearsals before continuing.",
    },
    "putting": {
        "SETUP": "Use a relatively flat section of green first unless the drill is specifically about break. Pick one precise start line, clean the putter face, and use the same ball model for the set. Make sure gates, rods, coins, or other aids are square to the intended line before judging the stroke.",
        "EXECUTION": "Use a full pre-putt routine even on short training putts: read, aim, settle, and stroke. Hit in blocks of 5 rather than continuously. After each putt, identify whether the miss came from start direction, strike location, or speed before making an adjustment.",
        "SUCCESS": "Track a measurable outcome such as gate clears, putts starting on line, center-face strikes, or balls finishing inside a distance window. Aim for at least 8 of 10 successful reps on a basic version before narrowing the gate, increasing distance, or adding break.",
        "AVOID": "Do not steer the putter just to pass the training aid. If the motion becomes tense, widen the constraint or shorten the putt. Avoid changing both aim and stroke at the same time; confirm the setup first, then evaluate the movement.",
    },
    "mental": {
        "SETUP": "Define exactly when the routine begins and ends before practicing it. Use the same physical cue each time—such as stepping behind the ball, crossing a line, taking a breath, or fixing your eyes on the target—so the mental skill becomes tied to an observable behavior rather than a vague intention.",
        "EXECUTION": "Practice the routine deliberately before adding pressure. Complete several dry repetitions, then use it before actual shots. Score whether you completed the routine exactly as intended, regardless of where the ball finished. The goal is to make the behavior automatic enough to survive frustration and score pressure.",
        "SUCCESS": "A successful rep means you followed the process and returned attention to the present shot. Look for shorter recovery time, fewer last-second changes, clearer decisions, and more committed swings. Track completion percentage rather than judging the routine only by score.",
        "AVOID": "Do not turn the mental drill into another technical checklist. Keep the cue short and repeatable. If you catch yourself adding extra thoughts, restart the routine from its first step rather than forcing the shot while uncertain.",
    },
    "general": {
        "SETUP": "Prepare the equipment and target before the first rep, then make a few slow rehearsals so you understand exactly what the drill is asking you to change.",
        "EXECUTION": "Start at low speed, complete one deliberate rep at a time, and reset between attempts. Build speed or difficulty only after the movement is repeatable.",
        "SUCCESS": "Use the stated drill checkpoint as the score. Look for a consistent pattern across several reps rather than one perfect result.",
        "AVOID": "If the drill becomes confusing or contact worsens repeatedly, simplify the task and rebuild it instead of adding more compensations.",
    },
}


CATEGORY_PROGRESSION = {
    "full_swing": "Progression: 3 slow rehearsals → 8–12 controlled shots at 60–75% → 5 normal-routine transfer shots with the training aid removed or ignored. Only increase speed when the movement survives the previous stage.",
    "short_game": "Progression: establish contact from one lie → hit 10–15 balls to one landing zone → finish with 5 random targets or lies so the skill transfers to the course.",
    "bunker": "Progression: 5 no-ball splash rehearsals → 8–12 balls from one lie → 5 different landing targets or bunker lies while keeping the same entry-point concept.",
    "putting": "Progression: calibrate the aid on a straight putt → complete 10 scored reps → increase distance or add break → finish with a short pressure set where a miss resets the count.",
    "mental": "Progression: 5 dry repetitions → 10 range shots using the routine → 5 simulated on-course shots with a consequence or score attached. Judge process completion first, result second.",
    "general": "Progression: rehearse slowly → complete a scored block of controlled reps → finish with several normal shots without relying on the training aid.",
}


def render_instruction_steps(content: str, drill_name: str = "", margin_left: int = 24):
    """Render detailed SETUP / EXECUTION / SUCCESS / AVOID coaching blocks."""
    pattern = r"(SETUP|EXECUTION|SUCCESS|AVOID):\s*"
    matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))

    if not matches:
        render_indented_html(content, margin_left=margin_left)
        return

    category = _drill_category(drill_name)
    addons = CATEGORY_INSTRUCTION_ADDONS.get(category, CATEGORY_INSTRUCTION_ADDONS["general"])
    icons = {"SETUP": "1️⃣", "EXECUTION": "2️⃣", "SUCCESS": "3️⃣", "AVOID": "⚠️"}
    titles = {
        "SETUP": "SETUP — Build the drill correctly",
        "EXECUTION": "EXECUTION — Run each rep deliberately",
        "SUCCESS": "SUCCESS — Know what a good rep looks like",
        "AVOID": "AVOID — Common ways the drill gets cheated",
    }

    blocks = []
    for idx, match in enumerate(matches):
        label = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        extra = addons.get(label, "")
        blocks.append(
            "<div style='margin-bottom:18px; padding-bottom:16px; "
            "border-bottom:1px solid rgba(128,128,128,0.20);'>"
            f"<div style='font-weight:700; margin-bottom:6px;'>{icons[label]} {titles[label]}</div>"
            f"<div style='line-height:1.68;'>{body}</div>"
            f"<div style='line-height:1.62; margin-top:8px; color:#aeb4bf;'>"
            f"<strong>Coach detail:</strong> {extra}</div>"
            "</div>"
        )

    st.markdown(
        f"<div style='margin-left:{margin_left}px; margin-top:6px; margin-bottom:10px;'>"
        f"{''.join(blocks)}</div>",
        unsafe_allow_html=True,
    )


def format_instruction_steps_for_export(content: str, drill_name: str = "") -> str:
    """Expand the structured drill instructions in the plain-text export."""
    pattern = r"(SETUP|EXECUTION|SUCCESS|AVOID):\s*"
    matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
    if not matches:
        return content.strip()

    category = _drill_category(drill_name)
    addons = CATEGORY_INSTRUCTION_ADDONS.get(category, CATEGORY_INSTRUCTION_ADDONS["general"])
    out = []
    for idx, match in enumerate(matches):
        label = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        out.append(f"{label}: {body}\n  Coach detail: {addons.get(label, '')}")
    return "\n\n".join(out)


def render_indented_ul(items: list, margin_left: int = 24):
    list_items = "".join(
        [f"<li>{item.strip()}</li>" for item in items if item.strip()]
    )
    st.markdown(
        f"<ul style='margin-left: {margin_left}px; margin-top: 4px;"
        f" margin-bottom: 12px;'>{list_items}</ul>",
        unsafe_allow_html=True,
    )


def render_compact_metric(label, value, subtext=None, delta=None, good_when_lower=False):
    """Render a restrained metric that fits the app's card-based visual hierarchy."""
    value_text = str(value)
    subtext_html = ""
    if subtext not in (None, ""):
        subtext_html = (
            "<div style='font-size:0.76rem; color:#8b919d; margin-top:3px;"
            " line-height:1.25;'>"
            f"{subtext}</div>"
        )

    delta_html = ""
    if delta is not None:
        try:
            d = float(delta)
            if d == 0:
                delta_color = "#8b919d"
            else:
                improved = d < 0 if good_when_lower else d > 0
                delta_color = "#22a06b" if improved else "#d65a5a"
            delta_text = f"{d:+.0f} vs prior"
        except Exception:
            delta_color = "#8b919d"
            delta_text = str(delta)

        delta_html = (
            f"<div style='font-size:0.76rem; color:{delta_color}; margin-top:3px;"
            f" line-height:1.25;'>{delta_text}</div>"
        )

    st.markdown(
        "<div style='padding:2px 0 6px 0; min-height:64px;'>"
        "<div style='font-size:0.72rem; color:#8b919d; margin-bottom:3px;"
        " letter-spacing:0.01em; line-height:1.2;'>"
        f"{label}</div>"
        "<div style='font-size:1.42rem; font-weight:650; line-height:1.12;"
        " letter-spacing:-0.02em; overflow-wrap:anywhere;'>"
        f"{value_text}</div>"
        f"{delta_html}{subtext_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def _short_progress_stage(stage):
    """Convert the full Value Chain stage name into a clean dashboard label."""
    mapping = {
        "Off-the-Tee Performance (Primary Drive)": "Off-the-Tee",
        "Approach Precision (Mid Game)": "Approach",
        "Scoring/Scrambling (Short Game/Putting)": "Scoring / Scrambling",
        "Course Management / Strategic Decision-Making": "Course Management",
        "Mental Infrastructure (Support Systems)": "Mental Game",
    }
    return mapping.get(str(stage or "").strip(), str(stage or "").strip())


def _neutral_progress_opportunity(row):
    """Build a concise, non-persona progress label from stage + drill evidence."""
    stage = str(row.get("Primary Value Chain Stage", "") or "").strip()
    subtype = str(row.get("Course Mgmt Subtype", "") or "").strip()
    drill = str(row.get("Primary Drill", "") or "").strip()
    raw_title = str(row.get("Primary Macro-Fault", "") or "").strip()

    invalid = {"", "N/A", "None", "null"}
    short_stage = _short_progress_stage(stage)

    if stage == "Course Management / Strategic Decision-Making":
        if subtype not in invalid:
            return f"Course Management — {subtype}"
        return "Course Management — Decision Quality"

    putting_distance = {
        "Ladder Distance Lag Drill",
        "Fringe-to-Fringe Feel Drill",
        "Eyes-Closed Distance Perception Drill",
        "Short Back Long Through Stroke Drill",
    }
    putting_start_line = {
        "Putting Tee Gate Drill",
        "Chalk Line Straight Target Drill",
        "Mirror Alignment Face Drill",
        "Metal Yardstick Roll Drill",
        "Parallel Rod Putting Channel Drill",
        "Two-Tee Putter Gate Drill",
        "Trail-Hand Push Putting Drill",
    }
    putting_strike = {
        "Rubber Band Putter Sweet-Spot Drill",
        "Coin Balance Putter Back Drill",
        "Push-Putting No-Backswing Drill",
        "Coin Balance Motion Stroke Drill",
    }
    short_game_distance = {
        "Clock System Wedge Drill",
        "Landing Zone Target Towel Drill",
        "Target-Focused Eyes-Up Chipping Drill",
        "Trail-Hand Only Pitch Drill",
    }
    short_game_contact = {
        "Towel Behind Ball Drill",
        "Lead Foot Weight Anchor Drill",
        "Brush Turf Chipping Drill",
        "Coin Lead-Point Pitch Drill",
        "Ruler in Glove Wrist Anchor Drill",
        "Hinge-and-Hold Chipping Drill",
        "Continuous Motion Pendulum Chipping Drill",
        "Accelerating Through Impact Gate Drill",
    }
    bunker = {
        "Line in the Sand Drill",
        "Dollar Bill Sand Extraction Drill",
        "Open-Face Sand Splash Drill",
    }
    swing_direction = {
        "Alignment Stick Gate Drill",
        "Tee Gate Drill",
        "Split-Hands Release Drill",
    }
    swing_contact = {
        "Coin Strike Low-Point Drill",
        "Impact Bag Compression Drill",
    }
    swing_sequence = {
        "Pause at Top Drill",
        "Towel Under Armpits Drill",
        "Two-Step Pump Lag Drill",
    }
    swing_balance = {
        "Feet-Together Balance Drill",
        "Wall-Head Posture Drill",
    }

    if drill in putting_distance:
        return "Putting — Distance Control"
    if drill in putting_start_line:
        return "Putting — Start Line & Face Control"
    if drill in putting_strike:
        return "Putting — Strike & Stroke Control"
    if drill in short_game_distance:
        return "Short Game — Distance & Landing Control"
    if drill in short_game_contact:
        return "Short Game — Contact & Low Point"
    if drill in bunker:
        return "Short Game — Bunker Contact"

    swing_prefix = "Approach" if stage == "Approach Precision (Mid Game)" else "Off-the-Tee"
    if drill in swing_direction:
        return f"{swing_prefix} — Direction & Face Control"
    if drill in swing_contact:
        return f"{swing_prefix} — Contact & Low Point"
    if drill in swing_sequence:
        return f"{swing_prefix} — Sequencing & Tempo"
    if drill in swing_balance:
        return f"{swing_prefix} — Balance & Posture"

    if drill == "Positive Box Pre-Shot Routine Drill":
        return "Mental Game — Decision & Pre-Shot Routine"
    if drill == "Target Visual Anchoring Drill":
        return "Mental Game — Target Commitment"
    if drill in {
        "1-2-3 Box Breathing Reset Drill",
        "Post-Shot Acceptance Hold Drill",
        "Mantra & Thought Neutralizer Drill",
    }:
        return "Mental Game — Composure & Reset"

    # Newer diagnoses are explicitly prompted to use a plain golf-language title.
    # Prefer it when it is already concise; otherwise fall back to the stage name.
    if raw_title not in invalid and len(raw_title) <= 48:
        return raw_title
    return short_stage or "Scoring Opportunity"


def render_progress_trends(df_history):
    """Render historical progress after the current round/practice workflow."""
    if df_history.empty:
        return

    rows = df_history.to_dict("records")
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None

    latest_label = _neutral_progress_opportunity(latest)
    previous_label = _neutral_progress_opportunity(previous) if previous else None

    scores = pd.to_numeric(df_history["Score"], errors="coerce").dropna()
    effectiveness = pd.to_numeric(
        df_history["Fix Effectiveness (1-5)"], errors="coerce"
    ).dropna()

    recent_rows = rows[-5:]
    recent_labels = [
        _neutral_progress_opportunity(row)
        for row in recent_rows
        if _neutral_progress_opportunity(row) not in ("", "N/A", "Scoring Opportunity")
    ]
    if recent_labels:
        recent_counts = pd.Series(recent_labels).value_counts()
        common_label = recent_counts.index[0]
        common_count = int(recent_counts.iloc[0])
        common_subtext = f"{common_count} of last {len(recent_labels)} diagnosed rounds"
    else:
        common_label = "Not enough data"
        common_subtext = "Keep logging rounds to reveal patterns"

    if previous_label:
        focus_tag = "🔁 Recurring focus" if latest_label == previous_label else "🆕 New focus"
    else:
        focus_tag = "First diagnosed focus"

    with st.container(border=True):
        st.markdown("### 📈 Progress & Trends")
        st.caption(
            "Review how your scoring priorities and practice results are changing over time."
        )

        m1, m2, m3 = st.columns(3)
        with m1:
            render_compact_metric("Rounds Logged", len(rows))
        with m2:
            if len(scores) >= 2:
                delta = scores.iloc[-1] - scores.iloc[-2]
                render_compact_metric(
                    "Latest Score",
                    f"{int(scores.iloc[-1])}",
                    delta=delta,
                    good_when_lower=True,
                )
            elif len(scores) == 1:
                render_compact_metric("Latest Score", f"{int(scores.iloc[-1])}")
            else:
                render_compact_metric("Latest Score", "N/A")
        with m3:
            if not effectiveness.empty:
                render_compact_metric(
                    "Avg Practice Effectiveness",
                    f"{effectiveness.mean():.1f}/5",
                    subtext=f"{len(effectiveness)} logged session(s)",
                )
            else:
                render_compact_metric(
                    "Avg Practice Effectiveness",
                    "—",
                    subtext="Log practice feedback to build this trend",
                )

        focus_col, common_col = st.columns(2)
        with focus_col:
            st.markdown(
                "<div style='font-size:0.72rem; color:#8b919d; margin-bottom:4px;'>"
                "Current Primary Opportunity</div>"
                f"<div style='font-size:0.95rem; font-weight:650; line-height:1.3;'>"
                f"{latest_label}</div>"
                f"<div style='font-size:0.78rem; color:#8b919d; margin-top:4px;'>"
                f"{focus_tag}</div>",
                unsafe_allow_html=True,
            )

        with common_col:
            st.markdown(
                "<div style='font-size:0.72rem; color:#8b919d; margin-bottom:4px;'>"
                "Most Common Opportunity — Recent Rounds</div>"
                f"<div style='font-size:0.95rem; font-weight:650; line-height:1.3;'>"
                f"{common_label}</div>"
                f"<div style='font-size:0.78rem; color:#8b919d; margin-top:4px;'>"
                f"{common_subtext}</div>",
                unsafe_allow_html=True,
            )

        with st.expander("View score & practice trends", expanded=False):
            if len(scores) >= 2:
                st.caption("Score trend — lower is better")
                st.line_chart(scores.reset_index(drop=True))
            else:
                st.caption("Log at least 2 scored rounds to see a score trend.")

            if len(effectiveness) >= 2:
                st.caption("Practice effectiveness trend — 1 to 5")
                st.line_chart(effectiveness.reset_index(drop=True))
            elif len(effectiveness) == 1:
                st.caption(
                    f"Practice effectiveness: {effectiveness.iloc[-1]:.0f}/5. "
                    "Log another session to start a trend."
                )
            else:
                st.caption("No practice-effectiveness feedback logged yet.")

            objective_gain = pd.to_numeric(
                df_history.get("Objective Gain", pd.Series(dtype=float)), errors="coerce"
            ).dropna()
            if len(objective_gain) >= 2:
                st.caption("Objective practice-test gain — post-test minus pre-test (out of 10)")
                st.line_chart(objective_gain.reset_index(drop=True))
            elif len(objective_gain) == 1:
                st.caption(f"Latest objective practice-test gain: {objective_gain.iloc[-1]:+.0f}/10.")

        # Full history log lives with Progress & Trends instead of in the sidebar.
        with st.expander("👁️ View Color-Coded Practice Log", expanded=False):
            def highlight_progress_cols(val):
                if val == "N/A" or val in (None, ""):
                    return "color: #888888; font-style: italic;"
                return "background-color: #1e3a8a22; font-weight: bold;"

            highlight_targets = [
                col for col in [
                    "Primary Macro-Fault",
                    "Primary Value Chain Stage",
                    "Primary Drill",
                ]
                if col in df_history.columns
            ]

            if highlight_targets:
                styled_history = df_history.style.map(
                    highlight_progress_cols,
                    subset=highlight_targets,
                )
            else:
                styled_history = df_history.style

            st.dataframe(
                styled_history,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Timestamp": st.column_config.TextColumn("Date / Time"),
                    "Score": st.column_config.TextColumn("Score"),
                    "Fairways Hit": st.column_config.TextColumn("FIR"),
                    "GIR": st.column_config.TextColumn("GIR"),
                    "Putts": st.column_config.TextColumn("Putts"),
                    "Penalty Strokes": st.column_config.TextColumn("Penalties"),
                    "OB/Lost Balls": st.column_config.TextColumn("OB / Lost"),
                    "3-Putts": st.column_config.TextColumn("3-Putts"),
                    "Failed Up-and-Downs": st.column_config.TextColumn("Failed U&Ds"),
                    "Scrambling Opportunities": st.column_config.TextColumn("Scramble Opps."),
                    "Problem Area": st.column_config.TextColumn("Problem Area"),
                    "Primary Macro-Fault": st.column_config.TextColumn(
                        "Primary Opportunity"
                    ),
                    "Primary Value Chain Stage": st.column_config.TextColumn(
                        "Value Chain Stage"
                    ),
                    "Course Mgmt Subtype": st.column_config.TextColumn(
                        "Strategy Subtype"
                    ),
                    "Secondary Fault": st.column_config.TextColumn(
                        "Secondary Opportunity"
                    ),
                    "Miss Frequency": st.column_config.TextColumn("Miss Frequency"),
                    "Primary Drill": st.column_config.TextColumn("Primary Drill"),
                    "ROI Opportunity": st.column_config.TextColumn("ROI Fix"),
                    "AI Confidence": st.column_config.TextColumn("AI Confidence"),
                    "Drill Completed?": st.column_config.TextColumn("Practice Completed"),
                    "Fix Effectiveness (1-5)": st.column_config.TextColumn(
                        "Effectiveness (1-5)"
                    ),
                    "Handicap": st.column_config.TextColumn("Handicap"),
                    "ROI Priority": st.column_config.TextColumn("Practice Priority"),
                    "ROI Score": st.column_config.TextColumn("Practice Priority Index"),
                    "Estimated Excess Strokes": st.column_config.TextColumn("Peer Gap (legacy)"),
                    "Holes Played": st.column_config.TextColumn("Holes"),
                    "Fairway Opportunities": st.column_config.TextColumn("FW Opps"),
                    "GIR Opportunities": st.column_config.TextColumn("GIR Opps"),
                    "Observed Direct Score Cost": st.column_config.TextColumn("Direct Cost"),
                    "Handicap-Relative Peer Gap": st.column_config.TextColumn("Peer Gap"),
                    "Decision Quality": st.column_config.TextColumn("Decision Quality"),
                    "Mechanical Evidence Level": st.column_config.TextColumn("Mechanical Evidence"),
                    "Practice Environment": st.column_config.TextColumn("Practice Environment"),
                    "Available Equipment": st.column_config.TextColumn("Equipment"),
                    "Practice Allocation": st.column_config.TextColumn("Practice Split"),
                    "Baseline KPI (10)": st.column_config.TextColumn("Pre-Test /10"),
                    "Post KPI (10)": st.column_config.TextColumn("Post-Test /10"),
                    "Objective Gain": st.column_config.TextColumn("Objective Gain"),
                },
            )

        st.markdown("#### History Data")
        st.caption(
            "Export your full practice history for safekeeping or analysis. "
            "Clearing history permanently removes the sessions stored in this app."
        )

        history_csv = df_history.to_csv(index=False).encode("utf-8")
        history_col1, history_col2 = st.columns([2, 1])

        with history_col1:
            st.download_button(
                label="📥 Download History CSV",
                data=history_csv,
                file_name="birdie_buddy_practice_history.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_history_csv_bottom",
            )

        with history_col2:
            if st.button(
                "🗑️ Clear History",
                use_container_width=True,
                key="clear_history_bottom",
            ):
                clear_history_csv()
                st.rerun()

        if st.session_state.get("history_file_warning"):
            st.caption(
                "ℹ️ History is currently being kept in this session because the "
                "local CSV file could not be written. Use Download History CSV "
                "to keep a permanent copy."
            )



def build_export_card(diag, res, active_drills, drill_schematics, caddie):
    lines = []
    lines.append("=" * 50)
    lines.append("⛳ BIRDIE BUDDY RANGE PRACTICE CARD")
    lines.append("=" * 50)
    lines.append(f"Caddie Persona: {caddie}")
    lines.append(f"Primary Scoring Opportunity: {diag.get('primary_miss', 'N/A')}")
    lines.append(f"Primary Value Chain Stage: {diag.get('primary_miss_stage', 'N/A')}")
    if diag.get("course_management_subtype"):
        lines.append(f"Course Management Subtype: {diag.get('course_management_subtype')}")
    if diag.get("secondary_miss"):
        lines.append(f"Secondary Opportunity: {diag.get('secondary_miss')}")
    lines.append(
        f"Total Allocation: {res['total_balls']} Balls | {res['total_time']} Mins"
        f" (@ {res['sec_per_ball']}s/ball)"
    )
    lines.append(f"Practice Areas: {', '.join(res.get('practice_areas', [])) or 'Not specified'}")
    lines.append(f"Available Equipment: {', '.join(res.get('equipment', [])) or 'No training aids selected'}")
    lines.append(
        f"Practice Split: {int(res.get('grind_pct', 0)*100)}% controlled skill work | "
        f"{int(res.get('game_pct', 0)*100)}% transfer/game work"
    )
    if res.get("allocation_rationale"):
        lines.append(f"Why this split: {res['allocation_rationale']}")
    lines.append("-" * 50)
    lines.append("\nVALUE CHAIN OPPORTUNITY BREAKDOWN:")
    vc = diag.get("value_chain_analysis", {})
    lines.append(f"- Off-the-Tee Performance (Primary Drive): {vc.get('off_the_tee', 'N/A')}")
    lines.append(f"- Approach Precision (Mid Game): {vc.get('approach', 'N/A')}")
    lines.append(
        f"- Scoring/Scrambling (Short Game/Putting): {vc.get('scoring_scrambling', 'N/A')}"
    )
    lines.append(
        f"- Course Management / Strategic Decision-Making: {vc.get('course_management', 'N/A')}"
    )
    lines.append(
        f"- Mental Infrastructure (Support Systems): {vc.get('mental_infrastructure', 'N/A')}"
    )
    lines.append(f"- #1 Priority Stage: {vc.get('primary_leak_stage', 'N/A')}")
    if vc.get("leak_rationale"):
        lines.append(f"- Why This Stage Ranks First: {vc.get('leak_rationale')}")
    blind_spot = diag.get("diagnostic_blind_spot")
    if blind_spot:
        lines.append(f"\nBLIND SPOT FLAGGED (not in your story, found in your numbers):")
        lines.append(f"- {blind_spot}")
    lines.append("\n" + "=" * 50)
    lines.append("DRILL EXECUTION SCHEDULE")
    lines.append("=" * 50)

    num_drills = len(active_drills)
    is_pure_game = (
        res.get("practice_mode") == "Pure Game Mode (100% Target / Transfer Work)"
    )
    alloc_balls = res["total_balls"] if is_pure_game else res["grind_balls"]
    alloc_time = res["total_time"] if is_pure_game else res["grind_time"]

    drill_weights = _practice_drill_weights(diag, active_drills)
    drill_ball_alloc = _allocate_integer(alloc_balls, drill_weights)
    drill_time_alloc = _allocate_integer(alloc_time, drill_weights)

    for idx, d_name in enumerate(active_drills):
        balls_per_drill = drill_ball_alloc[idx]
        time_per_drill = drill_time_alloc[idx]

        schematic = drill_schematics.get(
            d_name, drill_schematics["Alignment Stick Gate Drill"]
        )
        lines.append(f"\nDRILL #{idx+1}: {d_name.upper()}")
        lines.append(f"Target: {balls_per_drill} Balls | {time_per_drill} Mins")
        lines.append(f"Equipment: {schematic['equipment']}")
        kpi = get_drill_kpi(d_name)
        lines.append(f"Objective Test: {kpi['test']}")
        lines.append(f"Success Definition: {kpi['success']}")
        lines.append(f"Pass Target: {kpi['target']}/10")
        lines.append("Setup & Execution:\n" + format_instruction_steps_for_export(schematic["vivid_description"]))
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


with st.container(border=True):
    st.title("⛳ Birdie Buddy")
    st.caption("AI-Powered Golf Coach & Practice Asset Allocator")

# Sidebar - API Key Input & Spreadsheet History Exporter
with st.sidebar.container(border=True):
    st.header("Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")

# History and trends are intentionally kept in the main page flow.
# The sidebar is reserved for configuration only.


if not api_key:
    st.warning("Please paste your Google Gemini API Key in the sidebar to begin.")
    st.stop()

genai.configure(api_key=api_key)


# -------------------------------------------------------------
# VOICE INPUT + CHARACTER-STYLE CADDIE READ-ALOUD
# -------------------------------------------------------------
def transcribe_round_audio(audio_file):
    """Transcribe a golfer's microphone recording without diagnosing it.

    The transcript is always returned to an editable text box before it can be
    used as diagnostic evidence.
    """
    if audio_file is None:
        return ""

    audio_bytes = audio_file.getvalue()
    if not audio_bytes:
        return ""

    mime_type = getattr(audio_file, "type", None) or "audio/wav"
    prompt = """
    Transcribe this golfer's spoken round description accurately.

    Rules:
    - Return ONLY the transcript. No diagnosis, summary, coaching, or commentary.
    - Preserve golf terminology, club names, hole numbers, score/stat numbers,
      miss directions, hazards, and quoted distances as spoken.
    - Use normal punctuation and paragraphing so the golfer can review/edit it.
    - If a word is genuinely unclear, write [unclear] instead of guessing.
    """

    flash_models = [
        m.name
        for m in genai.list_models()
        if "generateContent" in m.supported_generation_methods
        and "flash" in m.name.lower()
    ]
    flash_models.sort(reverse=True)

    last_error = None
    for model_name in flash_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                [prompt, {"mime_type": mime_type, "data": audio_bytes}]
            )
            if response and response.text:
                return response.text.strip()
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(
        f"No Gemini Flash model could transcribe the recording. {last_error or ''}".strip()
    )


def render_voice_story_input(text_state_key, audio_key, button_key, label):
    """Record -> transcribe -> append into an editable Streamlit text field."""
    if not hasattr(st, "audio_input"):
        st.caption(
            "🎙️ Microphone input requires a Streamlit version that supports audio_input. "
            "Typing still works normally."
        )
        return

    st.markdown("##### 🎙️ Voice Input")
    audio_file = st.audio_input(label, key=audio_key)
    if audio_file is not None:
        if st.button(
            "Transcribe & Add to Round Story",
            key=button_key,
            use_container_width=True,
        ):
            try:
                with st.spinner("Transcribing your round description..."):
                    transcript = transcribe_round_audio(audio_file)
                existing = str(st.session_state.get(text_state_key, "") or "").strip()
                combined = "\n\n".join(x for x in [existing, transcript] if x).strip()
                st.session_state[text_state_key] = combined
                st.session_state[f"{audio_key}_transcript_notice"] = True
                st.rerun()
            except Exception as exc:
                st.error(f"Voice transcription failed: {exc}")

    if st.session_state.pop(f"{audio_key}_transcript_notice", False):
        st.success("Voice description added below. Review or edit it before continuing.")


def _speech_clean_text(text):
    """Make generated caddie prose clean and natural for studio TTS."""
    if not text:
        return ""
    cleaned = str(text)
    cleaned = re.sub(r"[`*_#>]", "", cleaned)
    cleaned = cleaned.replace("•", ". ").replace("—", ", ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_tts_audio_bytes(payload):
    """Extract the final audio block from a Gemini Interactions REST response."""
    if not isinstance(payload, dict):
        return None

    # Future/SDK-like convenience shapes.
    output_audio = payload.get("output_audio") or payload.get("outputAudio")
    if isinstance(output_audio, dict) and output_audio.get("data"):
        return base64.b64decode(output_audio["data"])

    # Raw REST Interactions response documented by Gemini: steps[].content[].data.
    candidates = []
    for step in payload.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        for item in step.get("content", []) or []:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).lower()
            mime_type = str(item.get("mime_type", item.get("mimeType", ""))).lower()
            if item.get("data") and (item_type == "audio" or mime_type.startswith("audio/")):
                candidates.append(item["data"])

    if candidates:
        return base64.b64decode(candidates[-1])
    return None


def generate_gemini_tts_audio(text, persona_key):
    """Generate high-quality seekable WAV speech using Gemini TTS.

    The app uses distinct prebuilt studio voices and persona-specific delivery
    directions. It deliberately asks for a character-inspired performance rather
    than an imitation of any real actor or recorded performer.
    """
    spoken_text = _speech_clean_text(text)
    if not spoken_text:
        raise ValueError("There is no caddie text to speak.")

    persona = PERSONA_DATABASE.get(persona_key, {})
    profile = persona.get("voice_profile", {})
    voice_name = profile.get("tts_voice", "Kore")
    style = profile.get(
        "tts_style",
        "Warm, conversational golf coach. Natural pacing, expressive but clear.",
    )

    request_body = {
        "model": "gemini-3.8-flash-tts",
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": spoken_text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": style,
                }],
            }],
        }],
        "response_format": {
            "type": "audio",
            "mime_type": "audio/wav",
            "sample_rate": 24000,
        },
        "generation_config": {
            "speech_config": [{"voice": voice_name}],
        },
    }

    endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"
    model_fallbacks = [
        "gemini-3.8-flash-tts",
        "gemini-3.8-flash-lite-tts",
    ]
    last_error = None

    for model_name in model_fallbacks:
        request_body["model"] = model_name
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            audio_bytes = _extract_tts_audio_bytes(payload)
            if audio_bytes:
                return audio_bytes, voice_name, model_name
            last_error = RuntimeError("Gemini returned no playable audio block.")
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            last_error = RuntimeError(f"{model_name}: HTTP {exc.code} {body[:350]}")
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        "High-quality caddie audio could not be generated. "
        f"{last_error or 'No compatible Gemini TTS model was available.'}"
    )


def _format_audio_time(seconds):
    try:
        seconds = max(0, int(float(seconds)))
    except Exception:
        seconds = 0
    return f"{seconds // 60}:{seconds % 60:02d}"


def _render_seekable_audio_player(audio_bytes, uid, caddie_name):
    """Render a large, explicit audio player with a visible scrub/seek bar."""
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    safe_caddie = str(caddie_name).replace("<", "&lt;").replace(">", "&gt;")

    html = f"""
    <style>
      html, body {{ margin:0; padding:0; background:transparent; font-family:Arial,sans-serif; }}
      .bb-audio-card {{
        border:1px solid #4b5563; border-radius:12px; padding:14px 14px 12px;
        background:#111827; color:#f3f4f6;
      }}
      .bb-audio-title {{ font-size:15px; font-weight:700; margin-bottom:3px; }}
      audio {{ width:100%; height:42px; margin-bottom:8px; }}
      .bb-seek-row {{ display:grid; grid-template-columns:50px 1fr 50px; gap:8px; align-items:center; }}
      .bb-time {{ font-size:12px; color:#cbd5e1; text-align:center; font-variant-numeric:tabular-nums; }}
      .bb-seek {{ width:100%; accent-color:#60a5fa; cursor:pointer; }}
      .bb-buttons {{ display:grid; grid-template-columns:1fr 1.3fr 1fr; gap:8px; margin-top:10px; }}
      .bb-buttons button {{
        border:1px solid #667085; border-radius:9px; padding:9px 8px; cursor:pointer;
        background:#1f2937; color:#f8fafc; font-size:13px; font-weight:600;
      }}
      .bb-buttons button:hover {{ background:#2b3647; }}
      .bb-hint {{ font-size:11px; color:#94a3b8; margin-top:8px; text-align:center; }}
      @media (prefers-color-scheme: light) {{
        .bb-audio-card {{ background:#f8fafc; color:#111827; border-color:#d0d5dd; }}
        .bb-hint,.bb-time {{ color:#667085; }}
        .bb-buttons button {{ background:#fff; color:#111827; border-color:#cbd5e1; }}
        .bb-buttons button:hover {{ background:#f1f5f9; }}
      }}
    </style>
    <div class="bb-audio-card">
      <div class="bb-audio-title">🎧 {safe_caddie}</div>
      <audio id="audio-{uid}" controls preload="metadata">
        <source src="data:audio/wav;base64,{encoded}" type="audio/wav">
      </audio>
      <div class="bb-seek-row">
        <span id="now-{uid}" class="bb-time">0:00</span>
        <input id="seek-{uid}" class="bb-seek" type="range" min="0" max="1000" value="0" step="1" aria-label="Audio position">
        <span id="dur-{uid}" class="bb-time">0:00</span>
      </div>
      <div class="bb-buttons">
        <button id="back-{uid}">↶ 10 sec</button>
        <button id="toggle-{uid}">▶ Play / Pause</button>
        <button id="forward-{uid}">10 sec ↷</button>
      </div>
      <div class="bb-hint">Drag the blue timeline to jump anywhere in the caddie audio.</div>
    </div>
    <script>
    (() => {{
      const audio = document.getElementById('audio-{uid}');
      const seek = document.getElementById('seek-{uid}');
      const now = document.getElementById('now-{uid}');
      const dur = document.getElementById('dur-{uid}');
      const toggle = document.getElementById('toggle-{uid}');
      const fmt = (value) => {{
        if (!Number.isFinite(value)) return '0:00';
        value = Math.max(0, Math.floor(value));
        return Math.floor(value / 60) + ':' + String(value % 60).padStart(2, '0');
      }};
      const sync = () => {{
        now.textContent = fmt(audio.currentTime);
        dur.textContent = fmt(audio.duration);
        if (Number.isFinite(audio.duration) && audio.duration > 0 && !seek.matches(':active')) {{
          seek.value = Math.round((audio.currentTime / audio.duration) * 1000);
        }}
        toggle.textContent = audio.paused ? '▶ Play / Pause' : '⏸ Play / Pause';
      }};
      audio.addEventListener('loadedmetadata', sync);
      audio.addEventListener('timeupdate', sync);
      audio.addEventListener('play', sync);
      audio.addEventListener('pause', sync);
      audio.addEventListener('ended', sync);
      seek.addEventListener('input', () => {{
        if (Number.isFinite(audio.duration) && audio.duration > 0) {{
          audio.currentTime = (Number(seek.value) / 1000) * audio.duration;
          sync();
        }}
      }});
      document.getElementById('back-{uid}').onclick = () => {{ audio.currentTime = Math.max(0, audio.currentTime - 10); sync(); }};
      document.getElementById('forward-{uid}').onclick = () => {{
        const end = Number.isFinite(audio.duration) ? audio.duration : audio.currentTime + 10;
        audio.currentTime = Math.min(end, audio.currentTime + 10); sync();
      }};
      toggle.onclick = () => {{ audio.paused ? audio.play() : audio.pause(); }};
      sync();
    }})();
    </script>
    """
    components.html(html, height=210, scrolling=False)


def render_caddie_voice_player(text, persona_key, label="Generate Caddie Audio"):
    """Generate and render seekable, persona-specific studio-quality TTS audio."""
    spoken_text = _speech_clean_text(text)
    if not spoken_text:
        return

    persona = PERSONA_DATABASE.get(persona_key, {})
    profile = persona.get("voice_profile", {})
    voice_name = profile.get("tts_voice", "Kore")
    caddie_name = persona_key.split(" (")[0]

    digest = hashlib.sha256(
        f"{persona_key}|{spoken_text}".encode("utf-8")
    ).hexdigest()[:18]
    state_key = f"caddie_tts_audio_{digest}"
    meta_key = f"caddie_tts_meta_{digest}"

    with st.container(border=True):
        st.markdown("#### 🎧 Caddie Audio")
        button_text = "🎙️ Generate Caddie Audio"
        if state_key in st.session_state:
            button_text = "🔄 Regenerate Caddie Audio"

        if st.button(
            button_text,
            key=f"generate_{digest}",
            use_container_width=True,
        ):
            try:
                with st.spinner("Creating caddie audio..."):
                    audio_bytes, used_voice, used_model = generate_gemini_tts_audio(
                        spoken_text, persona_key
                    )
                st.session_state[state_key] = audio_bytes
                st.session_state[meta_key] = {
                    "voice": used_voice,
                    "model": used_model,
                }
                st.rerun()
            except Exception as exc:
                st.error(f"Voice generation failed: {exc}")

        audio_bytes = st.session_state.get(state_key)
        if audio_bytes:
            meta = st.session_state.get(meta_key, {})
            _render_seekable_audio_player(
                audio_bytes,
                uid=digest,
                caddie_name=caddie_name,
            )


# -------------------------------------------------------------
# SCORE-ROI PRIORITY ENGINE
# -------------------------------------------------------------
VALUE_CHAIN_STAGES = [
    ("Off-the-Tee Performance (Primary Drive)", "off_the_tee", "🏌️", "Off-the-Tee"),
    ("Approach Precision (Mid Game)", "approach", "🎯", "Approach"),
    ("Scoring/Scrambling (Short Game/Putting)", "scoring_scrambling", "⛳", "Scoring / Scrambling"),
    ("Course Management / Strategic Decision-Making", "course_management", "🗺️", "Course Management"),
    ("Mental Infrastructure (Support Systems)", "mental_infrastructure", "🧠", "Mental"),
]

COURSE_MANAGEMENT_SUBTYPES = [
    "Target Selection",
    "Club Selection",
    "Hazard Avoidance",
    "Layup/Go Decision",
    "Recovery Decision",
    "Aggression/Pin Selection",
]


def _interp_handicap_benchmark(handicap, benchmarks):
    """Linearly interpolate between published Shot Scope handicap benchmarks.

    Missing handicap stays missing. A golfer is never silently benchmarked as
    scratch simply because the handicap field was left blank.
    """
    if handicap in (None, ""):
        return None
    h = max(0.0, min(25.0, float(handicap)))
    keys = sorted(benchmarks)
    if h <= keys[0]:
        return float(benchmarks[keys[0]])
    if h >= keys[-1]:
        return float(benchmarks[keys[-1]])
    for lo, hi in zip(keys, keys[1:]):
        if lo <= h <= hi:
            frac = (h - lo) / (hi - lo)
            return float(benchmarks[lo] + frac * (benchmarks[hi] - benchmarks[lo]))
    return float(benchmarks[keys[-1]])


def _fmt_stat(value, suffix=""):
    """Display a tracked zero as zero and missing data as Not tracked."""
    if value is None or value == "":
        return "Not tracked"
    return f"{value}{suffix}"



def _as_int_or_none(value):
    """Safely coerce an extracted scorecard value to int without inventing zeroes."""
    if value in (None, "", "null", "N/A", "Not shown", "Unknown"):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _as_float_or_none(value):
    """Safely coerce an extracted scorecard value to float."""
    if value in (None, "", "null", "N/A", "Not shown", "Unknown"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_scorecard_with_gemini(uploaded_file):
    """Read a paper/app scorecard image with Gemini and return grounded JSON.

    The extraction layer is intentionally conservative: unclear or absent values
    must stay null so the golfer can review them instead of silently accepting a
    hallucinated stat.
    """
    image_bytes = uploaded_file.getvalue()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    extraction_prompt = r"""
    You are Birdie Buddy's scorecard-reading layer. Read this golf scorecard photo
    or golf-app screenshot carefully. Extract ONLY information that is visibly
    supported by the image. Never guess a stat from a typical golf round.

    RULES:
    - If a number, icon, direction, or label is unreadable or not shown, return null.
    - Do not infer penalty strokes or OB from a high hole score.
    - Do not infer scrambling results merely because a green was missed.
    - You MAY derive 3-putt count from clearly readable hole-by-hole putt counts.
    - You MAY derive total score from clearly readable scores only when the full
      played round shown is complete enough to support it. List derived fields.
    - Preserve useful directional tracking such as fairway misses left/right and
      GIR misses short/long/left/right when the app visibly provides those markers.
    - For screenshots such as 18Birdies, use labels/icons actually present rather
      than assuming the app's layout.
    - Capture hole-level evidence when readable because it can expose patterns that
      aggregate totals hide.

    Output STRICT raw JSON with no markdown:
    {
      "source_type": "paper_scorecard | app_screenshot | unknown",
      "round_score": null,
      "holes_played": null,
      "fairways_hit": null,
      "fairways_total": null,
      "fairway_misses_left": null,
      "fairway_misses_right": null,
      "gir": null,
      "gir_total": null,
      "gir_misses_short": null,
      "gir_misses_long": null,
      "gir_misses_left": null,
      "gir_misses_right": null,
      "putts": null,
      "penalty_strokes": null,
      "ob_lost_balls": null,
      "three_putts": null,
      "failed_up_downs": null,
      "scrambling_opportunities": null,
      "handicap": null,
      "holes": [
        {
          "hole": 1,
          "par": null,
          "score": null,
          "fairway": "hit | left | right | other | n/a | unknown",
          "gir": null,
          "putts": null,
          "penalty_strokes": null,
          "notes": null
        }
      ],
      "visible_patterns": ["short factual pattern supported by the image"],
      "other_visible_stats": ["label: value"],
      "derived_fields": ["field name and how it was derived"],
      "unclear_fields": ["important item that appears present but cannot be read confidently"],
      "extraction_notes": "short factual summary of what the image does and does not support",
      "extraction_confidence": 0.0
    }
    """

    flash_models = [
        m.name
        for m in genai.list_models()
        if "generateContent" in m.supported_generation_methods
        and "flash" in m.name.lower()
    ]
    flash_models.sort(reverse=True)

    last_error = None
    for model_name in flash_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([extraction_prompt, image])
            if response and response.text:
                clean = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(
        f"No Gemini Flash model could read this scorecard. {last_error or ''}".strip()
    )


def _normalize_followup_questions(payload):
    """Support the new adaptive list schema and older fixed-question sessions."""
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        normalized = []
        for item in payload["questions"][:5]:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            options = item.get("options", [])
            if not question or not isinstance(options, list) or len(options) < 2:
                continue
            normalized.append({
                "focus": str(item.get("focus", "Diagnostic clarification")).strip(),
                "question": question,
                "why": str(item.get("why", "This answer helps rank the highest-ROI scoring opportunity.")).strip(),
                "options": [str(opt) for opt in options[:5]],
            })
        if len(normalized) >= 2:
            return normalized

    # Backward-compatible fallback for sessions generated by the previous schema.
    fallback = []
    if isinstance(payload, dict):
        for idx in range(1, 4):
            q = str(payload.get(f"question_{idx}", "")).strip()
            opts = payload.get(f"options_q{idx}", [])
            if q and isinstance(opts, list) and len(opts) >= 2:
                fallback.append({
                    "focus": str(payload.get(f"focus_q{idx}", f"Question {idx}")),
                    "question": q,
                    "why": str(payload.get(f"why_q{idx}", "This answer helps narrow the diagnosis.")),
                    "options": [str(opt) for opt in opts[:5]],
                })
    if len(fallback) >= 2:
        return fallback

    return [
        {
            "focus": "Strategy vs. execution",
            "question": "When the costly mistakes happened, was the bigger issue the shot choice or the execution?",
            "why": "This separates a Course Management opportunity from a swing-execution problem.",
            "options": [
                "The club/target choice created unnecessary risk",
                "The choice was reasonable, but I executed it poorly",
                "Both choice and execution contributed",
                "It varied / I'm not sure",
            ],
        },
        {
            "focus": "Scoring pattern",
            "question": "Which repeated mistake felt most responsible for turning playable holes into bigger numbers?",
            "why": "This identifies the strongest competing source of avoidable strokes.",
            "options": [
                "Penalty or recovery situations",
                "Approach misses",
                "Short-game or putting mistakes",
                "It varied / I'm not sure",
            ],
        },
    ]



def _recent_coaching_history(limit=5):
    """Return a compact, prompt-safe summary of recent coaching outcomes."""
    df = load_history_df()
    if df.empty:
        return "No prior coaching history available."
    rows = df.tail(limit).to_dict("records")
    lines = []
    for row in rows:
        lines.append(
            f"Stage={row.get('Primary Value Chain Stage','N/A')} | "
            f"Opportunity={row.get('Primary Macro-Fault','N/A')} | "
            f"Drill={row.get('Primary Drill','N/A')} | "
            f"Completed={row.get('Drill Completed?','')} | "
            f"Effectiveness={row.get('Fix Effectiveness (1-5)','')}"
        )
    return "\n".join(lines)


def _enforce_history_aware_drill(diag):
    """Change a repeated low-effectiveness drill only when it was actually completed."""
    df = load_history_df()
    if df.empty or not isinstance(diag, dict):
        return diag
    stage = str(diag.get("primary_miss_stage") or "")
    drill = str(diag.get("recommended_primary_drill") or "")
    if not stage or not drill:
        return diag
    candidates = df[df["Primary Value Chain Stage"].astype(str) == stage].tail(3)
    if candidates.empty:
        return diag
    last = candidates.iloc[-1]
    prior_drill = str(last.get("Primary Drill", ""))
    completed = str(last.get("Drill Completed?", "")).lower()
    try:
        effectiveness = float(last.get("Fix Effectiveness (1-5)", ""))
    except Exception:
        effectiveness = None
    actually_completed = ("partial" in completed) or ("fully" in completed) or completed.startswith("yes")
    if prior_drill == drill and actually_completed and effectiveness is not None and effectiveness <= 2:
        alternatives = {
            "Off-the-Tee Performance (Primary Drive)": ["Alignment Stick Gate Drill", "Tee Gate Drill", "Feet-Together Balance Drill", "Pause at Top Drill"],
            "Approach Precision (Mid Game)": ["Coin Strike Low-Point Drill", "Alignment Stick Gate Drill", "Impact Bag Compression Drill", "Pause at Top Drill"],
            "Scoring/Scrambling (Short Game/Putting)": ["Ladder Distance Lag Drill", "Putting Tee Gate Drill", "Landing Zone Target Towel Drill", "Brush Turf Chipping Drill"],
            "Course Management / Strategic Decision-Making": ["Target Visual Anchoring Drill", "Positive Box Pre-Shot Routine Drill"],
            "Mental Infrastructure (Support Systems)": ["1-2-3 Box Breathing Reset Drill", "Positive Box Pre-Shot Routine Drill", "Target Visual Anchoring Drill"],
        }
        for alt in alternatives.get(stage, []):
            if alt != drill:
                diag["recommended_primary_drill"] = alt
                diag["drill_rationale"] = (diag.get("drill_rationale", "") + " Prior practice history showed the previous drill was completed but rated low-effectiveness, so Birdie Buddy changed the intervention rather than repeating it.").strip()
                break
    return diag

# Published Shot Scope amateur benchmarks. These are peer benchmarks, not
# literal Strokes Gained values. They are used to make the diagnostic
# handicap-relative rather than comparing every golfer to scratch.
HANDICAP_BENCHMARKS = {
    "fir_pct": {0: 50, 5: 48, 10: 49, 15: 48, 20: 46, 25: 46},
    "gir_pct": {0: 61, 5: 44, 10: 36, 15: 24, 20: 17, 25: 10},
    "up_down_pct": {0: 47, 5: 41, 10: 31, 15: 21, 20: 20, 25: 18},
    "putts_round": {0: 29.4, 5: 30.2, 10: 31.2, 15: 33.1, 20: 33.1, 25: 33.8},
    "penalty_strokes": {0: 0.56, 5: 0.91, 10: 1.62, 15: 2.45, 20: 3.03, 25: 4.67},
}


def calculate_score_roi(round_score, fairways_hit, gir, putts, penalty_strokes,
                       ob_lost_balls=None, three_putts=None, failed_up_downs=None,
                       scrambling_opportunities=None, handicap=None, holes_played=18,
                       fairway_opportunities=None, gir_opportunities=None):
    """Estimate practice priority while separating observed cost from peer-relative gaps.

    Raw total putts are deliberately supporting evidence only because they are
    strongly affected by GIR, proximity, and short-game leave distance. Three-putts
    remain the stronger direct putting signal when they are actually tracked.
    """
    holes = max(1, int(holes_played or 18))
    gir_opps = max(1, int(gir_opportunities or holes))
    fw_opps = fairway_opportunities
    if fw_opps in (None, ""):
        fw_opps = round(14 * holes / 18)
    fw_opps = max(1, int(fw_opps))
    scale = holes / 18.0
    has_hcp = handicap not in (None, "")
    hcp = float(handicap) if has_hcp else None

    priority_score = 0.0
    reasons, gaps = [], {}
    peer_gap = {
        "Penalty / Trouble": None,
        "Approach / GIR": None,
        "Short Game / Scrambling": None,
        "Putting": None,
        "Driving / FIR": None,
    }
    direct_cost = {"Penalty / Trouble": 0.0, "Putting": 0.0}

    if penalty_strokes is not None:
        penalty_value = max(0.0, float(penalty_strokes))
        direct_cost["Penalty / Trouble"] = penalty_value
        if penalty_value > 0:
            priority_score += min(40.0, penalty_value * 12.0)
            reasons.append(f"{penalty_value:.0f} penalty stroke(s) were observed direct score cost")
        if has_hcp:
            bench18 = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["penalty_strokes"])
            bench = bench18 * scale
            gap = max(0.0, penalty_value - bench)
            peer_gap["Penalty / Trouble"] = gap
            gaps["penalty_strokes_vs_handicap"] = round(penalty_value - bench, 2)
            reasons.append(
                f"Penalty peer benchmark for {holes} holes: {bench:.1f}; "
                f"peer-relative opportunity {_format_stroke_estimate(gap)}"
            )

    if ob_lost_balls is not None and float(ob_lost_balls) > 0:
        if not (penalty_strokes is not None and float(penalty_strokes) > 0):
            priority_score += min(10.0, float(ob_lost_balls) * 5.0)
        reasons.append(
            f"{int(ob_lost_balls)} OB/lost-ball event(s) identify trouble source; not double-counted"
        )

    if gir is not None and has_hcp:
        gir_pct = float(gir) / gir_opps * 100.0
        bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["gir_pct"])
        expected = gir_opps * bench / 100.0
        missed_gap = max(0.0, expected - float(gir))
        est = missed_gap * 0.35
        peer_gap["Approach / GIR"] = est
        gaps["gir_pct_vs_handicap"] = round(gir_pct - bench, 1)
        diff = gir_pct - bench
        if diff < -15:
            priority_score += 32
        elif diff < -8:
            priority_score += 22
        elif diff < -3:
            priority_score += 11
        reasons.append(
            f"GIR {float(gir):.0f}/{gir_opps} ({gir_pct:.0f}%) vs {bench:.0f}% peer benchmark; "
            f"heuristic opportunity {_format_stroke_estimate(est)}"
        )
    elif gir is not None:
        reasons.append(
            f"GIR {float(gir):.0f}/{gir_opps} tracked; handicap-relative peer gap unavailable"
        )

    if (
        scrambling_opportunities is not None
        and int(scrambling_opportunities) > 0
        and failed_up_downs is not None
    ):
        opps = max(1, int(scrambling_opportunities))
        fails = min(opps, int(failed_up_downs))
        observed = (opps - fails) / opps * 100
        if has_hcp:
            bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["up_down_pct"])
            exp_fails = opps * (1 - bench / 100)
            extra = max(0.0, float(fails) - exp_fails)
            est = extra * 0.70
            peer_gap["Short Game / Scrambling"] = est
            gaps["up_down_pct_vs_handicap"] = round(observed - bench, 1)
            diff = observed - bench
            if diff < -15:
                priority_score += 24
            elif diff < -8:
                priority_score += 16
            elif diff < -3:
                priority_score += 8
            reasons.append(
                f"Up-and-down {observed:.0f}% vs {bench:.0f}% peer benchmark; "
                f"heuristic opportunity {_format_stroke_estimate(est)}"
            )

    # Total putts: supporting context only. We keep the gap for explanation but
    # do not convert it into an excess-stroke estimate.
    putt_gap = None
    if putts is not None and has_hcp:
        bench18 = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["putts_round"])
        bench = bench18 * scale
        putt_gap = float(putts) - bench
        gaps["putts_vs_handicap"] = round(putt_gap, 1)
        reasons.append(
            f"Putts {float(putts):.0f} vs scaled {holes}-hole benchmark {bench:.1f}; "
            "raw putts are supporting evidence only because GIR/proximity strongly affect the total"
        )

    if three_putts is not None:
        three_est = max(0.0, float(three_putts))
        direct_cost["Putting"] = three_est
        if three_est > 0:
            priority_score += min(24.0, three_est * 10.0)
            reasons.append(
                f"{int(three_est)} three-putt(s) = observed direct putting cost and stronger evidence than raw putt total"
            )
    elif putt_gap is not None and putt_gap >= max(2.0, 5.0 * scale):
        priority_score += 3.0
        reasons.append(
            "Total putts were materially above the peer benchmark, but without 3-putt/first-putt-distance data this receives only a small supporting-priority boost"
        )

    if fairways_hit is not None and has_hcp:
        fir_pct = float(fairways_hit) / fw_opps * 100.0
        bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["fir_pct"])
        diff = fir_pct - bench
        peer_gap["Driving / FIR"] = 0.0
        gaps["fir_pct_vs_handicap"] = round(diff, 1)
        if diff < -15 and ((penalty_strokes or 0) > 0 or (ob_lost_balls or 0) > 0):
            priority_score += 8
        elif diff < -10:
            priority_score += 2
        reasons.append(
            f"FIR {float(fairways_hit):.0f}/{fw_opps} ({fir_pct:.0f}%) vs {bench:.0f}% peer benchmark; FIR alone gets no stroke value"
        )

    numeric_peer = [
        float(v) for v in peer_gap.values()
        if isinstance(v, (int, float)) and v > 0
    ]
    total_peer = sum(numeric_peer)
    total_direct = sum(
        float(v) for v in direct_cost.values()
        if isinstance(v, (int, float)) and v > 0
    )
    priority_score = round(min(100.0, priority_score), 1)
    tier = (
        "CRITICAL — Direct / Excess Score Leak" if priority_score >= 45
        else "HIGH — Major Scoring Opportunity" if priority_score >= 30
        else "MEDIUM — Worth Targeting" if priority_score >= 18
        else "LOW — Near Benchmark / Need More Evidence"
    )

    peer_parts = [
        f"{k}: {_format_stroke_estimate(v)}"
        for k, v in peer_gap.items()
        if isinstance(v, (int, float)) and v > 0
    ]
    peer_display = " | ".join(peer_parts) or (
        "No material peer gap" if has_hcp else "Handicap benchmark unavailable"
    )
    direct_parts = []
    for key, value in direct_cost.items():
        if isinstance(value, (int, float)) and value > 0:
            label = "3-putt cost" if key == "Putting" else key
            direct_parts.append(f"{label}: {value:g} stroke(s)")
    direct_display = " | ".join(direct_parts) or "No observed direct-cost event captured"

    return {
        "score": priority_score,
        "tier": tier,
        "reasons": reasons,
        "gaps": gaps,
        "excess_strokes": peer_gap,
        "peer_gap_strokes": peer_gap,
        "direct_score_cost": direct_cost,
        "total_excess_strokes": total_peer,
        "total_peer_gap": total_peer,
        "total_direct_score_cost": total_direct,
        "excess_display": peer_display,
        "peer_gap_display": peer_display,
        "direct_cost_display": direct_display,
        "has_handicap_benchmark": has_hcp,
        "holes_played": holes,
        "fairway_opportunities": fw_opps,
        "gir_opportunities": gir_opps,
    }


def build_value_chain_roi_summary(roi_data, diag):
    """Map numerical evidence into the five-stage Value Chain without double counting.

    Direct penalty/3-putt events are used as the stage's observed scoring cost when
    available. Handicap-relative gaps are used for approach/scrambling. Raw total
    putts never receive a stroke estimate by themselves.
    """
    values = {stage: 0.0 for stage, _, _, _ in VALUE_CHAIN_STAGES}
    has_numeric = {stage: False for stage, _, _, _ in VALUE_CHAIN_STAGES}
    evidence = {stage: [] for stage, _, _, _ in VALUE_CHAIN_STAGES}
    peer = roi_data.get("peer_gap_strokes", {}) if roi_data else {}
    direct = roi_data.get("direct_score_cost", {}) if roi_data else {}
    stage_by_key = {key: stage for stage, key, _, _ in VALUE_CHAIN_STAGES}

    def add_value(stage, value, label):
        if isinstance(value, (int, float)):
            has_numeric[stage] = True
            values[stage] += float(value)
            evidence[stage].append(label)

    add_value(stage_by_key["approach"], peer.get("Approach / GIR"), "handicap-relative approach estimate")
    add_value(stage_by_key["scoring_scrambling"], peer.get("Short Game / Scrambling"), "handicap-relative scrambling estimate")

    putting_direct = direct.get("Putting")
    if isinstance(putting_direct, (int, float)) and putting_direct > 0:
        add_value(stage_by_key["scoring_scrambling"], putting_direct, "observed three-putt cost")
    elif isinstance(peer.get("Putting"), (int, float)):
        add_value(stage_by_key["scoring_scrambling"], peer.get("Putting"), "putting estimate")

    # FIR remains context only and carries no stroke estimate from accuracy alone.
    if isinstance(peer.get("Driving / FIR"), (int, float)):
        add_value(stage_by_key["off_the_tee"], peer.get("Driving / FIR"), "FIR context")

    penalty_value = direct.get("Penalty / Trouble")
    if not (isinstance(penalty_value, (int, float)) and penalty_value > 0):
        penalty_value = peer.get("Penalty / Trouble")

    penalty_attribution = (diag or {}).get("penalty_attribution", "unknown")
    attribution_map = {
        "course_management": stage_by_key["course_management"],
        "off_the_tee": stage_by_key["off_the_tee"],
        "approach": stage_by_key["approach"],
        "scoring_scrambling": stage_by_key["scoring_scrambling"],
    }
    penalty_stage = attribution_map.get(penalty_attribution)
    if penalty_stage is None and penalty_attribution not in {"mixed", "unknown"}:
        fallback = (diag or {}).get("primary_miss_stage")
        if fallback in values and fallback != stage_by_key["mental_infrastructure"]:
            penalty_stage = fallback

    unattributed_penalty = 0.0
    if isinstance(penalty_value, (int, float)):
        if penalty_stage:
            add_value(penalty_stage, penalty_value, "observed penalty/trouble cost")
        elif penalty_value > 0:
            unattributed_penalty = float(penalty_value)

    primary_stage = (diag or {}).get("primary_miss_stage") or (diag or {}).get("value_chain_analysis", {}).get("primary_leak_stage")
    secondary_stage = (diag or {}).get("secondary_miss_stage")

    rows = []
    for stage, key, icon, short_name in VALUE_CHAIN_STAGES:
        modeled = _format_stroke_estimate(values[stage], include_word=False) if has_numeric[stage] else "—"
        rank = "#1 Priority" if stage == primary_stage else ("#2 Priority" if stage == secondary_stage else "")
        rows.append({
            "Stage": f"{icon} {short_name}",
            "Modeled Strokes": modeled,
            "Role": rank,
        })

    return {
        "values": values,
        "has_numeric": has_numeric,
        "evidence": evidence,
        "rows": rows,
        "unattributed_penalty": unattributed_penalty,
    }

# -------------------------------------------------------------
# MOVIE PARODY PERSONA DATABASE
# -------------------------------------------------------------
PERSONA_DATABASE = {
    "Bogey-Wan Kenobi (Jedi Master of Swing)": {
        "description": (
            "Wise Jedi mentor guiding you away from the Dark Side (the slice)"
            " using the Force of swing tempo."
        ),
        "voice_profile": {
            "lang": "en-US", "rate": 0.86, "pitch": 0.82, "volume": 1.0,
            "delivery": "Calm, measured, wise mentor delivery",
            "tts_voice": "Gacrux",
            "tts_style": (
                "Calm, resonant, mature fantasy-mentor delivery. Speak slowly and naturally with "
                "measured pauses, warm authority, understated humor, and cinematic gravitas. "
                "Do not imitate or reference any real actor or performer."
            ),
        },
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
        "voice_profile": {
            "lang": "en-GB", "rate": 1.03, "pitch": 1.08, "volume": 1.0,
            "delivery": "Bright, energetic, magical British-style delivery",
            "tts_voice": "Puck",
            "tts_style": (
                "Youthful, upbeat magical-adventure delivery with lively curiosity and light British-style "
                "cadence. Keep it conversational, playful, quick but intelligible, and expressive. "
                "Do not imitate or reference any real actor or performer."
            ),
        },
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
        "voice_profile": {
            "lang": "en-GB", "rate": 0.90, "pitch": 0.88, "volume": 1.0,
            "delivery": "Cool, deliberate, dry tactical British-style delivery",
            "tts_voice": "Algieba",
            "tts_style": (
                "Smooth, polished secret-agent briefing delivery with restrained British-style cadence, "
                "dry wit, controlled confidence, deliberate pauses, and low-key sophistication. "
                "Do not imitate or reference any real actor or performer."
            ),
        },
        "system_instruction": """
        You are 'James Pond' (Agent 00-Slice), a suave, high-class secret agent AI golf caddie.
        Tone: Cool, sophisticated, covert, tactical, dry British charm.
        Sample Catchphrases: 'Shaken, not stirred—much like your grip pressure.', 'License to slice.', "The name's Pond... James Pond."
        Analyze shot errors and mental composure as if evaluating high-stakes tactical intelligence under pressure.
        """,
    },
    "Captain Hack Sparrow (Pirate of the Fairway)": {
        "description": "Captain Hack Sparrow",
        "voice_profile": {
            "lang": "en-GB", "rate": 0.88, "pitch": 0.93, "volume": 1.0,
            "delivery": "Tipsy, swaggering pirate delivery",
            "tts_voice": "Algenib",
            "tts_style": (
                "Perform as an original, rum-soaked eccentric pirate caddie. Use a gravelly voice, loose "
                "swaggering cadence, slightly tipsy rhythm, elastic pacing, dramatic pauses, sudden quiet "
                "muttered asides, amused little self-corrections, and bursts of misplaced confidence. Let "
                "some phrases wander before landing on the golf point, as though the speaker is balancing "
                "on a rolling ship deck. Occasionally stretch a word or briefly lose the thread, then recover "
                "with pirate bravado. Keep the speech intelligible: suggest mild drunkenness rather than heavy "
                "slurring. Use original pirate mannerisms and do not imitate, name, or reference any real actor "
                "or specific recorded performance."
            ),
        },
        "system_instruction": """
        You are 'Captain Hack Sparrow,' an original, rum-soaked, eccentric pirate AI golf caddie.

        PERSONALITY & DELIVERY:
        - Sound pleasantly tipsy, overconfident, theatrical, and slightly unsteady—but still smart about golf.
        - Ramble briefly, interrupt yourself, mutter conspiratorial asides, and occasionally correct your own
          train of thought before arriving at the coaching point.
        - Use pirate vocabulary naturally: aye, mate, rum, ship, deck, compass, treasure, cannon, storm,
          mutiny, reef, harbor, plank, and cursed hazards.
        - Treat bunkers like beaches you never intended to visit, water hazards like hostile seas, OB stakes
          like forbidden coastlines, and risky recovery shots like questionable acts of piracy.
        - Be amused by disaster rather than angry about it. Sound as though every terrible golf decision is
          either a grand adventure or a suspicious navigation error.
        - Use playful uncertainty and swagger: confidently announce a thought, reconsider it halfway through,
          then land on a useful coaching conclusion.
        - Keep all coaching advice accurate and understandable beneath the chaos.
        - Never imitate, name, or reference a real actor or a specific film performance.

        ORIGINAL MANNERISM EXAMPLES:
        - "Aye... that was a perfectly sensible club, which is precisely why I'm suspicious of it."
        - "The green was over there, mate. Your ball, however, appears to have joined another crew."
        - "We could attack that pin... or—and hear me out—we could keep the golf ball."
        - "Two penalty strokes? That's not a scorecard, that's a ransom note."
        - "Steady now. Pick the harbor, trust the compass, and stop negotiating with the trees."

        Analyze the golfer's scoring leaks using nautical pirate metaphors, but keep the diagnosis, priorities,
        and practice prescription technically sound.
        """,
    },
}

# -------------------------------------------------------------
# EXPANDED KNOWLEDGE BASE & SCHEMATICS (45 DRILLS INCL. MENTAL)
# -------------------------------------------------------------
DRILL_SCHEMATICS = {
    # --- FULL SWING DRILLS (10) ---
    "Alignment Stick Gate Drill": {
        "equipment": "2 Alignment Rods (or shafts), 2–4 Golf Tees, Mid-Iron or Driver",
        "vivid_description": (
            "SETUP: Place one alignment rod on the ground parallel to your target line "
            "(outside the ball, along the toe line). Place the second rod parallel to it "
            "just outside your feet to form a 'railroad track' for body alignment. Optionally "
            "angle a third stick or use a tee height as a 'roof' cue for swing plane. "
            "EXECUTION: Take 8–10 slow rehearsal swings without a ball, keeping the clubhead "
            "traveling inside the outer rail and under the plane cue. Then hit 10–15 balls "
            "at 70–80% speed, starting each shot with feet and shoulders square to the rails. "
            "SUCCESS: Clubhead passes cleanly through the gate; divots (if any) point slightly "
            "left of target for a right-handed player; start line is stable. "
            "AVOID: Standing open/closed to the rails, or lifting the club steeply over the plane cue."
        ),
        "analogy": (
            "Railroad Track & Tunnel: Your body rides the inner rail; the clubhead travels "
            "inside the outer rail without clipping the 'roof' on the way down."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep ~60% of your weight in the lead heel through impact so the "
            "hips clear and the club can stay on the rail through the ball."
        ),
    },
    "Pause at Top Drill": {
        "equipment": "1 Alignment Rod (optional, for foot line), Mid-Iron (7-iron recommended)",
        "vivid_description": (
            "SETUP: Address the ball with a normal mid-iron setup. Optionally lay an alignment "
            "rod along your toe line so you can check that the pause does not cause a sway. "
            "EXECUTION: Make a full, unhurried backswing and freeze at the top for a full "
            "two-second count ('one-one-thousand, two-one-thousand'). From the freeze, start "
            "the downswing with the lower body—lead hip turning toward the target—before the "
            "arms and club move. Hit 12–15 balls at 60–75% effort. "
            "SUCCESS: You feel sequential order (hips → torso → arms → club) and contact stays "
            "centered. "
            "AVOID: Starting the downswing with the hands from the pause, or shortening the "
            "backswing so the pause becomes a quick hitch."
        ),
        "analogy": (
            "Coiled Archer's Bow: The pause locks aim and load; the lower body releases the "
            "arrow smoothly instead of throwing the arms first."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Count the pause silently. If you lose balance during the hold, "
            "shorten the backswing slightly until the freeze is stable."
        ),
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees, Mid-Iron or Driver, Flat Mat or Turf",
        "vivid_description": (
            "SETUP: At address, plant two tees in the ground (or mat) just outside the toe and "
            "heel of the clubhead, forming a gate only slightly wider than the clubhead. Place "
            "two more tees 4–6 inches ahead of the ball along the same width to extend the gate "
            "through the impact zone. "
            "EXECUTION: Make half to three-quarter swings, focusing on passing the clubhead "
            "through both pairs of tees without knocking them over. Start with slow swings, "
            "then add ball strikes once you can clear the gate 5 times in a row. "
            "SUCCESS: Center-face strikes; tees remain standing; ball flight starts on the "
            "intended line more often. "
            "AVOID: Swinging hard before you can clear the gate, or setting the tees so wide "
            "that the gate gives no feedback."
        ),
        "analogy": (
            "Narrow Runway: The clubhead must roll cleanly between the guardrails; any path "
            "or face error clips a tee immediately."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Soften grip pressure to about 4/10 so the clubhead can release "
            "through the gate instead of being steered."
        ),
    },
    "Towel Under Armpits Drill": {
        "equipment": "1 Microfiber Golf Towel (or small gym towel), Short or Mid-Iron",
        "vivid_description": (
            "SETUP: Fold the towel once and tuck it across your chest under both armpits so "
            "it stays in place when your arms hang in a normal address posture. Use a short "
            "or mid-iron and a normal stance width. "
            "EXECUTION: Make smooth waist-to-waist or chest-high swings without letting the "
            "towel drop. The goal is connected arm–torso motion: if the arms separate from "
            "the body, the towel falls. Hit 10–15 balls, then remove the towel and hit 5 more "
            "trying to recreate the same connected feel. "
            "SUCCESS: Towel stays put through impact; contact is more consistent; finish is "
            "balanced. "
            "AVOID: Over-squeezing the arms into the torso (creates tension) or using a full "
            "aggressive driver swing before the pattern is established."
        ),
        "analogy": (
            "Solid Core Cylinder: Arms and torso turn as one engine rather than the arms "
            "swinging independently away from the body."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Rotate the sternum through the ball; do not try to 'hit' with "
            "the hands while pinning the towel."
        ),
    },
    "Coin Strike Low-Point Drill": {
        "equipment": "1 Coin or Ball Marker, Mid-Iron (7- or 8-iron), Turf or Practice Mat",
        "vivid_description": (
            "SETUP: Place a coin or ball marker about 2 inches ahead of the ball (toward the "
            "target) on the same target line. Ball position is standard for the club. "
            "EXECUTION: Focus entirely on brushing the coin after the ball—your low point "
            "must be forward of the ball. Take several rehearsals without a ball first, "
            "trying only to nick the coin. Then hit 12–15 shots at controlled tempo. "
            "SUCCESS: Coin is flicked or scraped forward; divot (on turf) starts at or just "
            "after the ball; ball flight is more penetrating. "
            "AVOID: Scooping up at the ball (coin untouched) or digging so deep that you "
            "chunk well behind the ball."
        ),
        "analogy": (
            "Compress vs Scoop: Drive the club through the turf after the ball instead of "
            "lifting the ball with the hands."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** At impact, chest buttons should be over or slightly ahead of "
            "the coin—not hanging back over the trail foot."
        ),
    },
    "Split-Hands Release Drill": {
        "equipment": "Mid-Iron (7-iron), No special props required",
        "vivid_description": (
            "SETUP: Grip the club with the lead hand in its normal position. Place the trail "
            "hand 2–3 inches down the shaft (like a hockey stick grip) so the hands are "
            "separated. Use a slightly narrower stance for balance. "
            "EXECUTION: Make half-swings to waist height, feeling the lead forearm rotate "
            "and the clubface square/close through impact. The split grip exaggerates the "
            "release so you cannot leave the face open as easily. Hit 10–12 balls, then "
            "return to a normal grip and hit 5 matching the same release feel. "
            "SUCCESS: Ball starts closer to the intended line; face feels less 'stuck open.' "
            "AVOID: Full aggressive swings with the split grip (control first), or collapsing "
            "the lead wrist into a scoop."
        ),
        "analogy": (
            "Hockey Slap-Shot Release: The separated hands force a natural forearm roll and "
            "toe-through release instead of a blocked open face."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** On the follow-through, feel the toe of the club pointing roughly "
            "skyward as the arms extend toward the target."
        ),
    },
    "Feet-Together Balance Drill": {
        "equipment": "Any Short or Mid-Iron, Flat Stance Surface",
        "vivid_description": (
            "SETUP: Stand with feet touching (heels and toes close together). Use a short "
            "or mid-iron and a ball teed very low or on turf. Keep posture athletic—slight "
            "knee flex, hinge from the hips. "
            "EXECUTION: Make smooth 60–75% swings, prioritizing balance over distance. Hold "
            "the finish for two seconds without stepping or hopping. If you tip or spin out, "
            "shorten the swing until you can finish still. Hit 12–15 balls, then widen to a "
            "normal stance and recreate the centered feel. "
            "SUCCESS: Quiet lower body, centered contact, finish held without a recovery step. "
            "AVOID: Trying to hit hard; lateral sway; lifting the head early to 'see' the shot."
        ),
        "analogy": (
            "Deep-Rooted Tree: Rotate around a fixed central axis instead of sliding side to side."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep pressure centered over the mid-foot from address through "
            "the finish—avoid rolling to the toes or the outside of either foot."
        ),
    },
    "Wall-Head Posture Drill": {
        "equipment": "Wall, Soft Pad, or Alignment Rod propped as a rear reference; Mid-Iron",
        "vivid_description": (
            "SETUP: Stand so the back of your head (or a soft pad on the wall) lightly "
            "touches a wall, or place an alignment rod vertically behind your trail hip/glute "
            "as a contact cue. Address a mid-iron with normal posture. "
            "EXECUTION: Make slow half to three-quarter swings while maintaining light head "
            "or hip contact with the reference. The goal is to prevent early extension "
            "(hips thrusting toward the ball, head rising). Hit 10–12 controlled balls, then "
            "step away from the wall and hit 5 shots matching the same posture feel. "
            "SUCCESS: Head height stays more stable; hips rotate rather than thrust; contact "
            "is cleaner. "
            "AVOID: Pressing hard into the wall (creates tension) or making full driver swings "
            "before the pattern is stable."
        ),
        "analogy": (
            "Fixed Pivot Pin: The rear reference keeps your axis from lunging toward the ball "
            "on the downswing."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** On the first move down, feel the trail hip stay back against the "
            "reference while the lead hip clears toward the target."
        ),
    },
    "Impact Bag Compression Drill": {
        "equipment": "Impact Bag, or a tightly rolled heavy towel / duffel; Mid-Iron",
        "vivid_description": (
            "SETUP: Place the impact bag (or towel bundle) where the ball would be, at a "
            "height that matches your iron address. Take a normal mid-iron setup with hands "
            "slightly ahead of the bag face. "
            "EXECUTION: Make half-speed swings into the bag and stop at impact. Hold for one "
            "full second, checking: hands ahead of the clubhead, lead wrist flat, shaft "
            "leaning toward the target, weight favoring the lead side. Reset and repeat "
            "10–15 times. Optionally finish a few swings through the bag at slightly higher "
            "speed once the impact position feels solid. "
            "SUCCESS: Consistent forward shaft lean and 'compressed' feel without flipping. "
            "AVOID: Full-speed thrashing into the bag; hanging back on the trail foot; cupping "
            "the lead wrist at the stop."
        ),
        "analogy": (
            "Driving a Nail: Maximum energy transfers when the hands lead and the clubhead "
            "arrives last—like striking a nail flush with the hammer head trailing the grip."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Firm the lead wrist so it forms a relatively flat line with the "
            "forearm at the impact freeze—do not scoop under the bag."
        ),
    },
    "Two-Step Pump Lag Drill": {
        "equipment": "Mid-Iron (6- or 7-iron), Optional Alignment Rod for foot line",
        "vivid_description": (
            "SETUP: Normal mid-iron address. Optional: alignment rod along the toe line to "
            "monitor sway. "
            "EXECUTION: Take a full backswing. From the top, pump the club halfway down twice "
            "while holding the wrist angle (lag), then on the third motion sweep through to "
            "a full finish. The pumps train patience in the transition. Do 8–10 pump reps "
            "without a ball, then hit 10 balls using one pump and a smooth third-through swing. "
            "SUCCESS: You feel the club 'lagging' behind the hands longer; contact is less "
            "cast or early-released. "
            "AVOID: Casting the wrists on the pumps; rushing the third swing into a hit-from-"
            "the-top move."
        ),
        "analogy": (
            "Whip Crack: Preserve the wrist angle until the last moment so energy releases "
            "at the ball, not at the top of the swing."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Let the hips lead the pull-down while the hands stay relatively "
            "passive—arms follow the body, they do not throw the club from the top."
        ),
    },
    # --- SHORT GAME DRILLS (15) ---
    "Towel Behind Ball Drill": {
        "equipment": "1 Microfiber Golf Towel, Pitching Wedge or Sand Wedge, Flat Lie",
        "vivid_description": (
            "SETUP: Fold a towel flat and place it on the grass (or mat) about 4 inches "
            "behind the ball, covering the area where a fat shot would strike first. Ball "
            "is in a standard chip position—slightly back of center, weight favoring lead "
            "foot. "
            "EXECUTION: Chip with a quiet lower body, focusing on missing the towel entirely "
            "and contacting ball then turf. If you hit the towel, the strike was heavy. Hit "
            "15–20 chips to a 10–20 yard landing zone. "
            "SUCCESS: Towel stays clean; ball-first contact; predictable carry. "
            "AVOID: Trying to help the ball up with the hands (often causes the fat strike "
            "the towel is designed to expose)."
        ),
        "analogy": (
            "Steep Landing Descent: The wedge sole must enter at the ball, not drag through "
            "the danger zone behind it."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Set ~70% of your weight on the lead foot at address and keep it "
            "there through the stroke—no rocking back onto the trail foot."
        ),
    },
    "Lead Foot Weight Anchor Drill": {
        "equipment": "Wedge (56° or 60° preferred), Flat Practice Lie",
        "vivid_description": (
            "SETUP: Address a short chip with a narrow stance. Lift the trail heel (or "
            "entire trail foot onto the toe) so almost all pressure is on the lead foot. "
            "Hands slightly ahead of the ball. "
            "EXECUTION: Make soft chipping strokes while balanced on the lead leg. The "
            "forced forward center makes it hard to hit behind the ball. Hit 12–15 balls, "
            "then return both feet flat and recreate the same forward pressure. "
            "SUCCESS: Crisp ball-first contact; low point stays ahead of the ball. "
            "AVOID: Leaning the upper body backward to 'lift' the ball; excessive wrist "
            "flip to manufacture loft."
        ),
        "analogy": (
            "Heavy Anchor: The swing center stays planted ahead of the ball so the club "
            "must strike down and through."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Let the loft of the wedge elevate the ball—do not try to scoop "
            "it into the air with the hands."
        ),
    },
    "Brush Turf Chipping Drill": {
        "equipment": "Pitching Wedge or Gap Wedge, Bare Turf or Practice Mat",
        "vivid_description": (
            "SETUP: No ball at first. Take your normal chip setup—weight left, hands ahead, "
            "narrow stance. "
            "EXECUTION: Make continuous or single practice strokes focusing only on a crisp "
            "'thump' or brush of the grass just in front of the lead big toe (low-point "
            "target). Listen for a clean brush, not a deep dig. After 10 successful brushes, "
            "add a ball and try to recreate the same sound and low point for 15 chips. "
            "SUCCESS: Consistent brush location; shallow divot or paint-brush mark; solid "
            "contact when the ball is introduced. "
            "AVOID: Stopping the chest at impact; flipping the wrists to manufacture height."
        ),
        "analogy": (
            "Broom Sweep: Sweep the grass roots smoothly rather than digging a trench with "
            "the leading edge."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep the chest rotating toward the target through impact so the "
            "low point does not stall behind the ball."
        ),
    },
    "Coin Lead-Point Pitch Drill": {
        "equipment": "1 Quarter or Ball Marker, Sand or Lob Wedge, Soft Turf",
        "vivid_description": (
            "SETUP: Place a coin flat under or just behind the ball so the ball sits on or "
            "immediately ahead of the coin. Open the face slightly if the lie allows, and "
            "set weight favoring the lead side. "
            "EXECUTION: Pitch with the intent to slide the bounce of the wedge under the "
            "coin and skip the coin forward—using the sole, not the leading edge. Hit 12–15 "
            "pitches of 15–30 yards. "
            "SUCCESS: Coin skids forward; ball launches with the club's loft; fewer skulls "
            "and chunks. "
            "AVOID: Digging the leading edge into the ground behind the coin; decelerating "
            "into the strike."
        ),
        "analogy": (
            "Credit-Card Slide: The rounded sole glides along the surface like sliding a "
            "card under an object—not like chopping with an axe."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep the trail wrist softly bent (extended) through impact "
            "rather than flipping it flat early."
        ),
    },
    "Ruler in Glove Wrist Anchor Drill": {
        "equipment": "1 Thin Plastic Ruler (or similar flat stick), Lead-Hand Golf Glove, Wedge",
        "vivid_description": (
            "SETUP: Tuck a 6-inch plastic ruler under the back of the lead wrist (inside "
            "or against the glove) so it lies along the forearm–wrist line. Address a chip "
            "with normal setup. "
            "EXECUTION: Chip without letting the ruler poke painfully into the back of the "
            "hand—that poke means the lead wrist cupped or flipped. Make 15 controlled chips. "
            "Remove the ruler and hit 5 more matching the flat-wrist feel. "
            "SUCCESS: Lead wrist stays quieter; contact is more consistent; less scooping. "
            "AVOID: Gripping so tight that the arms freeze; using long pitch swings before "
            "the wrist pattern is stable on short chips."
        ),
        "analogy": (
            "Rigid Wrist Shield: The ruler trains a flat, stable lead-wrist structure so "
            "the hands cannot scoop under the ball."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Drive the motion with torso rotation and a quiet lower body—"
            "not with independent hand action."
        ),
    },
    "Hinge-and-Hold Chipping Drill": {
        "equipment": "52° or 56° Wedge, Flat Lie, Optional Alignment Stick for Target Line",
        "vivid_description": (
            "SETUP: Standard chip setup—weight left, ball slightly back, hands ahead. "
            "Pick a specific landing spot 8–15 yards away. "
            "EXECUTION: Hinge the wrists early on the takeaway to set a firm wrist angle, "
            "then hold that angle through impact and into a short finish with the hands "
            "still ahead of the clubhead (no release flip). Hit 15–20 chips varying only "
            "swing length, not the hinge-and-hold pattern. "
            "SUCCESS: Predictable trajectory; hands finish ahead of the clubhead; minimal "
            "wrist breakdown. "
            "AVOID: Re-hinging or flipping at the ball; decelerating into impact."
        ),
        "analogy": (
            "Vault-Door Lock: Hinge to set the angle, then lock that structure in steel "
            "through the strike."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** At the finish, the butt end of the grip should point roughly "
            "at the lead hip—evidence the hands stayed ahead."
        ),
    },
    "Clock System Wedge Drill": {
        "equipment": "Wedge set (e.g. 50°, 54°, 58°), Notebook or Phone for Distances, Target Flags",
        "vivid_description": (
            "SETUP: On a range or short-game area with clear landing targets, designate "
            "swing lengths as clock positions: 7:30 (lead arm about waist-high), 9:00 "
            "(lead arm about chest-high), and 10:30 (three-quarter). Use one wedge at a "
            "time. "
            "EXECUTION: Hit 5–8 balls at each clock length with the same tempo. Record "
            "average carry for each club/length pair. Do not change speed—only length. "
            "Build a personal distance chart. "
            "SUCCESS: Tight distance clusters for each length; repeatable tempo. "
            "AVOID: Swinging harder on longer clocks; mixing clubs randomly without logging "
            "results."
        ),
        "analogy": (
            "Precision Dial: Distance is controlled by arm-swing length on a fixed tempo, "
            "not by random acceleration."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep downswing tempo the same for every clock position—length "
            "changes distance; speed changes should stay minimal."
        ),
    },
    "Landing Zone Target Towel Drill": {
        "equipment": "Small Target Towel or Towel-Sized Cloth, Wedge, Rangefinder Optional",
        "vivid_description": (
            "SETUP: Place a small towel on the green or fringe 15–20 yards away as the "
            "only landing target. Ignore the flag pin for this drill—your job is the towel. "
            "Choose one wedge and one intended trajectory. "
            "EXECUTION: Hit 15–20 pitches focusing 100% on landing the ball on the towel. "
            "Walk to the towel periodically to see dispersion. Adjust setup or length based "
            "on whether you are short/long or left/right of the towel. "
            "SUCCESS: Increasing percentage of towel landings; tighter dispersion over the "
            "session. "
            "AVOID: Aiming at the flag while 'hoping' the towel works; changing clubs every "
            "shot without a plan."
        ),
        "analogy": (
            "Bullseye Landing Pad: The towel is the only scoreboard—flag-hunting comes after "
            "you can hit a spot."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Before the first ball, walk to the green and pick the exact "
            "towel spot based on slope and how much release you want after landing."
        ),
    },
    "Trail-Hand Only Pitch Drill": {
        "equipment": "Sand Wedge or Lob Wedge, Soft Turf or Mat",
        "vivid_description": (
            "SETUP: Remove the lead hand from the club. Grip lightly with the trail hand "
            "only. Use a narrow stance and a short pitch setup. "
            "EXECUTION: Pitch balls 10–25 yards using only the trail hand, feeling the "
            "clubhead weight and a soft underhand release. The trail hand often reveals "
            "whether you are scooping or sliding the bounce. Hit 10–12 balls, then add the "
            "lead hand back and match the same soft release. "
            "SUCCESS: Better awareness of clubhead mass; softer landings; less grip tension "
            "in two-handed pitches afterward. "
            "AVOID: Full aggressive swings one-handed; gripping so tight the wrist locks."
        ),
        "analogy": (
            "Underhand Toss: Replicate the natural motion of lobbing a soft ball underhand "
            "to a partner—smooth acceleration, soft hands."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Let the bounce of the wedge slap the turf softly; do not dig "
            "with the leading edge."
        ),
    },
    "Line in the Sand Drill": {
        "equipment": "Sand Wedge, Practice Bunker, Club or Stick to Draw a Line",
        "vivid_description": (
            "SETUP: In a practice bunker, draw a straight line in the sand perpendicular "
            "to the target line. No ball for the first set. Stand as you would for a "
            "standard greenside bunker shot (open stance/face as preferred). "
            "EXECUTION: Swing to enter the sand on the line and splash a consistent patch "
            "forward. After 8–10 line-only swings, place a ball just ahead of the line and "
            "repeat, entering on the line (typically 1–2 inches behind the ball). "
            "SUCCESS: Divots/splash marks start on the line; ball exits consistently. "
            "AVOID: Decelerating in the sand; aiming the low point at the ball instead of "
            "behind it."
        ),
        "analogy": (
            "Erasing the Line: Train the club to enter the sand on a precise mark so the "
            "cushion under the ball is predictable."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Accelerate fully through the sand—bunker shots die when you "
            "quit on the club through impact."
        ),
    },
    "Dollar Bill Sand Extraction Drill": {
        "equipment": "Sand Wedge, Practice Bunker, Dollar Bill or Bill-Sized Card/Target",
        "vivid_description": (
            "SETUP: Place a dollar bill (or a bill-sized card) in the bunker sand and set "
            "the ball on top of it. Open the face, set an open stance if that is your "
            "method, and lower your center slightly. "
            "EXECUTION: Splash the entire bill-sized patch of sand out onto the fringe, "
            "carrying the ball with the sand cushion. The club should not 'hit' the ball "
            "directly. Hit 10–12 shots, resetting the bill each time if needed. "
            "SUCCESS: Ball exits on a soft arc; sand patch is consistent; fewer thin skulls "
            "across the green. "
            "AVOID: Closing the face at address; trying to lift the ball with the hands "
            "instead of the sand."
        ),
        "analogy": (
            "Sand Cushion Pillow: The club lifts a pillow of sand; the ball rides the "
            "pillow—clubface never needs to strike the ball clean."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Open the clubface fully before you take your grip so the face "
            "stays open when you close your hands."
        ),
    },
    "Open-Face Sand Splash Drill": {
        "equipment": "Lob Wedge (58°–60°), Practice Bunker",
        "vivid_description": (
            "SETUP: Lay the clubface open so the face points more skyward. Grip after "
            "opening the face. Widen the stance slightly and lower your posture (more knee "
            "flex) to keep the swing shallow. Ball slightly forward of center. "
            "EXECUTION: Splash sand aggressively toward the green fringe with a full "
            "acceleration through the sand. Focus on the face staying open and the sole "
            "gliding. Hit 12–15 greenside bunker shots. "
            "SUCCESS: Higher, softer landings; sole glides rather than digs. "
            "AVOID: Standing too tall (steep dig); flipping the face closed through impact."
        ),
        "analogy": (
            "Pancake Flip: Slide the open face under the sand like turning a pancake—wide, "
            "shallow, and committed."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Lower your stance by flexing the knees and adding a bit more "
            "hip hinge so the swing stays shallow through the sand."
        ),
    },
    "Continuous Motion Pendulum Chipping Drill": {
        "equipment": "Pitching Wedge or Gap Wedge, Open Turf Strip",
        "vivid_description": (
            "SETUP: Normal chip setup. No need for a single 'hit' focus—this is a rhythm "
            "drill. "
            "EXECUTION: Swing the wedge back and through continuously over the grass for "
            "20–30 seconds, brushing turf on every forward pass without stopping at the "
            "bottom. Then place a ball and take one uninterrupted pendulum stroke into it, "
            "matching the same rhythm. Alternate 5 continuous cycles with 5 ball strikes. "
            "SUCCESS: Less jabbing and flinching; smoother tempo on real chips. "
            "AVOID: Pausing at the top or at impact; adding a sudden hit impulse when the "
            "ball appears."
        ),
        "analogy": (
            "Grandfather-Clock Pendulum: Unbroken rhythm removes the freeze and twitch that "
            "cause thin and fat chips."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Exhale softly through the forward stroke—breathing out reduces "
            "the tendency to tense and jab."
        ),
    },
    "Accelerating Through Impact Gate Drill": {
        "equipment": "2 Golf Tees, Wedge, Flat Lie",
        "vivid_description": (
            "SETUP: Plant one tee about 6 inches behind the ball and another about 12 "
            "inches ahead of the ball on the target line (or just outside the path). These "
            "mark a 'corridor' of acceleration. "
            "EXECUTION: Start the backswing from a short position and accelerate the "
            "clubhead through both tees so the forward tee is the focus—not the ball. Hit "
            "12–15 chips/pitches with a backswing shorter than the follow-through. "
            "SUCCESS: Fewer decelerated fat/thin strikes; more solid compression on short "
            "shots. "
            "AVOID: Long backswings with a soft hit at the ball; quitting on the follow-through."
        ),
        "analogy": (
            "Rocket Launch: Speed builds toward a finish line past the ball—not a stop at "
            "the ball."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Make the backswing shorter than the follow-through on purpose; "
            "that bias promotes acceleration."
        ),
    },
    "Target-Focused Eyes-Up Chipping Drill": {
        "equipment": "56° Wedge (or preferred chip club), Clear Target Flag or Spot",
        "vivid_description": (
            "SETUP: Choose a close chip (5–15 yards). Address the ball normally, then lift "
            "your eyes to the target and keep them there. "
            "EXECUTION: Stroke the chip while looking at the target instead of the ball—"
            "like a basketball free throw. Start with very short chips. Hit 10–15 balls. "
            "Then hit 5 looking at the ball but keeping the same external focus mentally. "
            "SUCCESS: Less steering and freezing over the ball; often improved contact from "
            "reduced tension. "
            "AVOID: Starting with long pitches; turning it into a trick-shot contest before "
            "the feel is natural."
        ),
        "analogy": (
            "Free-Throw Shooting: Look at the rim (target) and trust the stroke—staring at "
            "the ball often invites micromanagement."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** This drill is about freeing hand–eye coordination; if contact "
            "suffers at first, shorten the shot until solid strikes return."
        ),
    },
    # --- PUTTING DRILLS (15) ---
    "Putting Tee Gate Drill": {
        "equipment": "2 Standard Golf Tees, Putter, Flat Section of Green or Mat",
        "vivid_description": (
            "SETUP: From about 3–6 feet, set two tees just wider than a golf ball, 2–3 feet "
            "in front of the ball on the start line, forming a gate the ball must pass "
            "through. "
            "EXECUTION: Roll 15–20 putts through the center of the gate. If the ball clips "
            "a tee, the start line or face angle was off. Adjust setup until most putts "
            "pass cleanly. "
            "SUCCESS: High percentage of center-gate rolls; improved short-putt make rate. "
            "AVOID: Setting the gate too wide (no feedback) or too far away before start "
            "line is stable."
        ),
        "analogy": (
            "Soccer Goal: The ball must pass between the posts; any face or path error "
            "shows up immediately."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep the lead wrist relatively quiet and flat through impact "
            "so the face does not flare open."
        ),
    },
    "Chalk Line Straight Target Drill": {
        "equipment": "Chalk Line Tool (or string line), Putter, Flat Practice Green",
        "vivid_description": (
            "SETUP: Snap a straight chalk line 6–10 feet long on a flat portion of the "
            "green. Place the ball on the line. Square the putter face perpendicular to "
            "the line at address. "
            "EXECUTION: Roll putts that stay on the chalk the entire way. Watch where the "
            "ball leaves the line—that reveals face or path error. Hit 15–20 putts. "
            "SUCCESS: Ball tracks the line longer; face control improves. "
            "AVOID: Practicing only on severe slopes until straight-line control is solid."
        ),
        "analogy": (
            "Laser Beam: The chalk is instant visual feedback—any curve off the line is a "
            "face or path miss you can see in the first few feet."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** At address, align the putter's face line (or sight line) 90° "
            "to the chalk before you look at the hole."
        ),
    },
    "Mirror Alignment Face Drill": {
        "equipment": "Putting Alignment Mirror (or a small mirror with a line), Putter",
        "vivid_description": (
            "SETUP: Place the mirror on the green so the guideline points at your target. "
            "Set the putter on the mirror. Check that eyes are over or just inside the "
            "ball line and that shoulders look parallel to the guideline. "
            "EXECUTION: Make 10–15 practice strokes on the mirror focusing only on square "
            "face and quiet head. Then roll 10 putts from the mirror setup to a short "
            "target. "
            "SUCCESS: More consistent setup; fewer pulls/pushes from poor alignment. "
            "AVOID: Obsessing over perfect eye position for long lag putts—this drill is "
            "primarily a setup and face-awareness tool."
        ),
        "analogy": (
            "Reflective Blueprint: The mirror shows whether shoulders, eyes, and face match "
            "the plan before the stroke starts."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** For most players, the lead eye should sit roughly over the "
            "back of the ball—confirm what your mirror shows and repeat it."
        ),
    },
    "Trail-Hand Push Putting Drill": {
        "equipment": "Putter, Flat 4–8 Foot Putts",
        "vivid_description": (
            "SETUP: Grip the putter with the trail hand only. Use a comfortable stance. "
            "Pick 4–6 foot putts on a relatively straight line. "
            "EXECUTION: Stroke putts with only the trail hand, emphasizing a smooth push "
            "down the line without a wristy snap. Hit 12–15 putts, then return both hands "
            "and match the same smooth trail-hand feel. "
            "SUCCESS: Better sense of face control; less lead-hand over-dominance for some "
            "players. "
            "AVOID: Large lag strokes one-handed; flipping the trail wrist shut through impact."
        ),
        "analogy": (
            "Bowling Roll: A smooth single-arm roll down the lane—no sudden hook of the wrist."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep the shoulders quiet and square so the trail arm does not "
            "pull across the line."
        ),
    },
    "Metal Yardstick Roll Drill": {
        "equipment": "36-inch Flat Metal Yardstick (or similar straight metal edge), Putter, Carpet or Flat Green",
        "vivid_description": (
            "SETUP: Place the yardstick on a flat surface. Rest the ball on one end so it "
            "can roll along the metal edge. "
            "EXECUTION: Stroke putts so the ball stays on the yardstick for the full length. "
            "Any open/closed face or off-center hit dumps the ball off the edge quickly. "
            "Do 10–15 attempts. "
            "SUCCESS: Increasing number of full-length rolls; improved center-face contact. "
            "AVOID: Hitting hard; using a warped stick; practicing on a side-slope that "
            "makes the drill unfair."
        ),
        "analogy": (
            "Tightrope: The ball must balance on a narrow path—face and strike errors show "
            "up within inches."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** True center-face contact is required to complete the full "
            "36-inch roll—treat off-edge dumps as strike feedback, not just aim feedback."
        ),
    },
    "Parallel Rod Putting Channel Drill": {
        "equipment": "2 Alignment Rods (or shafts), Putter, Flat Green",
        "vivid_description": (
            "SETUP: Lay two rods parallel on the green slightly wider than the putter head, "
            "creating a channel aimed at the target. Place the ball in the middle of the "
            "channel. "
            "EXECUTION: Stroke putts without the putter head colliding with either rod. "
            "The channel trains a square path. Hit 15–20 short-to-medium putts. "
            "SUCCESS: Clean passes through the channel; improved path consistency. "
            "AVOID: Setting rods so tight that every stroke is a collision, or so wide that "
            "nothing is learned."
        ),
        "analogy": (
            "Bobsled Track: The putter is forced to run a stable path; cuts across or "
            "loops inside hit the walls."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Rock the shoulders as a unit; minimize independent hand and "
            "hip motion inside the channel."
        ),
    },
    "Ladder Distance Lag Drill": {
        "equipment": "4 Golf Tees or Markers, Putter, Stretch of Green 40+ Feet if Possible",
        "vivid_description": (
            "SETUP: Place tees or markers at 10, 20, 30, and 40 feet (adjust to available "
            "space). You will lag to each zone in order. "
            "EXECUTION: Roll three putts to the 10-foot zone, then 20, then 30, then 40, "
            "trying to stop inside a 3-foot circle of each marker (or leave inside a putter-"
            "length). Never leave a lag short of the first tee on long attempts. "
            "SUCCESS: Improving leave distances; better feel for backswing length vs speed. "
            "AVOID: Only practicing makeable short putts; racing through without judging "
            "the leave."
        ),
        "analogy": (
            "Climbing Rungs: Each distance is a rung—build a ladder of feel rather than "
            "one random speed."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Hold your finish until the ball stops so your eyes and hands "
            "can calibrate distance together."
        ),
    },
    "Fringe-to-Fringe Feel Drill": {
        "equipment": "Putter, Green with Visible Fringe Boundaries",
        "vivid_description": (
            "SETUP: From one fringe, putt across the green toward the opposite fringe. "
            "Goal: stop the ball within about 6 inches of the far fringe without going "
            "into the rough. "
            "EXECUTION: Hit 10–15 lags of varying green width. Focus on a smooth distance "
            "stroke and a clear visual of the landing/roll-out. "
            "SUCCESS: More leaves near the fringe; fewer long comeback putts in practice "
            "and on course. "
            "AVOID: Jabbing; picking a vague 'somewhere over there' target instead of the "
            "fringe edge."
        ),
        "analogy": (
            "Docking a Ship: Ease into the boundary—firm enough to arrive, soft enough not "
            "to crash into the rough."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Take a long look at the full distance before you step in; the "
            "visual survey is part of the stroke."
        ),
    },
    "Eyes-Closed Distance Perception Drill": {
        "equipment": "Putter, 15–25 Foot Flat or Mildly Breaking Putts",
        "vivid_description": (
            "SETUP: Pick a 15–25 foot putt. Look at the hole, then address the ball. "
            "EXECUTION: Close your eyes, stroke the putt, and immediately call 'short,' "
            "'long,' or 'good' before opening your eyes. Compare your call to the result. "
            "Do 10–12 repetitions. "
            "SUCCESS: Calls match results more often; distance feel improves without visual "
            "steering mid-stroke. "
            "AVOID: Peeking early; using this on severe doubles until basic feel is decent."
        ),
        "analogy": (
            "Internal Sensing: With eyes closed, the hands and ears report speed truthfully—"
            "no mid-stroke visual corrections."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** The point is calibration—honest calls matter more than making "
            "the putt on any single rep."
        ),
    },
    "Rubber Band Putter Sweet-Spot Drill": {
        "equipment": "2 Small Rubber Bands (or impact tape), Putter, Short Putts",
        "vivid_description": (
            "SETUP: Wrap rubber bands around the heel and toe of the putter face, leaving "
            "only the center sweet spot exposed. (Impact stickers work if bands are "
            "unavailable.) "
            "EXECUTION: Stroke 15–20 short putts. Off-center hits feel dead or bounce oddly "
            "off the bands; center hits roll pure. Adjust setup until center contact is "
            "common. "
            "SUCCESS: Higher rate of pure center strikes; more consistent roll distance. "
            "AVOID: Only long putts (feedback is clearer short); ignoring a repeated heel "
            "or toe pattern."
        ),
        "analogy": (
            "Sweet-Spot Pinpoint: Heel and toe are 'dead zones'—only the center lane gives "
            "true speed and direction."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Center contact stabilizes both direction and distance; chase "
            "the pure feel before worrying about hole-outs."
        ),
    },
    "Two-Tee Putter Gate Drill": {
        "equipment": "2 Golf Tees, Putter, Flat Green",
        "vivid_description": (
            "SETUP: Plant two tees just outside the toe and heel of the putter head at the "
            "address position, forming a gate the head must swing through. "
            "EXECUTION: Make strokes that pass through the gate without hitting either tee. "
            "Start with rehearsals, then add a ball for 15 putts from 3–8 feet. "
            "SUCCESS: Clean gate passes; centered strikes; quieter face rotation. "
            "AVOID: A gate so narrow it is impossible, or so wide it never gets touched."
        ),
        "analogy": (
            "Precision Archway: The putter head must thread the opening—path and centeredness "
            "are forced into a small window."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep the stroke low to the ground through the gate; lifting "
            "the head often causes heel/toe clips."
        ),
    },
    "Coin Balance Putter Back Drill": {
        "equipment": "1 Coin (dime or penny), Putter with a Relatively Flat Crown",
        "vivid_description": (
            "SETUP: Balance a coin on the flat top of the putter head at address. Use short "
            "putts on a flat surface. "
            "EXECUTION: Stroke the putt without letting the coin fall. Jerky acceleration "
            "or wrist snaps dump the coin. Do 10–15 successful balanced strokes (coin may "
            "fall—reset and continue). "
            "SUCCESS: Smoother tempo; fewer stabby short putts. "
            "AVOID: Only measuring success by makes; the coin is a tempo trainer first."
        ),
        "analogy": (
            "Balanced Tray: Carry a full glass across the room—smooth starts and stops keep "
            "it from spilling."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Smooth the transition from backswing to forward stroke; that "
            "is where most coins fall."
        ),
    },
    "Push-Putting No-Backswing Drill": {
        "equipment": "Putter, 3–5 Foot Straight Putts",
        "vivid_description": (
            "SETUP: Rest the putter face against the back of the ball with zero backswing "
            "planned. Use a standard putting posture. "
            "EXECUTION: Simply push the ball toward the hole with a smooth forward stroke. "
            "This removes the jab and trains forward acceleration. Hit 12–15 putts, then "
            "allow a tiny backswing and keep the same forward-only intent. "
            "SUCCESS: Less deceleration on short putts; cleaner roll. "
            "AVOID: Using this exclusively on long lags; jabbing the push instead of "
            "sliding it."
        ),
        "analogy": (
            "Shuffleboard Slide: Pure forward force—no wind-up needed for short, true rolls."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Feel the lead wrist stay stable as the putter moves down the "
            "line; the push should not become a flip."
        ),
    },
    "Short Back Long Through Stroke Drill": {
        "equipment": "Putter, 2 Tees or Markers for Stroke Length, 4–10 Foot Putts",
        "vivid_description": (
            "SETUP: Place a marker limiting the backswing to about 3 inches behind the "
            "ball and another marking a 9–12 inch follow-through target. "
            "EXECUTION: Stroke putts with a short backswing and a longer, accelerating "
            "follow-through. Hit 15 putts focusing on continuous speed through impact. "
            "SUCCESS: Fewer left-short or face-off short putts caused by deceleration. "
            "AVOID: Making the backswing long again out of habit; quitting at the ball."
        ),
        "analogy": (
            "Pendulum Acceleration: Energy builds through the low point and into a longer "
            "finish—never stalls at the ball."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Deceleration is a primary cause of missed short putts; bias "
            "your stroke so the through-swing is obviously longer than the backswing."
        ),
    },
    "Coin Balance Motion Stroke Drill": {
        "equipment": "1 Quarter or Coin, Putter, Flat Green",
        "vivid_description": (
            "SETUP: Place a coin on the green about 1 inch behind the ball. Address "
            "normally. "
            "EXECUTION: Stroke so the putter sole sweeps over the coin without touching "
            "it—promoting a level, low-to-the-ground arc. Hit 12–15 putts. If you click "
            "the coin, the putter is diving or scooping. "
            "SUCCESS: Clean misses of the coin; smoother roll and truer topspin. "
            "AVOID: Lifting up abruptly to miss the coin (creates thin, hopping putts)."
        ),
        "analogy": (
            "Gliding Hovercraft: The putter skims just above the surface—stable height, "
            "no dig, no scoop."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** A low, level sole through impact encourages pure roll instead "
            "of a hop-and-skid start."
        ),
    },
    # --- MENTAL GAME & MINDSET DRILLS (5) ---
    "1-2-3 Box Breathing Reset Drill": {
        "equipment": "None (breathwork only); Use before any shot or after a bad hole",
        "vivid_description": (
            "SETUP: Stand behind the ball or to the side of the teeing area where you can "
            "breathe without rushing. Feet planted, shoulders soft, eyes soft-focused. "
            "EXECUTION: Inhale through the nose for 4 seconds, hold for 4 seconds, exhale "
            "through the mouth or nose for 4 seconds (box pattern). Complete 3 full cycles "
            "before stepping into your pre-shot routine. Use after bogeys, penalties, or "
            "any spike of tension. Practice 5 minutes at home so the pattern is automatic "
            "on the course. "
            "SUCCESS: Noticeably slower heart rate and clearer decision-making before the "
            "next shot. "
            "AVOID: Skipping the hold phase; using shallow chest breathing instead of deeper "
            "belly-assisted breaths."
        ),
        "analogy": (
            "System Reboot: A deliberate breath cycle clears noise before you enter the "
            "execution zone."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Finish with a full exhale just before you set the club behind "
            "the ball—the body settles as the routine starts."
        ),
    },
    "Post-Shot Acceptance Hold Drill": {
        "equipment": "Golf Club; 3-Second Count After Every Practice or On-Course Swing",
        "vivid_description": (
            "SETUP: Commit before the shot that you will hold the finish regardless of "
            "result. "
            "EXECUTION: After impact, freeze a balanced finish for a full 3-second count. "
            "Observe ball flight as neutral data—no club slam, no verbal outburst. After "
            "the hold, take one deep exhale or a brief smile to release residual tension, "
            "then walk. Practice on the range for an entire bucket so the habit transfers "
            "to the course. "
            "SUCCESS: Shorter emotional recovery time; fewer spiral holes after a miss. "
            "AVOID: Holding a finish only on good shots; the drill matters most on poor ones."
        ),
        "analogy": (
            "Neutral Journalist: Report what the ball did; do not put yourself on trial in "
            "the first three seconds."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Pair the end of the 3-second hold with a physical release cue "
            "(exhale or soft smile) so tension does not carry to the next shot."
        ),
    },
    "Positive Box Pre-Shot Routine Drill": {
        "equipment": "1 Alignment Rod, Towel Line, or Imaginary Line on the Ground",
        "vivid_description": (
            "SETUP: Place a rod or draw a line on the ground a few steps behind the ball. "
            "Behind the line is the Think Box; across the line toward the ball is the Play "
            "Box. "
            "EXECUTION: In the Think Box, choose target, shot shape, club, and intermediate "
            "aim—decide fully. When ready, step across the line into the Play Box with a "
            "final look and zero new swing thoughts. If doubt appears in the Play Box, step "
            "back behind the line and restart. Rehearse this on the range for 15–20 balls "
            "before using it on the course. "
            "SUCCESS: Clearer decisions; fewer freeze-ups over the ball; easier commitment. "
            "AVOID: Doing technical swing analysis inside the Play Box; crossing the line "
            "before the decision is actually made."
        ),
        "analogy": (
            "Boxing Ring: All strategy happens outside the ropes; inside the ring is pure "
            "execution."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Doubt in the Play Box is a signal to walk back—not a signal to "
            "force a hesitant swing."
        ),
    },
    "Target Visual Anchoring Drill": {
        "equipment": "Target Flag or Specific Micro-Target (leaf, branch tip, discolored turf)",
        "vivid_description": (
            "SETUP: From behind the ball, pick a micro-target smaller than the flag—e.g. a "
            "single leaf, a fence post edge, or a distinct blade of grass on the fairway "
            "line. "
            "EXECUTION: Stare at that micro-target for a full 3 seconds. Carry the image "
            "to address, take one last look, then execute. On the range, alternate 10 shots "
            "with a vague 'fairway' aim and 10 with a micro-target; compare dispersion. "
            "SUCCESS: Tighter start lines; stronger commitment to a specific aim point. "
            "AVOID: Aiming at huge general areas; changing the micro-target after you have "
            "already addressed the ball."
        ),
        "analogy": (
            "Sniper Crosshairs: Aim small, miss small—aim at a house and you can miss the "
            "whole neighborhood."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Keep a vivid mental snapshot of the micro-target during the "
            "backswing so aim does not drift to a vague area mid-stroke."
        ),
    },
    "Mantra & Thought Neutralizer Drill": {
        "equipment": "Personal 2-Word Cue (examples: 'Smooth… Turn', 'Low… Slow', 'Trust… Finish')",
        "vivid_description": (
            "SETUP: Choose one two-word mantra before the session. Words should be process "
            "cues, not outcome cues ('make it' is a poor mantra). "
            "EXECUTION: During the backswing say word 1 silently; at the start of the "
            "downswing or through impact say word 2. The rhythm crowds out last-second "
            "doubt and technical overload. Use on 15–20 range shots, then on the course for "
            "full swings or putts that usually trigger overthinking. "
            "SUCCESS: Quieter mind over the ball; fewer freeze or quick-hit reactions. "
            "AVOID: Long multi-word speeches; changing mantras every hole; pairing the "
            "mantra with a mechanical checklist of five other swing thoughts."
        ),
        "analogy": (
            "Noise-Canceling Headphones: A simple rhythm occupies the channel that usually "
            "fills with fear and last-second fixes."
        ),
        "pro_tip": (
            "🏆 **Pro Tip:** Sync word 1 to the start of the backswing and word 2 to the "
            "release or impact so the cue becomes rhythmic, not chatty."
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
# STEP 1: HYBRID STORY + MULTI-CHOICE DIAGNOSTIC
# -------------------------------------------------------------
with st.container(border=True):
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


    # --- STEP 1A: STORY, MANUAL STATS, OR SCORECARD UPLOAD ---
    if st.session_state["diag_step"] == 1:
        st.markdown("### 📝 Add Your Round")
        st.caption(
            "Describe the round yourself, enter tracked stats, or upload a scorecard/app screenshot. "
            "Birdie Buddy will use the information available and ask only the clarifying questions it still needs."
        )

        intake_mode = st.radio(
            "Round intake method",
            ["✍️ Describe / Enter Stats", "📷 Upload Scorecard"],
            horizontal=True,
            key="round_intake_mode",
        )

        # Defaults shared by both intake paths. Missing is intentionally distinct
        # from a tracked zero throughout the diagnostic engine.
        user_round_story = ""
        scorecard_context = "No scorecard image was used."
        stats_tracked = False
        round_score = None
        fairways_hit = None
        gir = None
        putts = None
        penalty_strokes = None
        ob_lost_balls = None
        three_putts = None
        failed_up_downs = None
        scrambling_opportunities = None
        handicap = None
        handicap_known = False
        holes_played = 18
        fairway_opportunities = 14
        gir_opportunities = 18

        if intake_mode == "✍️ Describe / Enter Stats":
            render_voice_story_input(
                text_state_key="round_story_text",
                audio_key="round_story_audio",
                button_key="transcribe_round_story_btn",
                label="Record your round description",
            )
            user_round_story = st.text_area(
                "Describe your round in your own words:",
                height=150,
                placeholder=(
                    "e.g., I hit several solid drives but kept choosing aggressive targets after bogeys. "
                    "My approaches tended to finish short-right and I struggled with long-putt distance control..."
                ),
                key="round_story_text",
                help="Type normally or use Voice Input above. Voice transcripts stay editable before diagnosis.",
            )

            stats_tracked = st.toggle(
                "📋 I tracked round stats",
                value=False,
                help="Turn this on when these numbers are from the round. Once enabled, a zero is treated as a real zero rather than missing data.",
            )

            if stats_tracked:
                st.markdown("##### 🔢 Round Numbers")
                cov1, cov2, cov3 = st.columns(3)
                with cov1:
                    holes_played = st.number_input("Holes Played", min_value=1, max_value=36, value=18, step=1, help="Use 9 for a nine-hole round or the actual number completed.")
                with cov2:
                    fairway_opportunities = st.number_input("Fairway Opportunities", min_value=1, max_value=36, value=14, step=1, help="Number of holes where a fairway could be hit; do not assume 14 if the course differs.")
                with cov3:
                    gir_opportunities = st.number_input("GIR Opportunities", min_value=1, max_value=36, value=18, step=1, help="Usually equals holes played, but keep the actual denominator for partial rounds.")
                col_n1, col_n2, col_n3 = st.columns(3)
                col_n4, col_n5, col_n6 = st.columns(3)
                with col_n1:
                    score_input = st.number_input(
                        "Score", min_value=0, max_value=200, value=0, step=1,
                        help="Optional. Leave at 0 if you do not want to log total score.",
                    )
                    round_score = score_input if score_input > 0 else None
                with col_n2:
                    fairways_hit = st.number_input(
                        "Fairways Hit", min_value=0, max_value=18, value=0, step=1,
                        help="A tracked zero remains a real zero.",
                    )
                with col_n3:
                    gir = st.number_input(
                        "GIR", min_value=0, max_value=18, value=0, step=1,
                        help="Greens hit in regulation. A tracked zero remains a real zero.",
                    )
                with col_n4:
                    putts = st.number_input(
                        "Putts", min_value=0, max_value=60, value=0, step=1,
                        help="Interpret with GIR; high putts do not automatically mean poor putting.",
                    )
                with col_n5:
                    penalty_strokes = st.number_input(
                        "Penalty Strokes", min_value=0, max_value=20, value=0, step=1,
                        help="Use total penalty strokes from the round. Zero is valid when tracked.",
                    )
                with col_n6:
                    st.markdown("<div style='height: 0.15rem'></div>", unsafe_allow_html=True)
                    handicap_known = st.checkbox(
                        "Use handicap benchmark",
                        value=False,
                        help="Leave unchecked if you do not know your current handicap. The app will not assume scratch.",
                    )
                    if handicap_known:
                        handicap = st.number_input(
                            "Handicap Index", min_value=0.0, max_value=54.0, value=18.0, step=0.1,
                            help="Used only for peer-relative benchmark estimates.",
                        )
                    else:
                        st.caption("Handicap: not provided")

                st.markdown("##### 🎯 Scoring Events")
                st.caption("High-value signals that help expose hidden scoring opportunities.")
                col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                with col_e1:
                    ob_lost_balls = st.number_input(
                        "OB / Lost Balls", min_value=0, max_value=20, value=0, step=1,
                        help="Count actual out-of-bounds or lost-ball events separately from total penalty strokes.",
                    )
                with col_e2:
                    three_putts = st.number_input(
                        "3-Putts", min_value=0, max_value=18, value=0, step=1,
                        help="A concrete putting event. It is not added on top of total-putt excess in the stroke estimate.",
                    )
                with col_e3:
                    failed_up_downs = st.number_input(
                        "Failed U&Ds", min_value=0, max_value=18, value=0, step=1,
                        help="Failed Up-and-Downs: count missed up-and-down opportunities after missing the green.",
                    )
                with col_e4:
                    scrambling_opportunities = st.number_input(
                        "Scramble Opps.", min_value=0, max_value=18, value=0, step=1,
                        help="Scrambling Opportunities: holes where you missed the green and had a realistic up-and-down opportunity.",
                    )
            else:
                st.caption(
                    "Turn this on if you tracked round stats. This keeps an actual 0 (for example, 0 GIR or 0 penalties) separate from 'not tracked'."
                )

        else:
            st.markdown("##### 📷 Upload a Scorecard or Tracking Screenshot")
            st.caption(
                "Upload a clear photo of a paper scorecard or a screenshot from a golf app such as 18Birdies. "
                "The AI will read visible totals, hole-by-hole stats, miss directions, and other tracked data when available."
            )
            scorecard_file = st.file_uploader(
                "Scorecard image",
                type=["png", "jpg", "jpeg", "webp"],
                key="scorecard_upload",
                help="For best results, use a sharp image where stat labels and hole rows are readable.",
            )

            if scorecard_file is not None:
                upload_signature = (scorecard_file.name, len(scorecard_file.getvalue()))
                if st.session_state.get("scorecard_upload_signature") != upload_signature:
                    st.session_state["scorecard_upload_signature"] = upload_signature
                    st.session_state.pop("scorecard_extraction", None)
                    for key in list(st.session_state.keys()):
                        if key.startswith("upload_") and key != "upload_round_notes":
                            st.session_state.pop(key, None)

                st.image(scorecard_file, caption="Uploaded scorecard", use_container_width=True)
                if st.button("📷 Read Scorecard", type="secondary", use_container_width=True):
                    try:
                        with st.spinner("Reading the scorecard and checking visible stats..."):
                            extraction = _extract_scorecard_with_gemini(scorecard_file)
                        for key in list(st.session_state.keys()):
                            if key.startswith("upload_"):
                                st.session_state.pop(key, None)
                        st.session_state["scorecard_extraction"] = extraction
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not read this scorecard: {exc}")

            extraction = st.session_state.get("scorecard_extraction")
            if extraction:
                st.success("Scorecard read. Review the extracted values below before diagnosis.")
                confidence = _as_float_or_none(extraction.get("extraction_confidence"))
                note = extraction.get("extraction_notes")
                if confidence is not None:
                    if confidence > 1:
                        confidence = confidence / 100.0
                    confidence = max(0.0, min(1.0, confidence))
                    st.caption(f"Image-reading confidence: {confidence:.0%}")
                if note:
                    st.caption(str(note))

                unclear = extraction.get("unclear_fields") or []
                if unclear:
                    st.warning("Some items were unclear: " + "; ".join(str(x) for x in unclear[:6]))

                visible_patterns = extraction.get("visible_patterns") or []
                holes = extraction.get("holes") or []
                with st.expander("👁️ What Birdie Buddy could read from the image", expanded=False):
                    if visible_patterns:
                        st.markdown("**Visible patterns**")
                        for pattern in visible_patterns:
                            st.write(f"• {pattern}")
                    if extraction.get("other_visible_stats"):
                        st.markdown("**Other visible stats**")
                        for stat in extraction.get("other_visible_stats", []):
                            st.write(f"• {stat}")
                    readable_holes = [h for h in holes if isinstance(h, dict) and h.get("hole") is not None]
                    if readable_holes:
                        hole_df = pd.DataFrame(readable_holes)
                        st.dataframe(hole_df, hide_index=True, use_container_width=True)

                st.markdown("##### ✅ Review / Correct Extracted Stats")
                st.caption(
                    "These fields are editable. Leave a field blank when the scorecard does not actually support it. "
                    "Your confirmed values override the raw image extraction."
                )
                stats_tracked = True
                readable_holes_count = len([h for h in (extraction.get("holes") or []) if isinstance(h, dict) and h.get("hole") is not None])
                inferred_holes = _as_int_or_none(extraction.get("holes_played")) or readable_holes_count or 18
                extracted_fw_total = _as_int_or_none(extraction.get("fairways_total"))
                extracted_gir_total = _as_int_or_none(extraction.get("gir_total"))
                cov1, cov2, cov3 = st.columns(3)
                with cov1:
                    holes_played = st.number_input("Holes Played", min_value=1, max_value=36, value=int(inferred_holes), step=1, key="upload_holes_review")
                with cov2:
                    fairway_opportunities = st.number_input("Fairway Opportunities", min_value=1, max_value=36, value=int(extracted_fw_total or max(1, round(14 * holes_played / 18))), step=1, key="upload_fwopps_review")
                with cov3:
                    gir_opportunities = st.number_input("GIR Opportunities", min_value=1, max_value=36, value=int(extracted_gir_total or holes_played), step=1, key="upload_giropps_review")
                col_n1, col_n2, col_n3 = st.columns(3)
                col_n4, col_n5, col_n6 = st.columns(3)
                with col_n1:
                    round_score = st.number_input(
                        "Score", min_value=0, max_value=200,
                        value=_as_int_or_none(extraction.get("round_score")), step=1,
                        placeholder="Not shown", key="upload_score_review",
                    )
                with col_n2:
                    fairways_hit = st.number_input(
                        "Fairways Hit", min_value=0, max_value=18,
                        value=_as_int_or_none(extraction.get("fairways_hit")), step=1,
                        placeholder="Not shown", key="upload_fir_review",
                    )
                with col_n3:
                    gir = st.number_input(
                        "GIR", min_value=0, max_value=18,
                        value=_as_int_or_none(extraction.get("gir")), step=1,
                        placeholder="Not shown", key="upload_gir_review",
                    )
                with col_n4:
                    putts = st.number_input(
                        "Putts", min_value=0, max_value=60,
                        value=_as_int_or_none(extraction.get("putts")), step=1,
                        placeholder="Not shown", key="upload_putts_review",
                    )
                with col_n5:
                    penalty_strokes = st.number_input(
                        "Penalty Strokes", min_value=0, max_value=20,
                        value=_as_int_or_none(extraction.get("penalty_strokes")), step=1,
                        placeholder="Not shown", key="upload_penalty_review",
                    )
                with col_n6:
                    extracted_hcp = _as_float_or_none(extraction.get("handicap"))
                    handicap_known = st.checkbox(
                        "Use handicap benchmark",
                        value=extracted_hcp is not None,
                        key="upload_hcp_known",
                    )
                    if handicap_known:
                        handicap = st.number_input(
                            "Handicap Index", min_value=0.0, max_value=54.0,
                            value=extracted_hcp if extracted_hcp is not None else 18.0,
                            step=0.1, key="upload_hcp_review",
                        )

                st.markdown("##### 🎯 Scoring Events")
                col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                with col_e1:
                    ob_lost_balls = st.number_input(
                        "OB / Lost Balls", min_value=0, max_value=20,
                        value=_as_int_or_none(extraction.get("ob_lost_balls")), step=1,
                        placeholder="Not shown", key="upload_ob_review",
                    )
                with col_e2:
                    three_putts = st.number_input(
                        "3-Putts", min_value=0, max_value=18,
                        value=_as_int_or_none(extraction.get("three_putts")), step=1,
                        placeholder="Not shown", key="upload_3putt_review",
                    )
                with col_e3:
                    failed_up_downs = st.number_input(
                        "Failed U&Ds", min_value=0, max_value=18,
                        value=_as_int_or_none(extraction.get("failed_up_downs")), step=1,
                        placeholder="Not shown", key="upload_ud_review",
                    )
                with col_e4:
                    scrambling_opportunities = st.number_input(
                        "Scramble Opps.", min_value=0, max_value=18,
                        value=_as_int_or_none(extraction.get("scrambling_opportunities")), step=1,
                        placeholder="Not shown", key="upload_scramble_review",
                    )

                render_voice_story_input(
                    text_state_key="upload_round_notes",
                    audio_key="upload_round_notes_audio",
                    button_key="transcribe_upload_notes_btn",
                    label="Record context the scorecard cannot show",
                )
                user_round_story = st.text_area(
                    "Anything the scorecard does not show? (optional)",
                    height=120,
                    placeholder=(
                        "e.g., The two penalty holes came from aggressive recovery attempts; "
                        "my driver contact actually felt solid most of the day."
                    ),
                    key="upload_round_notes",
                    help="You can type or dictate this context. Review the transcript before continuing.",
                )

                scorecard_context = json.dumps(extraction, ensure_ascii=False)
            elif scorecard_file is not None:
                st.info("Click **Read Scorecard** to extract the tracked stats before continuing.")
            else:
                st.info("Upload a scorecard image or app screenshot to begin.")

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
                        "Course Management / Strategy",
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

        analyze_label = (
            "Analyze Uploaded Scorecard"
            if intake_mode == "📷 Upload Scorecard"
            else f"Analyze Round with {persona_display_name}"
        )
        if st.button(analyze_label, type="primary"):
            scorecard_ready = (
                intake_mode == "📷 Upload Scorecard"
                and bool(st.session_state.get("scorecard_extraction"))
            )
            if not user_round_story.strip() and not scorecard_ready:
                st.warning(
                    "Describe your round, or upload and read a scorecard, before starting the diagnosis."
                )
            else:
                st.session_state["user_round_story"] = user_round_story.strip()
                st.session_state["start_dir"] = start_dir
                st.session_state["curvature"] = curvature
                st.session_state["club_category"] = club_category
                st.session_state["divot_loc"] = divot_loc
                st.session_state["impact_feel"] = impact_feel
                st.session_state["miss_freq"] = miss_freq
                st.session_state["caddie_name"] = persona_display_name
                st.session_state["round_intake_source"] = intake_mode
                st.session_state["scorecard_context"] = scorecard_context
                st.session_state["round_stats_tracked"] = stats_tracked
                st.session_state["round_score"] = round_score
                st.session_state["round_fairways_hit"] = fairways_hit
                st.session_state["round_gir"] = gir
                st.session_state["round_putts"] = putts
                st.session_state["round_penalty_strokes"] = penalty_strokes
                st.session_state["round_ob_lost_balls"] = ob_lost_balls
                st.session_state["round_three_putts"] = three_putts
                st.session_state["round_failed_up_downs"] = failed_up_downs
                st.session_state["round_scrambling_opportunities"] = scrambling_opportunities
                st.session_state["round_handicap"] = handicap
                st.session_state["round_handicap_known"] = handicap_known
                st.session_state["round_holes_played"] = holes_played
                st.session_state["round_fairway_opportunities"] = fairway_opportunities
                st.session_state["round_gir_opportunities"] = gir_opportunities

                if stats_tracked:
                    round_numbers_block = f"""
                    - Score: {_fmt_stat(round_score)}
                    - Holes Played: {holes_played}
                    - Fairways Hit: {_fmt_stat(fairways_hit)} (out of {fairway_opportunities} opportunities)
                    - Greens in Regulation: {_fmt_stat(gir)} (out of {gir_opportunities} opportunities)
                    - Putts: {_fmt_stat(putts)}
                    - Penalty Strokes: {_fmt_stat(penalty_strokes)}
                    - OB / Lost Balls: {_fmt_stat(ob_lost_balls)}
                    - 3-Putts: {_fmt_stat(three_putts)}
                    - Failed Up-and-Downs: {_fmt_stat(failed_up_downs)}
                    - Scrambling Opportunities: {_fmt_stat(scrambling_opportunities)}
                    - Handicap: {_fmt_stat(handicap)}
                    """
                else:
                    round_numbers_block = "No round stats were tracked for this diagnosis."

                question_prompt = f"""
                You are the neutral diagnostic intake layer for Birdie Buddy.

                IMPORTANT TONE RULE FOR THIS STEP:
                - Do NOT roleplay the selected movie caddie persona here.
                - Do NOT use fantasy/movie metaphors, catchphrases, theatrical language, or jokes.
                - Use plain, direct golf language that a recreational golfer can understand immediately.
                - The persona will return AFTER the diagnostic questions are answered.

                The golfer's optional round notes/story:
                "{user_round_story if user_round_story.strip() else 'No additional story supplied.'}"

                Scorecard / screenshot extraction (if one was uploaded):
                {scorecard_context}

                IMPORTANT: the reviewed round numbers below supersede any conflicting raw extraction values.

                Optional observable settings (if marked 'Not specified', rely strictly on the story text above):
                - Start Direction: {format_selector_value(start_dir)}
                - Flight Curvature: {format_selector_value(curvature)}
                - Problem Area: {format_selector_value(club_category)}
                - Divot Location: {format_selector_value(divot_loc)}
                - Impact Feel: {format_selector_value(impact_feel)}
                - Consistency: {format_selector_value(miss_freq)}

                Round numbers they logged:
                {round_numbers_block}

                Your job is NOT to diagnose the golfer yet. Your job is to identify only the
                remaining uncertainties that could materially change which Value Chain stage deserves
                the #1 practice priority.

                Use these five stages:
                1. Off-the-Tee Performance — tee-shot execution/dispersion.
                2. Approach Precision — iron/approach execution into greens.
                3. Scoring/Scrambling — chipping, pitching, bunker play, putting.
                4. Course Management / Strategic Decision-Making — target, club, risk, layup/go,
                   hazard avoidance, pin selection, and recovery-shot choices.
                5. Mental Infrastructure — composure, commitment, routine, focus, emotional recovery.

                ADAPTIVE QUESTION RULES:
                - Ask between 2 and 5 questions. Use the FEWEST questions needed for a confident ranking.
                - Ask 2 when the scorecard/story already resolves most competing explanations.
                - Ask 3 for a normal round with a few meaningful uncertainties.
                - Use 4 or 5 only when several high-value ambiguities remain, the scorecard has important
                  unreadable fields, or multiple Value Chain stages have similarly strong evidence.
                - Each question must investigate a DIFFERENT uncertainty.
                - The first question must address the ambiguity most likely to change the #1 ROI category.
                - Do NOT ask the golfer to repeat a stat that is clearly visible on the uploaded scorecard
                  or already present in the reviewed round numbers.
                - Use hole-by-hole and directional scorecard evidence when available. If the scorecard shows
                  repeated misses right, do not ask whether misses were right; ask what CAUSED or followed them.
                - Prefer cause-discriminating questions over symptom questions.
                - If penalties/OB occurred, distinguish strategy from execution before labeling Course Management.
                - Explicitly resolve decision quality when it matters: good decision/bad execution, poor decision/reasonable execution, both, or unclear.
                - A bad outcome does NOT prove a bad decision, and a good outcome does NOT prove a good decision.
                - Do not ask a swing-mechanics question that cannot be answered from the available observations; ask for observable ball flight/contact evidence instead.
                - If 3-putts occurred, distinguish first-putt pace, read/start line, short-putt conversion,
                  and unusually long first-putt distance.
                - If GIR is poor, distinguish contact, start direction/curve, distance/club selection, and target choice.
                - If scrambling is poor, distinguish strike quality, landing-spot selection, lie difficulty, and putting conversion.
                - If fairway/GIR miss directions are visible, use them as evidence instead of asking the direction again.
                - If the uploaded scorecard has an important unclear field that would materially change the diagnosis,
                  ask a direct clarification about it rather than pretending the image supplied the answer.
                - If emotional reactions are already explicit, ask what they changed in the NEXT decision/execution.
                - Keep each question under 30 words when possible.
                - Give 3-5 short, mutually distinct, behavior-based answer choices.
                - Include "It varied / I'm not sure" when uncertainty is realistic.
                - No leading questions, no persona roleplay, and no implied diagnosis.

                For each question provide a short `focus` label and a one-sentence `why` explanation.

                **Dashboard naming rule:** Keep `primary_miss` and `secondary_miss` neutral,
                concise, and immediately understandable in normal golf language. Do not put jokes,
                character references, dramatic metaphors, or persona voice in those fields. Personality
                belongs only in `primary_miss_persona`, `secondary_miss_persona`,
                `expanded_caddie_intro`, and `caddie_drill_pep_talk`.

                Output strictly raw JSON with no markdown formatting:
                {{
                  "questions": [
                    {{
                      "focus": "2-5 word label",
                      "question": "plain-English clarification question",
                      "why": "why this answer could change the ROI diagnosis",
                      "options": ["Option A", "Option B", "Option C", "It varied / I'm not sure"]
                    }}
                  ]
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
        if st.session_state.get("round_intake_source") == "📷 Upload Scorecard":
            st.info("📷 **Scorecard-based diagnosis:** Birdie Buddy is using the reviewed stats and visible scorecard patterns below.")
            story_note = st.session_state.get("user_round_story", "").strip()
            if story_note:
                st.caption(f"Additional round note: {story_note}")
        else:
            st.info(
                f"📖 **Your Round Narrative:** \"{st.session_state.get('user_round_story')}\""
            )
        caddie = st.session_state.get("caddie_name", persona_display_name)
        qs = st.session_state.get("followup_questions", {})

        st.markdown("### 🔎 Quick Diagnostic Follow-Ups")
        st.caption(
            "Answer only the clarifications Birdie Buddy still needs. The number of questions adapts to "
            "how much the story, scorecard, and tracked stats already explain."
        )

        question_items = _normalize_followup_questions(qs)
        selected_answers = []
        for idx, item in enumerate(question_items, start=1):
            with st.container(border=True):
                st.caption(f"QUESTION {idx} · {item['focus']}")
                st.markdown(f"**{item['question']}**")
                st.caption(f"Why we're asking: {item['why']}")
                answer = st.radio(
                    f"Q{idx} Choice:",
                    options=item["options"],
                    index=None,
                    key=f"followup_answer_{idx}",
                    label_visibility="collapsed",
                )
                selected_answers.append(answer)

        answers_complete = bool(question_items) and all(
            answer is not None for answer in selected_answers
        )
        if not answers_complete:
            st.caption(f"Choose one answer for each of the {len(question_items)} clarification questions to continue.")

        followup_context = "\n".join(
            f"Diagnostic Follow-Up {idx} ({item['focus']}): {item['question']} -> Selected: {answer}"
            for idx, (item, answer) in enumerate(zip(question_items, selected_answers), start=1)
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(
                "🔍 Synthesize Highest-ROI Opportunities",
                type="primary",
                disabled=not answers_complete,
            ):
                _rs = st.session_state.get("round_score")
                _fh = st.session_state.get("round_fairways_hit")
                _gir = st.session_state.get("round_gir")
                _pt = st.session_state.get("round_putts")
                _pen = st.session_state.get("round_penalty_strokes")
                _ob = st.session_state.get("round_ob_lost_balls")
                _3p = st.session_state.get("round_three_putts")
                _ud = st.session_state.get("round_failed_up_downs")
                _scramble_opps = st.session_state.get("round_scrambling_opportunities")

                roi_data = calculate_score_roi(
                    _rs, _fh, _gir, _pt, _pen, _ob, _3p, _ud, _scramble_opps,
                    st.session_state.get("round_handicap"),
                    st.session_state.get("round_holes_played", 18),
                    st.session_state.get("round_fairway_opportunities"),
                    st.session_state.get("round_gir_opportunities")
                )

                # Preserve the grounded numerical model for the final unified scorecard.
                # The user sees one five-stage framework after the AI has attributed
                # penalty/trouble events to strategy vs execution.
                st.session_state["roi_data"] = roi_data

                full_round_input = f"""
                User Story: "{st.session_state.get('user_round_story')}"
                Start Direction: {format_selector_value(st.session_state['start_dir'])}
                Flight Curvature: {format_selector_value(st.session_state['curvature'])}
                Problem Area: {format_selector_value(st.session_state['club_category'])}
                Divot / Turf Location: {format_selector_value(st.session_state['divot_loc'])}
                Impact Sound & Feel: {format_selector_value(st.session_state['impact_feel'])}
                Miss Frequency: {format_selector_value(st.session_state['miss_freq'])}
                Diagnostic Follow-Ups:
                {followup_context}
                Scorecard / Screenshot Context:
                {st.session_state.get('scorecard_context', 'No scorecard image was used.')}
                Round Stats Tracked: {st.session_state.get('round_stats_tracked', False)}
                Round Numbers: Score={_fmt_stat(_rs)}, Holes Played={st.session_state.get('round_holes_played', 18)}, Fairways Hit={_fmt_stat(_fh)} (of {st.session_state.get('round_fairway_opportunities')}),
                GIR={_fmt_stat(_gir)} (of {st.session_state.get('round_gir_opportunities')}), Putts={_fmt_stat(_pt)}, Penalty Strokes={_fmt_stat(_pen)},
                OB/Lost Balls={_fmt_stat(_ob)}, 3-Putts={_fmt_stat(_3p)}, Failed Up-and-Downs={_fmt_stat(_ud)}, Scrambling Opportunities={_fmt_stat(_scramble_opps)},
                Handicap={_fmt_stat(st.session_state.get('round_handicap'))}
                Practice Priority Engine: {roi_data['tier']} | internal priority index {roi_data['score']}/100 (heuristic, not an externally validated score)
                Handicap Benchmark Available: {roi_data.get('has_handicap_benchmark', False)}
                Score-ROI Evidence: {'; '.join(roi_data['reasons']) if roi_data['reasons'] else 'No strong numerical scoring signal detected'}
                Observed Direct Score Cost: {roi_data['direct_cost_display']} | Total observed direct cost: {roi_data['total_direct_score_cost']:.1f}
                Handicap-Relative Peer Gap: {roi_data['peer_gap_display']} | Aggregate heuristic range: {_format_stroke_estimate(roi_data['total_peer_gap'])}
                Recent Coaching History (last 5):
                {_recent_coaching_history(5)}
                """

                system_prompt = f"""
                {active_persona['system_instruction']}

                Act as an expert biomechanical, sports psychology, and strategic golf instructor AI.
                Analyze the user's round narrative, decision tree answers, and round numbers through a
                **Golf Value Chain ROI Lens** — the same "where does the value actually leak" logic used
                in a business value chain, applied to a round of golf. Every fault belongs to exactly one
                of these five Value Chain stages. Course Management is intentionally separate from Mental
                Infrastructure: choosing the wrong shot is a strategic error; failing to stay composed or
                committed after the choice is made is a mental-execution error.

                1. **Off-the-Tee Performance (Primary Drive):** tee-shot execution and dispersion. If this
                   stage is leaking (e.g. low Fairways Hit), probe whether those misses create actual
                   scoring damage. Do not assume tee shots are the highest-ROI fix without score evidence.
                2. **Approach Precision (Mid Game):** iron/approach shot execution into greens (GIR).
                3. **Scoring/Scrambling (Short Game/Putting):** chipping, pitching, sand, and putting —
                   converting positions already gained into a low score.
                4. **Course Management / Strategic Decision-Making:** target selection, club choice,
                   aggression level, layup-vs-hero-shot decisions, playing away from hazards/OB, choosing
                   the fat side of the green, and recovery-shot decisions. This stage can be the #1 ROI
                   leak even when the underlying swing is unchanged. Penalties alone do NOT prove a
                   strategy fault: use the story/follow-up answers to distinguish poor decisions from
                   poor execution.
                5. **Mental Infrastructure (Support Systems):** routine, composure, emotional recovery,
                   confidence, commitment, and focus after the strategic choice has already been made.
                   Do not place target/club/risk-selection mistakes here.

                **Decision-Quality Rule:** Evaluate the choice separately from the result. Use one of: Good decision / bad execution; Poor decision / reasonable execution; Both contributed; Unclear; Not applicable. Never use the final outcome alone to judge the decision.

                **Mechanical Evidence Rule:** A scorecard, round story, or miss pattern can establish a performance problem but usually cannot prove a specific biomechanical cause. Label mechanics as a hypothesis unless direct observations (contact, start direction, curvature, divot, or video-quality evidence) support it. When evidence is limited, prescribe an assessment/feedback drill rather than declaring a body-motion fault as fact.

                **History Adaptation Rule:** Use the recent coaching history supplied in Round Context. If the same issue recurs after the golfer actually completed the same drill and rated it 1-2/5, change the intervention. If the drill was not completed, do not call the intervention ineffective. If a drill was rated highly yet the issue recurs, favor transfer/pressure/context work rather than simply repeating blocked mechanics.

                **Direct Cost vs Peer Gap Rule:** Keep observed direct scoring costs (such as actual penalty strokes and 3-putts) conceptually separate from handicap-relative peer gaps. A direct cost does not disappear merely because it is normal for the golfer's handicap.

                **Scorecard Grounding Rule:** When a scorecard/screenshot was uploaded, treat the reviewed
                numeric fields as authoritative for totals. Use raw image extraction only for supporting
                hole-by-hole/directional context. Never invent a stat that the extraction marked null/unclear,
                and never treat an unreadable icon as evidence.

                **Score-ROI Evidence Hierarchy:** Direct score events (OB/lost balls, penalty strokes, 3-putts)
                are stronger evidence of lost strokes than broad accuracy statistics. Failed up-and-downs
                are then interpreted against handicap/GIR context. FIR is only elevated when misses create
                meaningful trouble. Total putts are weak evidence unless supported by 3-putt frequency.
                For Course Management, the strongest evidence is a costly result PLUS evidence that the
                player voluntarily selected a higher-risk line, club, target, or recovery option when a
                reasonable lower-risk alternative existed.

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
                5. **COURSE MANAGEMENT / STRATEGIC DECISION-MAKING:** elevate when avoidable risk choices
                   repeatedly expose hazards, OB, short-sided misses, low-percentage recovery shots, or
                   unnecessary pin hunting. A single bad swing into trouble is not automatically a
                   course-management fault.
                6. **MENTAL INFRASTRUCTURE:** elevate when routine, composure, commitment, or emotional
                   recovery caused repeated scoring damage. Frustration alone is not enough, and strategic
                   target/club/risk choices belong in Course Management instead.

                **Putting context rule:** Raw putts per round are supporting evidence only because GIR,
                first-putt distance, proximity, and short-game leave distance strongly affect the total.
                Three-putts are the stronger direct putting signal when tracked. Do not convert raw putts
                into lost strokes or let a high putt total outrank stronger direct evidence by itself.

                **Missing-data rule:** If handicap is Not tracked, do NOT compare the golfer to scratch
                and do NOT invent a handicap-relative benchmark. If a zero is shown for a tracked stat,
                treat it as a real zero. If a stat says Not tracked, do not infer a value.

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
                   - If **Course Management / Strategic Decision-Making** is the primary or secondary leak,
                     do NOT invent a new drill. Use an existing implementation scaffold only: choose
                     'Target Visual Anchoring Drill' for target/aim discipline or 'Positive Box Pre-Shot
                     Routine Drill' for a repeatable club/target/risk decision gate. Keep the diagnosed
                     Value Chain stage as Course Management — do not relabel it as Mental Infrastructure
                     merely because an existing mental-game drill is used to rehearse the decision process.

                **Primary/Secondary Card Consistency:** Diagnose the secondary opportunity with the same
                rigor as the primary. Give it its own severity (`secondary_roi_priority`), evidence
                (`secondary_roi_evidence`), confidence (`secondary_confidence_score`), concise persona
                line, cause explanation, and drill. Being ranked #2 does not automatically mean LOW;
                a round can contain two HIGH or CRITICAL opportunities.

                **Canonical Caddie Narrative Directive:** `expanded_caddie_intro` is the ONE narrative
                used both on screen and for voice playback. Write it so it works equally well when read
                and when spoken aloud: about 45-75 seconds, conversational rather than report-like, and in
                the selected caddie's fictional parody persona. Use that persona's pacing, vocabulary,
                humor, tone, and mannerisms, but do not claim to be or imitate a real actor/performer.
                Mention the #1 opportunity, the most important evidence, the #2 opportunity if material,
                and the immediate practice focus. Avoid markdown, tables, raw JSON language, long strings
                of statistics, or reading confidence percentages aloud. Do NOT create a separate alternate
                spoken version of this narrative.

                Map faults to the most effective drills from this EXACT list of 45 drills:
                - FULL SWING: 'Alignment Stick Gate Drill', 'Pause at Top Drill', 'Tee Gate Drill', 'Towel Under Armpits Drill', 'Coin Strike Low-Point Drill', 'Split-Hands Release Drill', 'Feet-Together Balance Drill', 'Wall-Head Posture Drill', 'Impact Bag Compression Drill', 'Two-Step Pump Lag Drill'
                - SHORT GAME: 'Towel Behind Ball Drill', 'Lead Foot Weight Anchor Drill', 'Brush Turf Chipping Drill', 'Coin Lead-Point Pitch Drill', 'Ruler in Glove Wrist Anchor Drill', 'Hinge-and-Hold Chipping Drill', 'Clock System Wedge Drill', 'Landing Zone Target Towel Drill', 'Trail-Hand Only Pitch Drill', 'Line in the Sand Drill', 'Dollar Bill Sand Extraction Drill', 'Open-Face Sand Splash Drill', 'Continuous Motion Pendulum Chipping Drill', 'Accelerating Through Impact Gate Drill', 'Target-Focused Eyes-Up Chipping Drill'
                - PUTTING: 'Putting Tee Gate Drill', 'Chalk Line Straight Target Drill', 'Mirror Alignment Face Drill', 'Trail-Hand Push Putting Drill', 'Metal Yardstick Roll Drill', 'Parallel Rod Putting Channel Drill', 'Ladder Distance Lag Drill', 'Fringe-to-Fringe Feel Drill', 'Eyes-Closed Distance Perception Drill', 'Rubber Band Putter Sweet-Spot Drill', 'Two-Tee Putter Gate Drill', 'Coin Balance Putter Back Drill', 'Push-Putting No-Backswing Drill', 'Short Back Long Through Stroke Drill', 'Coin Balance Motion Stroke Drill'
                - MENTAL GAME: '1-2-3 Box Breathing Reset Drill', 'Post-Shot Acceptance Hold Drill', 'Positive Box Pre-Shot Routine Drill', 'Target Visual Anchoring Drill', 'Mantra & Thought Neutralizer Drill'

                Output strictly raw JSON with no markdown formatting:
                {{
                  "diagnosis_category": "Strategic ROI & Value Chain Diagnosis",
                  "primary_miss": "string — concise plain golf-language title, 2-6 words, no movie/persona language or dramatic metaphor; use labels like 'Putting — Distance Control', 'Approach — Contact', or 'Course Management — Recovery Decisions'",
                  "primary_miss_stage": "string — exactly one of: 'Off-the-Tee Performance (Primary Drive)', 'Approach Precision (Mid Game)', 'Scoring/Scrambling (Short Game/Putting)', 'Course Management / Strategic Decision-Making', 'Mental Infrastructure (Support Systems)'",
                  "primary_miss_persona": "string (1 short, witty sentence calling out primary flaw in character)",
                  "primary_cause_breakdown": "string (2-3 sentences explaining the performance cause and ROI. Do not state a specific biomechanical fault as fact unless the mechanical evidence level supports it.)",
                  "secondary_miss": "string or null — concise plain golf-language title using the same neutral style as primary_miss",
                  "secondary_miss_stage": "string or null — one of the same five Value Chain stage names",
                  "secondary_miss_persona": "string or null (1 short, witty sentence calling out the secondary opportunity in character)",
                  "secondary_cause_breakdown": "string or null (2-3 sentences explaining secondary cause and its relative stroke impact)",
                  "secondary_roi_priority": "CRITICAL | HIGH | MEDIUM | LOW | null — severity of the secondary opportunity itself, independent of being ranked #2",
                  "secondary_roi_evidence": "string or null — specific round evidence supporting the secondary opportunity",
                  "secondary_confidence_score": "number from 0.0 to 1.0 or null — confidence in the secondary diagnosis",
                  "expanded_caddie_intro": "string (canonical 45-75 second caddie narrative used VERBATIM for both on-screen text and voice playback; conversational, persona-consistent, references the golfer's story, #1 opportunity, key evidence, #2 opportunity if material, and immediate practice focus; no markdown or real-actor imitation)",
                  "caddie_drill_pep_talk": "string (2-3 sentences in persona giving encouraging range advice; this same exact text is displayed and spoken in the practice section)",
                  "value_chain_analysis": {{
                    "off_the_tee": "string (1 sentence assessment of driving/tee-shot performance, grounded in the numbers if provided)",
                    "approach": "string (1 sentence assessment of mid-iron/approach performance)",
                    "scoring_scrambling": "string (1 sentence assessment of short game & putting performance)",
                    "course_management": "string (1 sentence assessment of target selection, club choice, risk/reward decisions, layups, hazard/OB avoidance, and recovery choices; distinguish strategy from execution)",
                    "mental_infrastructure": "string (1 sentence assessment of routine, composure, commitment, focus, and emotional recovery after a decision is made)",
                    "primary_leak_stage": "string — exactly one of the five stage names above, the stage actually costing the most strokes",
                    "leak_rationale": "string (1-2 sentences explaining why this stage outranks the others, citing the round numbers where available)"
                  }},
                  "diagnostic_blind_spot": "string or null — a stat-implied leak the player's story did not mention or explain",
                  "course_management_subtype": "one of: Target Selection | Club Selection | Hazard Avoidance | Layup/Go Decision | Recovery Decision | Aggression/Pin Selection | null; use null unless Course Management is a material primary or secondary opportunity",
                  "penalty_attribution": "exactly one of: course_management | off_the_tee | approach | scoring_scrambling | mixed | unknown — classify only the best-supported cause; use mixed/unknown when evidence does not support a single category",
                  "decision_quality": "Good decision / bad execution | Poor decision / reasonable execution | Both contributed | Unclear | Not applicable",
                  "mechanical_evidence_level": "Performance pattern only | Hypothesis to test | Supported by golfer observations | Not applicable",
                  "roi_priority": "CRITICAL | HIGH | MEDIUM | LOW",
                  "roi_score": 0.0,  // internal Practice Priority Index only; heuristic 0-100, not an externally validated golf metric
                  "estimated_excess_strokes": "string — use rounded values or ranges (not hundredths) for handicap-relative heuristic estimates; explicitly label them as estimates, not measured Strokes Gained",
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
                    diag_data = _enforce_history_aware_drill(diag_data)
                    st.session_state["diagnosis"] = diag_data
                    st.session_state["show_practice_builder"] = False
                    st.session_state["show_execution_plan"] = False
                    st.session_state.pop("confirmed_resources", None)

                    # --- SAVE TO PERSISTENT CSV SPREADSHEET ---
                    vc_data = diag_data.get("value_chain_analysis", {})
                    roi_note = vc_data.get("leak_rationale") or vc_data.get(
                        "primary_leak_stage", ""
                    )
                    if diag_data.get("diagnostic_blind_spot"):
                        roi_note = (
                            f"[Blind spot] {diag_data['diagnostic_blind_spot']}"
                        )

                    save_session_to_csv(
                        primary_miss=diag_data.get("primary_miss", "N/A"),
                        primary_drill=diag_data.get("recommended_primary_drill", "N/A"),
                        secondary_miss=diag_data.get("secondary_miss", ""),
                        roi_opportunity=roi_note,
                        score=st.session_state.get("round_score"),
                        fairways_hit=st.session_state.get("round_fairways_hit"),
                        gir=st.session_state.get("round_gir"),
                        putts=st.session_state.get("round_putts"),
                        penalty_strokes=st.session_state.get("round_penalty_strokes"),
                        ob_lost_balls=st.session_state.get("round_ob_lost_balls"),
                        three_putts=st.session_state.get("round_three_putts"),
                        failed_up_downs=st.session_state.get("round_failed_up_downs"),
                        scrambling_opportunities=st.session_state.get("round_scrambling_opportunities"),
                        problem_area=st.session_state.get("club_category", ""),
                        primary_stage=diag_data.get("primary_miss_stage", ""),
                        course_management_subtype=diag_data.get("course_management_subtype", ""),
                        miss_freq=st.session_state.get("miss_freq", ""),
                        confidence=diag_data.get("confidence_score", ""),
                        handicap=st.session_state.get("round_handicap"),
                        roi_priority=diag_data.get("roi_priority", roi_data.get("tier", "")),
                        roi_score=diag_data.get("roi_score", roi_data.get("score", "")),
                        estimated_excess_strokes=roi_data.get("peer_gap_display", ""),
                        holes_played=st.session_state.get("round_holes_played"),
                        fairway_opportunities=st.session_state.get("round_fairway_opportunities"),
                        gir_opportunities=st.session_state.get("round_gir_opportunities"),
                        observed_direct_score_cost=roi_data.get("direct_cost_display", ""),
                        handicap_relative_peer_gap=roi_data.get("peer_gap_display", ""),
                        decision_quality=diag_data.get("decision_quality", ""),
                        mechanical_evidence_level=diag_data.get("mechanical_evidence_level", ""),
                    )

                    st.session_state["diag_step"] = 3
                    st.rerun()
                except Exception as e:
                    st.error(f"Error executing diagnosis: {e}")

        with col_btn2:
            if st.button("↺ Start Over"):
                # Clear the prior question set and radio selections so a new round
                # cannot inherit answers generated for the previous story.
                st.session_state.pop("followup_questions", None)
                for key in list(st.session_state.keys()):
                    if (
                        key.startswith("followup_answer_")
                        or key.startswith("upload_")
                        or key.startswith("scorecard_")
                    ):
                        st.session_state.pop(key, None)
                st.session_state["diag_step"] = 1
                st.session_state["show_practice_builder"] = False
                st.session_state["show_execution_plan"] = False
                st.session_state.pop("confirmed_resources", None)
                st.rerun()

    # --- STEP 1C: UNIFIED ROUND SCORECARD ---
    if st.session_state.get("diag_step") == 3 and "diagnosis" in st.session_state:
        diag = st.session_state["diagnosis"]
        caddie = st.session_state.get("caddie_name", persona_display_name)
        roi_data = st.session_state.get("roi_data", {})
        vc = diag.get("value_chain_analysis", {})
        stage_summary = build_value_chain_roi_summary(roi_data, diag)

        st.markdown("### 🧾 Round Scorecard")
        st.caption(
            "One five-stage view of your highest-ROI scoring opportunities. Numerical stroke estimates come from logged round data; strategy/mental attribution comes from your story and follow-up answers."
        )

        # The on-screen narrative is the single source of truth for voice playback.
        # Whatever the golfer reads here is exactly what the caddie audio speaks.
        narrative_text = str(diag.get("expanded_caddie_intro", "") or "").strip()
        if not narrative_text:
            narrative_text = " ".join(
                x for x in [
                    diag.get("primary_miss_persona", ""),
                    diag.get("secondary_miss_persona", ""),
                ]
                if x
            ).strip()

        if narrative_text:
            st.success(f'**{caddie}:** “{narrative_text}”')
            render_caddie_voice_player(
                narrative_text,
                selected_persona_key,
                label=f"Hear {caddie}'s Round Diagnosis",
            )

        primary_stage = diag.get("primary_miss_stage") or vc.get("primary_leak_stage", "Highest-ROI Focus")
        primary_title = diag.get("primary_miss", "Primary scoring opportunity")
        primary_persona = diag.get("primary_miss_persona", primary_title)
        primary_value = stage_summary["values"].get(primary_stage, 0.0)
        primary_has_numeric = stage_summary["has_numeric"].get(primary_stage, False)
        primary_metric = _format_stroke_estimate(primary_value) if primary_has_numeric and primary_value > 0 else (
            "0" if primary_has_numeric else "Qualitative"
        )

        def _confidence_label(value, fallback="N/A"):
            try:
                if value in (None, "", "null"):
                    return fallback
                return f"{float(value) * 100:.0f}%"
            except Exception:
                return str(value) if value not in (None, "") else fallback

        def _render_priority_card(
            rank, stage, title, persona_line, modeled_metric, priority_label,
            confidence_label, evidence, why_it_matters, practice_focus,
            subtype=None, accent="warning"
        ):
            medal = "🥇" if rank == 1 else "🥈"
            with st.container(border=True):
                st.markdown(f"#### {medal} #{rank} Priority: {stage}")
                callout = f"**{title}**"
                if persona_line and persona_line != title:
                    callout += f" — {persona_line}"
                if accent == "warning":
                    st.warning(callout)
                else:
                    st.info(callout)

                m1, m2, m3 = st.columns(3)
                with m1:
                    render_compact_metric("Modeled Scoring Opportunity", modeled_metric)
                with m2:
                    render_compact_metric("Practice Priority", priority_label or "N/A")
                with m3:
                    render_compact_metric("AI Confidence", confidence_label)

                if subtype and subtype != "null":
                    st.caption(f"🗺️ **Course-management subtype:** {subtype}")
                if evidence:
                    st.markdown(f"**Evidence:** {evidence}")
                if why_it_matters:
                    st.markdown(f"**Why it matters:** {why_it_matters}")
                st.markdown(f"**Highest-priority practice focus:** `{practice_focus or 'N/A'}`")

        priority_label = diag.get("roi_priority") or roi_data.get("tier", "N/A").split(" —")[0]
        confidence_label = _confidence_label(diag.get("confidence_score"))
        subtype = diag.get("course_management_subtype")
        roi_evidence = diag.get("roi_evidence") or vc.get("leak_rationale")
        primary_causes = diag.get("primary_cause_breakdown")

        _render_priority_card(
            rank=1,
            stage=primary_stage,
            title=primary_title,
            persona_line=primary_persona,
            modeled_metric=primary_metric,
            priority_label=priority_label,
            confidence_label=confidence_label,
            evidence=roi_evidence,
            why_it_matters=primary_causes,
            practice_focus=diag.get("recommended_primary_drill"),
            subtype=subtype if primary_stage == "Course Management / Strategic Decision-Making" else None,
            accent="warning",
        )

        secondary = diag.get("secondary_miss")
        if secondary:
            secondary_stage = diag.get("secondary_miss_stage", "Secondary opportunity")
            secondary_value = stage_summary["values"].get(secondary_stage, 0.0)
            secondary_has_numeric = stage_summary["has_numeric"].get(secondary_stage, False)
            secondary_metric = _format_stroke_estimate(secondary_value) if secondary_has_numeric and secondary_value > 0 else (
                "0" if secondary_has_numeric else "Qualitative"
            )
            secondary_persona = diag.get("secondary_miss_persona") or secondary
            secondary_priority = diag.get("secondary_roi_priority") or "SECONDARY"
            secondary_confidence = _confidence_label(
                diag.get("secondary_confidence_score"), fallback=confidence_label
            )
            secondary_evidence = diag.get("secondary_roi_evidence")
            if not secondary_evidence:
                secondary_evidence = diag.get("secondary_cause_breakdown")

            _render_priority_card(
                rank=2,
                stage=secondary_stage,
                title=secondary,
                persona_line=secondary_persona,
                modeled_metric=secondary_metric,
                priority_label=secondary_priority,
                confidence_label=secondary_confidence,
                evidence=secondary_evidence,
                why_it_matters=diag.get("secondary_cause_breakdown"),
                practice_focus=diag.get("recommended_secondary_drill"),
                subtype=subtype if secondary_stage == "Course Management / Strategic Decision-Making" else None,
                accent="info",
            )

        with st.container(border=True):
            st.markdown("#### Scoring Evidence: Direct Cost vs Peer Gap")
            dc1, dc2 = st.columns(2)
            with dc1:
                direct_total = roi_data.get("total_direct_score_cost", 0)
                direct_text = f"{direct_total:g} stroke(s)" if isinstance(direct_total, (int, float)) else str(direct_total)
                render_compact_metric("Observed Direct Score Cost", direct_text, subtext=roi_data.get("direct_cost_display", "No direct events captured"))
            with dc2:
                peer_text = _format_stroke_estimate(roi_data.get("total_peer_gap", 0)) if roi_data.get("has_handicap_benchmark") else "Unavailable"
                render_compact_metric("Handicap-Relative Peer Gap", peer_text, subtext=roi_data.get("peer_gap_display", "No handicap benchmark"))
            st.caption("Direct cost answers what visibly added strokes this round. Peer gap answers where performance fell below a similar-handicap benchmark. Birdie Buddy uses both rather than letting one erase the other.")

        if diag.get("decision_quality") and diag.get("decision_quality") != "Not applicable":
            st.caption(f"🧭 **Decision quality:** {diag.get('decision_quality')}")
        if diag.get("mechanical_evidence_level"):
            st.caption(f"🔬 **Mechanical evidence:** {diag.get('mechanical_evidence_level')}")

        st.markdown("#### Five-Stage ROI Snapshot")
        snapshot_df = pd.DataFrame(stage_summary["rows"])
        st.dataframe(
            snapshot_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Stage": st.column_config.TextColumn("Value Chain Stage"),
                "Modeled Strokes": st.column_config.TextColumn("Approx. Opportunity"),
                "Role": st.column_config.TextColumn("Current Focus"),
            },
        )

        if not roi_data.get("has_handicap_benchmark", False):
            st.caption(
                "ℹ️ Handicap was not provided, so handicap-relative stroke estimates are intentionally omitted where a peer benchmark is required. Direct scoring events still influence priority."
            )
        if stage_summary.get("unattributed_penalty", 0) > 0:
            st.caption(
                f"ℹ️ {stage_summary['unattributed_penalty']:g} penalty/trouble stroke(s) remain unattributed because the story did not establish whether the cause was strategy or execution."
            )

        if roi_data.get("reasons"):
            with st.expander("Why the numerical model reached this conclusion", expanded=False):
                for reason in roi_data["reasons"]:
                    st.write(f"• {reason}")

        if vc:
            with st.expander("View full five-stage Value Chain analysis", expanded=False):
                leak_stage = vc.get("primary_leak_stage", "")
                for stage_name, key, icon, _ in VALUE_CHAIN_STAGES:
                    marker = " — **#1 priority**" if stage_name == leak_stage else ""
                    st.markdown(f"**{icon} {stage_name}{marker}**")
                    st.write(vc.get(key, "N/A"))
                if vc.get("leak_rationale"):
                    st.markdown(f"**Why this stage ranks first:** {vc.get('leak_rationale')}")

        blind_spot = diag.get("diagnostic_blind_spot")
        if blind_spot:
            st.warning(
                f"🔍 **Hidden scoring opportunity:** {blind_spot}\n\n"
                "This was not prominent in your round story, but the logged evidence made it relevant to the practice plan."
            )

        st.markdown("---")
        action_col1, action_col2 = st.columns([2, 1])
        with action_col1:
            if not st.session_state.get("show_practice_builder", False):
                if st.button("🏌️ Build My Practice Plan", type="primary", use_container_width=True):
                    st.session_state["show_practice_builder"] = True
                    st.session_state.pop("confirmed_resources", None)
                    st.session_state["show_execution_plan"] = False
                    st.rerun()
            else:
                st.success("Practice-plan builder unlocked below.")
        with action_col2:
            if st.button("🔄 Describe Another Round", use_container_width=True):
                st.session_state["diag_step"] = 1
                st.session_state["show_practice_builder"] = False
                st.session_state["show_execution_plan"] = False
                st.session_state.pop("confirmed_resources", None)
                st.rerun()

# -------------------------------------------------------------
# STEP 2: PRACTICE ASSET ALLOCATION & CONSTRAINTS
# -------------------------------------------------------------
if "diagnosis" in st.session_state and st.session_state.get("show_practice_builder", False):
    with st.container(border=True):
        st.subheader("2. Build Today’s Practice Plan")
        st.caption(
            "Birdie Buddy now allocates controlled skill work vs transfer work from the diagnosis, "
            "practice history, and the facilities/equipment you actually have today."
        )

        diag_for_plan = st.session_state["diagnosis"]
        preferred_primary = diag_for_plan.get("recommended_primary_drill")
        preferred_secondary = diag_for_plan.get("recommended_secondary_drill")

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

        primary_category = _drill_category(preferred_primary or "")
        default_area = {
            "full_swing": "Driving Range / Full-Swing Bay",
            "putting": "Putting Green",
            "short_game": "Short-Game / Chipping Area",
            "bunker": "Practice Bunker",
            "mental": "Driving Range / Full-Swing Bay",
        }.get(primary_category, "Driving Range / Full-Swing Bay")

        practice_areas = st.multiselect(
            "Where can you practice today?",
            PRACTICE_AREA_OPTIONS,
            default=[default_area],
            help="Select every area you can actually use during this session.",
        )
        equipment = st.multiselect(
            "Training aids / equipment available",
            EQUIPMENT_OPTIONS,
            default=["Tees"],
            help="Golf clubs and balls are assumed. Select only the extra aids you actually have.",
        )

        resolved_primary, primary_sub = _resolve_drill_for_environment(
            preferred_primary, practice_areas, equipment
        )
        resolved_secondary, secondary_sub = _resolve_drill_for_environment(
            preferred_secondary, practice_areas, equipment
        ) if preferred_secondary else (None, None)

        if primary_sub and resolved_primary:
            st.info(
                f"🛠️ **Environment-aware substitution:** `{primary_sub}`. "
                "The replacement stays in the same coaching category so the diagnosis is preserved."
            )
        elif primary_sub and not resolved_primary:
            st.error(
                f"The primary recommendation — **{preferred_primary}** — cannot be executed with the selected "
                "practice area/equipment, and no same-category substitute is currently available. "
                "Add the required facility/aid before generating this plan."
            )

        if secondary_sub and resolved_secondary:
            st.caption(f"Secondary drill adjusted for today's setup: {secondary_sub}")
        elif preferred_secondary and not resolved_secondary:
            st.caption(
                "The secondary drill is unavailable in today's environment, so Birdie Buddy will keep the session focused on the primary opportunity rather than prescribe unrelated work."
            )

        practice_mode = st.radio(
            "Select Practice Mode:",
            options=[
                "Combination / Hybrid (AI Balanced)",
                "Pure Grind Mode (100% Controlled Skill Work)",
                "Pure Game Mode (100% Target / Transfer Work)",
            ],
            horizontal=False,
        )

        allocation_rationale = ""
        if practice_mode == "Pure Grind Mode (100% Controlled Skill Work)":
            grind_pct = 1.0
            allocation_rationale = "You selected 100% controlled skill work."
        elif practice_mode == "Pure Game Mode (100% Target / Transfer Work)":
            grind_pct = 0.0
            allocation_rationale = "You selected 100% transfer/target-pressure work."
        else:
            adaptive_grind_pct, allocation_rationale = _adaptive_hybrid_split(diag_for_plan)
            st.info(
                f"**AI-Balanced recommendation:** {int(adaptive_grind_pct*100)}% controlled skill work / "
                f"{int((1-adaptive_grind_pct)*100)}% transfer & pressure.\n\n{allocation_rationale}"
            )
            user_override = st.checkbox("Override the AI practice split")
            if user_override:
                grind_pct = st.slider(
                    "Controlled Skill Work Allocation (%)",
                    min_value=0,
                    max_value=100,
                    value=int(adaptive_grind_pct * 100),
                ) / 100.0
                allocation_rationale += " The golfer manually overrode the suggested split."
            else:
                grind_pct = adaptive_grind_pct

        game_pct = 1.0 - grind_pct
        grind_balls = int(round(total_balls * grind_pct))
        game_balls = total_balls - grind_balls
        grind_time = int(round(total_time * grind_pct))
        game_time = total_time - grind_time
        sec_per_ball = int((total_time * 60) / total_balls) if total_balls > 0 else 0

        can_generate = bool(practice_areas) and resolved_primary is not None
        if not practice_areas:
            st.warning("Select at least one practice area before generating the execution plan.")

        if st.button(
            "✅ Confirm & Generate Practice Execution Plan",
            type="primary",
            disabled=not can_generate,
            use_container_width=True,
        ):
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
                "practice_areas": practice_areas,
                "equipment": equipment,
                "resolved_primary_drill": resolved_primary,
                "resolved_secondary_drill": resolved_secondary,
                "allocation_rationale": allocation_rationale,
            }
            st.session_state["show_execution_plan"] = True
            st.rerun()

        if "confirmed_resources" in st.session_state:
            res_data = st.session_state["confirmed_resources"]
            st.write("**Confirmed Practice Distribution:**")
            st.progress(
                res_data["grind_pct"],
                text=(
                    f"Controlled Skill Work: {int(res_data['grind_pct']*100)}% | "
                    f"Transfer / Game Work: {int(res_data['game_pct']*100)}%"
                ),
            )
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                render_compact_metric(
                    "Controlled Work",
                    f"{res_data['grind_balls']} balls",
                    subtext=f"{res_data['grind_time']} mins",
                )
            with col_b:
                render_compact_metric(
                    "Transfer / Game Work",
                    f"{res_data['game_balls']} balls",
                    subtext=f"{res_data['game_time']} mins",
                )
            with col_c:
                render_compact_metric(
                    "Target Pace",
                    f"{res_data['sec_per_ball']} sec/ball",
                    subtext="Session-average pace",
                )

# -------------------------------------------------------------
# STEP 3: ADAPTIVE PRACTICE EXECUTION & SETUP GUIDE
# -------------------------------------------------------------
if (
    "diagnosis" in st.session_state
    and "confirmed_resources" in st.session_state
    and st.session_state.get("show_execution_plan", False)
):
    with st.container(border=True):
        st.subheader("3. Adaptive Practice Execution & Setup Guide")

        if "diagnosis" in st.session_state and "confirmed_resources" in st.session_state:
            diag = st.session_state["diagnosis"]
            res = st.session_state["confirmed_resources"]
            caddie = st.session_state.get("caddie_name", persona_display_name)

            p_drill = res.get("resolved_primary_drill") or diag.get("recommended_primary_drill", "Alignment Stick Gate Drill")
            s_drill = res.get("resolved_secondary_drill")
            p_miss = diag.get("primary_miss", "your highest-priority scoring opportunity")
            s_miss = diag.get("secondary_miss")
            rationale = diag.get("drill_rationale")
            pep_talk = diag.get("caddie_drill_pep_talk")

            c_balls = res["total_balls"]
            c_time = res["total_time"]
            p_mode = res.get("practice_mode", "Combination / Hybrid (AI Balanced)")

            is_pure_game = p_mode == "Pure Game Mode (100% Target / Transfer Work)"
            is_hybrid = p_mode == "Combination / Hybrid (AI Balanced)"

            if is_pure_game:
                st.info(
                    "🎮 **Pure Game Mode Active:** the available work is converted toward one-ball target/transfer reps."
                )
                p_drill = GAME_MODE_DRILL_MAP.get(p_drill, p_drill)
                if s_drill:
                    s_drill = GAME_MODE_DRILL_MAP.get(s_drill, s_drill)

            p_complexity = DRILL_COMPLEXITY.get(p_drill, "Medium")
            active_drills = [p_drill]
            if c_balls >= 30 and c_time >= 30 and s_drill and s_drill not in active_drills:
                active_drills.append(s_drill)

            # More practice time deepens the highest-priority work; it does not automatically
            # create extra swing changes. Hybrid transfer work is handled by the final pressure block.

            if (c_balls < 40 or c_time < 30) and p_complexity == "High":
                st.warning(
                    f"⚠️ **Low Resource Alert:** `{p_drill}` is High Complexity. Focus on"
                    f" basic feel keys with your limited budget ({c_balls} balls / {c_time}"
                    " mins)."
                )

            if pep_talk:
                st.success(f"🗣️ **{caddie}'s Practice Strategy:** “{pep_talk}”")
                render_caddie_voice_player(
                    pep_talk,
                    selected_persona_key,
                    label=f"Hear {caddie}'s Practice Strategy",
                )

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

            drill_weights = _practice_drill_weights(diag, active_drills)
            drill_ball_alloc = _allocate_integer(alloc_balls, drill_weights)
            drill_time_alloc = _allocate_integer(alloc_time, drill_weights)

            for idx, d_name in enumerate(active_drills):
                schematic = DRILL_SCHEMATICS.get(
                    d_name, DRILL_SCHEMATICS["Alignment Stick Gate Drill"]
                )

                balls_per_drill = drill_ball_alloc[idx]
                time_per_drill = drill_time_alloc[idx]

                if is_pure_game:
                    label = (
                        "🎮 Interactive Target Game (Addressing:"
                        f" {p_miss if idx == 0 else (s_miss if s_miss else p_miss)})"
                    )
                elif d_name == p_drill:
                    label = f"Primary Highest-Priority Drill (Addressing: {p_miss})"
                else:
                    label = (
                        "Secondary Focus Drill (Addressing:"
                        f" {s_miss if s_miss else 'Performance Polish'})"
                    )

                with st.container(border=True):
                    st.markdown(f"### 🎯 Drill #{idx+1}: **{d_name}**")
                    st.markdown(f"🔥 **{label}**")
                    st.caption(
                        f"⚡ `{balls_per_drill} Balls` | `{time_per_drill} Mins` |"
                        f" `@~{res['sec_per_ball']}s/ball`"
                    )

                    st.markdown("**🎯 What This Drill Trains**")
                    render_indented_html(
                        DRILL_PURPOSES.get(
                            d_name,
                            "Build the movement pattern targeted by this drill and make it repeatable under a normal pre-shot routine.",
                        )
                    )

                    st.markdown("**📏 Objective Pre/Post Test**")
                    kpi = get_drill_kpi(d_name)
                    st.markdown(f"**{kpi['name']}** — {kpi['test']}")
                    st.caption(
                        f"Success = {kpi['success']}  •  Pass target: {kpi['target']}/10. "
                        "Run this 10-rep test before the drill and repeat the same test after practice."
                    )

                    st.markdown("**🛠️ Range Equipment Needed**")
                    equip_items = re.split(r",\s*(?![^()]*\))", schematic["equipment"])
                    render_indented_ul(equip_items)

                    st.markdown("**📖 Step-by-Step Coaching Guide**")
                    render_instruction_steps(schematic["vivid_description"], d_name)

                    st.markdown("**📈 How to Progress the Drill**")
                    render_indented_html(
                        CATEGORY_PROGRESSION.get(
                            _drill_category(d_name), CATEGORY_PROGRESSION["general"]
                        )
                    )

                    st.markdown("**🧠 Mental Analogy**")
                    render_indented_html(schematic["analogy"])

                    st.info(schematic["pro_tip"])

            gm_balls = res["game_balls"]
            gm_time = res["game_time"]
            if gm_balls > 0 and gm_time > 0 and not is_pure_game:
                st.markdown("---")
                with st.container(border=True):
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

                    st.markdown("**📏 Objective Transfer Test**")
                    st.markdown("**Decision + routine transfer** — score 10 one-ball scenarios.")
                    st.caption(
                        "Success = a clear club/target decision, full routine, committed swing, and a playable outcome. "
                        "Pass target: 7/10. Do not hit a mulligan after a miss."
                    )

                    st.markdown("**🛠️ Range Equipment Needed**")
                    render_indented_ul([
                        "Full Golf Bag (All Clubs)",
                        "Laser Rangefinder or Target Flags",
                        "Pre-shot Routine Line",
                    ])

                    st.markdown("**🎯 What This Drill Trains**")
                    render_indented_html(
                        "Transfer the technical and mental work from the session into realistic one-ball, one-decision course behavior."
                    )

                    st.markdown("**📖 Step-by-Step Coaching Guide**")
                    pressure_text = (
                        "SETUP: Pick 3–5 different range targets that represent different on-course shots. "
                        "Assign a club, target, and imaginary hole situation before each ball; do not hit the same club twice in a row unless the simulated hole calls for it. "
                        "EXECUTION: Step completely away from the ball between reps. Go through your normal yardage/target decision, rehearsal, alignment, and pre-shot routine, then hit one ball only. "
                        "After the shot, score the decision and execution before choosing the next scenario. "
                        "SUCCESS: You commit to a clear target and club before every shot, complete the same routine each time, and produce a playable result without reverting to rapid-fire range habits. "
                        "AVOID: Hitting mulligans, repeating the same club immediately after a poor shot, or changing the target after address. The point is to live with one decision and one result, just like on the course."
                    )
                    render_instruction_steps(pressure_text, "Target Course Pressure Simulation")

                    st.markdown("**📈 How to Progress the Drill**")
                    render_indented_html(
                        "Start with 5 unscored simulated holes, then create a 9-shot or 18-shot game where each ball earns a simple result (good decision/playable shot, neutral, or penalty-level miss). Add consequences only after the routine stays consistent."
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

            with st.container(border=True):
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

            # ---------------------------------------------------------
            # END-OF-PRACTICE FEEDBACK — close the loop without requiring
            # the golfer to begin another round first.
            # ---------------------------------------------------------
            _init_history()
            _practice_rows = st.session_state.get("practice_history", [])
            _current_log = _practice_rows[-1] if _practice_rows else None

            with st.container(border=True):
                st.markdown("### ✅ Log This Practice Session")
                st.caption(
                    "When you finish the plan, record how much you completed and whether "
                    "the prescribed work helped. Birdie Buddy will use this feedback in "
                    "your practice history and future progress tracking."
                )

                if _current_log:
                    _logged_drill = (
                        res.get("resolved_primary_drill")
                        or _current_log.get("Primary Drill")
                        or diag.get("recommended_primary_drill", "your primary drill")
                    )
                    st.markdown(f"**Primary practice focus:** `{_logged_drill}`")
                    primary_kpi = get_drill_kpi(_logged_drill)
                    st.markdown(
                        f"**Objective test:** {primary_kpi['name']} — {primary_kpi['test']}"
                    )
                    st.caption(
                        f"Count a success when: {primary_kpi['success']} Pass target: {primary_kpi['target']}/10."
                    )

                    _completion_options = ["Not yet", "Yes, partially", "Yes, fully"]
                    _existing_completion = str(
                        _current_log.get("Drill Completed?", "") or ""
                    ).strip()
                    # Backward compatibility with older wording used by previous builds.
                    _completion_aliases = {
                        "Yes, a little": "Yes, partially",
                        "Skipped": "Not yet",
                    }
                    _existing_completion = _completion_aliases.get(
                        _existing_completion, _existing_completion
                    )
                    _completion_index = (
                        _completion_options.index(_existing_completion)
                        if _existing_completion in _completion_options
                        else 0
                    )

                    _existing_effectiveness = _current_log.get(
                        "Fix Effectiveness (1-5)", ""
                    )
                    try:
                        _effectiveness_default = int(float(_existing_effectiveness))
                        _effectiveness_default = max(1, min(5, _effectiveness_default))
                    except (TypeError, ValueError):
                        _effectiveness_default = 3

                    log_col1, log_col2 = st.columns(2)
                    with log_col1:
                        practice_completed = st.selectbox(
                            "How much of the practice plan did you complete?",
                            _completion_options,
                            index=_completion_index,
                            key="end_practice_completed",
                        )
                    with log_col2:
                        practice_effectiveness = st.slider(
                            "How effective did the practice feel?",
                            min_value=1,
                            max_value=5,
                            value=_effectiveness_default,
                            key="end_practice_effectiveness",
                            help=(
                                "1 = no noticeable benefit, 3 = some improvement, "
                                "5 = clear improvement you would keep practicing."
                            ),
                            disabled=practice_completed == "Not yet",
                        )

                    def _history_int(key, default=0):
                        try:
                            raw = _current_log.get(key, "")
                            if raw in (None, "", "N/A"):
                                return default
                            return max(0, min(10, int(float(raw))))
                        except Exception:
                            return default

                    existing_pre = _current_log.get("Baseline KPI (10)", "")
                    existing_post = _current_log.get("Post KPI (10)", "")
                    existing_objective = (
                        existing_pre not in (None, "", "N/A")
                        and existing_post not in (None, "", "N/A")
                    )
                    objective_test_done = st.checkbox(
                        "I completed the objective pre/post test",
                        value=existing_objective,
                        disabled=practice_completed == "Not yet",
                        help="Leave this unchecked if you only want to log completion/effectiveness. Birdie Buddy will not treat a missing test as a zero.",
                    )

                    baseline_kpi = post_kpi = None
                    if objective_test_done and practice_completed != "Not yet":
                        kpi_col1, kpi_col2 = st.columns(2)
                        with kpi_col1:
                            baseline_kpi = st.number_input(
                                "Pre-test successes (out of 10)",
                                min_value=0, max_value=10,
                                value=_history_int("Baseline KPI (10)", 0),
                                step=1,
                                help="Run the exact 10-rep objective test shown on the primary drill card before practice.",
                            )
                        with kpi_col2:
                            post_kpi = st.number_input(
                                "Post-test successes (out of 10)",
                                min_value=0, max_value=10,
                                value=_history_int("Post KPI (10)", 0),
                                step=1,
                                help="Repeat the same test after practice under the same conditions.",
                            )
                        gain = int(post_kpi) - int(baseline_kpi)
                        st.caption(
                            f"Objective change: **{gain:+d}/10**. Subjective effectiveness and objective change are both saved; neither replaces the other."
                        )

                    existing_saved = bool(
                        str(_current_log.get("Drill Completed?", "")).strip()
                    )
                    button_label = (
                        "💾 Update Practice Log"
                        if existing_saved
                        else "💾 Log Practice & Effectiveness"
                    )

                    if st.button(
                        button_label,
                        type="primary",
                        use_container_width=True,
                        key="log_practice_feedback_btn",
                    ):
                        effectiveness_to_save = (
                            "" if practice_completed == "Not yet" else practice_effectiveness
                        )
                        update_last_session_feedback(
                            practice_completed,
                            effectiveness_to_save,
                            baseline_kpi=(baseline_kpi if objective_test_done else ""),
                            post_kpi=(post_kpi if objective_test_done else ""),
                            practice_environment="; ".join(res.get("practice_areas", [])),
                            available_equipment="; ".join(res.get("equipment", [])),
                            practice_allocation=(
                                f"{int(res.get('grind_pct', 0)*100)}% controlled / "
                                f"{int(res.get('game_pct', 0)*100)}% transfer"
                            ),
                            actual_primary_drill=res.get("resolved_primary_drill") or diag.get("recommended_primary_drill", ""),
                        )
                        st.session_state["practice_feedback_saved"] = True
                        st.rerun()

                    if existing_saved:
                        saved_completion = _current_log.get("Drill Completed?", "")
                        saved_effectiveness = _current_log.get("Fix Effectiveness (1-5)", "")
                        if saved_effectiveness not in (None, ""):
                            objective_text = ""
                            try:
                                saved_gain = _current_log.get("Objective Gain", "")
                                if saved_gain not in (None, "", "N/A"):
                                    objective_text = f" • Objective change **{int(float(saved_gain)):+d}/10**"
                            except Exception:
                                objective_text = ""
                            st.success(
                                f"Practice logged: **{saved_completion}** • "
                                f"Effectiveness **{saved_effectiveness}/5**{objective_text}"
                            )
                        else:
                            st.info(f"Practice status logged: **{saved_completion}**")
                else:
                    st.info(
                        "Complete the round diagnosis first so Birdie Buddy has a "
                        "practice session to attach this feedback to."
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


# -------------------------------------------------------------
# PROGRESS & TRENDS — intentionally placed after the current-round
# diagnosis, practice plan, and practice-feedback workflow.
# -------------------------------------------------------------
_progress_df = load_history_df()
render_progress_trends(_progress_df)
