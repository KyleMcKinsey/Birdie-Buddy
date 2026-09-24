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
    "OB/Lost Balls",
    "3-Putts",
    "Failed Up-and-Downs",
    "Scrambling Opportunities",
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
    "Estimated Excess Strokes",
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
    ob_lost_balls=None,
    three_putts=None,
    failed_up_downs=None,
    scrambling_opportunities=None,
    problem_area="",
    miss_freq="",
    confidence=None,
    handicap=None,
    roi_priority="",
    roi_score=None,
    estimated_excess_strokes="",
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
        lines.append(f"Setup & Execution: {schematic['vivid_description']}")
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
def _interp_handicap_benchmark(handicap, benchmarks):
    """Linearly interpolate between published Shot Scope handicap benchmarks."""
    h = max(0.0, min(25.0, float(handicap or 0.0)))
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
                       ob_lost_balls=0, three_putts=0, failed_up_downs=0,
                       scrambling_opportunities=0, handicap=None):
    """Estimate handicap-relative practice ROI from round-level evidence.

    The excess-strokes figures are transparent model estimates, not literal
    Strokes Gained measurements. They estimate how many strokes the observed
    category is above the golfer's handicap benchmark. Shot-level SG remains
    the preferred evidence when available.
    """
    hcp = float(handicap or 0.0)
    score = 0.0
    reasons = []
    gaps = {}
    excess = {}

    # Direct penalty tax: this is the strongest round-level stroke evidence.
    penalty_bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["penalty_strokes"])
    if penalty_strokes is not None:
        penalty_gap = max(0.0, float(penalty_strokes) - penalty_bench)
        gaps["penalty_strokes_vs_handicap"] = round(float(penalty_strokes) - penalty_bench, 2)
        excess["Penalty / Trouble"] = round(penalty_gap, 2)
        if penalty_gap > 0:
            score += min(40.0, penalty_gap * 16.0)
            reasons.append(f"Penalty strokes {penalty_strokes:.1f} vs {penalty_bench:.1f} handicap benchmark = +{penalty_gap:.1f} excess strokes")

    # OB/lost balls explain trouble, but are not added again as full strokes.
    if ob_lost_balls:
        if penalty_strokes and ob_lost_balls >= penalty_strokes:
            reasons.append(f"{ob_lost_balls} OB/lost ball event(s) likely explain penalty leakage; not double-counted")
        else:
            score += min(10.0, ob_lost_balls * 5.0)
            reasons.append(f"{ob_lost_balls} OB/lost ball event(s) = direct trouble signal")

    # Three-putts: each event contains at least one extra putt versus a 2-putt,
    # so use the event count as a conservative direct-stroke estimate.
    if three_putts:
        excess["3-Putting"] = round(float(three_putts), 2)
        score += min(24.0, three_putts * 10.0)
        reasons.append(f"{three_putts} three-putt(s) = approximately {three_putts:.1f} avoidable stroke(s), before distance context")
    else:
        excess["3-Putting"] = 0.0

    # GIR: translate excess missed greens into a conservative stroke proxy.
    if gir is not None:
        gir_pct = float(gir) / 18.0 * 100.0
        gir_bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["gir_pct"])
        expected_gir = 18.0 * gir_bench / 100.0
        excess_missed_greens = max(0.0, expected_gir - float(gir))
        # 0.35 is deliberately conservative: a missed green is not an
        # automatic full stroke because short-game skill can recover it.
        gir_excess_strokes = excess_missed_greens * 0.35
        gir_gap = gir_pct - gir_bench
        gaps["gir_pct_vs_handicap"] = round(gir_gap, 1)
        excess["Approach / GIR"] = round(gir_excess_strokes, 2)
        if gir_gap < -15:
            score += 32.0
            reasons.append(f"GIR {gir_pct:.0f}% vs {gir_bench:.0f}% benchmark = ~{gir_excess_strokes:.1f} estimated excess approach strokes")
        elif gir_gap < -8:
            score += 22.0
            reasons.append(f"GIR {gir_pct:.0f}% vs {gir_bench:.0f}% benchmark = ~{gir_excess_strokes:.1f} estimated excess approach strokes")
        elif gir_gap < -3:
            score += 11.0
            reasons.append(f"GIR {gir_pct:.0f}% vs {gir_bench:.0f}% benchmark = ~{gir_excess_strokes:.1f} estimated excess approach strokes")
        elif gir_gap >= 0:
            reasons.append(f"GIR {gir_pct:.0f}% is at/above the {gir_bench:.0f}% handicap benchmark")
    else:
        excess["Approach / GIR"] = 0.0

    # Short game: compare observed save rate to the handicap benchmark, then
    # estimate excess failed saves. One excess failure is modeled as 0.7 stroke
    # because a successful up-and-down is not always par-saving from identical lies.
    if scrambling_opportunities and failed_up_downs is not None:
        opps = max(1, int(scrambling_opportunities))
        fails = min(opps, int(failed_up_downs))
        observed_ud = (opps - fails) / opps * 100.0
        ud_bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["up_down_pct"])
        expected_fails = opps * (1.0 - ud_bench / 100.0)
        excess_failures = max(0.0, float(fails) - expected_fails)
        ud_excess_strokes = excess_failures * 0.70
        ud_gap = observed_ud - ud_bench
        gaps["up_down_pct_vs_handicap"] = round(ud_gap, 1)
        excess["Short Game / Scrambling"] = round(ud_excess_strokes, 2)
        if ud_gap < -15:
            score += 24.0
            reasons.append(f"Up-and-down {observed_ud:.0f}% vs {ud_bench:.0f}% benchmark = ~{ud_excess_strokes:.1f} estimated excess short-game strokes")
        elif ud_gap < -8:
            score += 16.0
            reasons.append(f"Up-and-down {observed_ud:.0f}% vs {ud_bench:.0f}% benchmark = ~{ud_excess_strokes:.1f} estimated excess short-game strokes")
        elif ud_gap < -3:
            score += 8.0
            reasons.append(f"Up-and-down {observed_ud:.0f}% vs {ud_bench:.0f}% benchmark = ~{ud_excess_strokes:.1f} estimated excess short-game strokes")
        else:
            reasons.append(f"Up-and-down {observed_ud:.0f}% is near/above the {ud_bench:.0f}% handicap benchmark")
    else:
        excess["Short Game / Scrambling"] = 0.0
        if failed_up_downs:
            reasons.append("Failed up-and-downs supplied without total opportunities — add opportunities for excess-stroke estimate")

    # Total putts: excess putts are a useful category signal, but are kept
    # separate from 3-putts so the UI can show why the putting diagnosis exists.
    if putts is not None:
        putt_bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["putts_round"])
        putt_gap = max(0.0, float(putts) - putt_bench)
        gaps["putts_vs_handicap"] = round(float(putts) - putt_bench, 1)
        excess["Putting / Total"] = round(putt_gap, 2)
        if putt_gap >= 5:
            score += 11.0
            reasons.append(f"{putts} putts vs {putt_bench:.1f} benchmark = +{putt_gap:.1f} excess putts; check 3-putts and approach proximity")
        elif putt_gap >= 3:
            score += 6.0
            reasons.append(f"{putts} putts vs {putt_bench:.1f} benchmark = +{putt_gap:.1f} excess putts")
        elif putt_gap <= 0:
            reasons.append(f"{putts} putts are at/below the {putt_bench:.1f} handicap benchmark")
    else:
        excess["Putting / Total"] = 0.0

    # FIR remains a weak signal; estimate no strokes from accuracy alone.
    if fairways_hit is not None:
        fir_pct = float(fairways_hit) / 14.0 * 100.0
        fir_bench = _interp_handicap_benchmark(hcp, HANDICAP_BENCHMARKS["fir_pct"])
        fir_gap = fir_pct - fir_bench
        gaps["fir_pct_vs_handicap"] = round(fir_gap, 1)
        excess["Driving / FIR"] = 0.0
        if fir_gap < -15 and (penalty_strokes or ob_lost_balls):
            score += 8.0
            reasons.append(f"FIR {fir_pct:.0f}% vs {fir_bench:.0f}% benchmark plus trouble = tee-shot risk; no strokes credited from FIR alone")
        elif fir_gap < -10:
            score += 2.0
            reasons.append(f"FIR {fir_pct:.0f}% is below the {fir_bench:.0f}% benchmark, but accuracy alone is weak ROI evidence")

    total_excess = round(sum(excess.values()), 2)
    score = round(min(100.0, score), 1)
    if score >= 45:
        tier = "CRITICAL — Direct / Excess Score Leak"
    elif score >= 30:
        tier = "HIGH — Major Scoring Opportunity"
    elif score >= 18:
        tier = "MEDIUM — Worth Targeting"
    else:
        tier = "LOW — Near Handicap Benchmark / Need More Evidence"

    excess_display = " | ".join(
        f"{k}: {v:.1f}" for k, v in excess.items() if v > 0
    ) or "No material excess-stroke estimate"
    return {
        "score": score,
        "tier": tier,
        "reasons": reasons,
        "gaps": gaps,
        "excess_strokes": excess,
        "total_excess_strokes": total_excess,
        "excess_display": excess_display,
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

    st.markdown("##### 🎯 Scoring Events (high-value hidden-fault signals)")
    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    with col_e1:
        ob_lost_balls = st.number_input(
            "OB / Lost Balls", min_value=0, max_value=20, value=0, step=1,
            help="Count actual out-of-bounds or lost-ball events separately from total penalty strokes.",
        )
    with col_e2:
        three_putts = st.number_input(
            "3-Putts", min_value=0, max_value=18, value=0, step=1,
            help="A concrete extra-stroke event; more useful for ROI than total putts alone.",
        )
    with col_e3:
        failed_up_downs = st.number_input(
            "Failed Up-and-Downs", min_value=0, max_value=18, value=0, step=1,
            help="Count missed up-and-down opportunities after missing the green.",
        )
    with col_e4:
        scrambling_opportunities = st.number_input(
            "Scrambling Opportunities", min_value=0, max_value=18, value=0, step=1,
            help="Number of holes where you missed the green and had a realistic up-and-down opportunity. Needed for handicap-relative short-game benchmarking.",
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
            st.session_state["round_ob_lost_balls"] = ob_lost_balls
            st.session_state["round_three_putts"] = three_putts
            st.session_state["round_failed_up_downs"] = failed_up_downs
            st.session_state["round_scrambling_opportunities"] = scrambling_opportunities
            st.session_state["round_handicap"] = handicap

            round_numbers_block = f"""
            - Score: {round_score if round_score else 'Not provided'}
            - Fairways Hit: {fairways_hit if fairways_hit else 'Not provided'} (out of ~14 driving holes on a typical 18)
            - Greens in Regulation: {gir if gir else 'Not provided'} (out of 18)
            - Putts: {putts if putts else 'Not provided'}
            - Penalty Strokes: {penalty_strokes if penalty_strokes else 'Not provided'}
            - OB / Lost Balls: {ob_lost_balls if ob_lost_balls else 'Not provided'}
            - 3-Putts: {three_putts if three_putts else 'Not provided'}
            - Failed Up-and-Downs: {failed_up_downs if failed_up_downs else 'Not provided'}
            - Scrambling Opportunities: {scrambling_opportunities if scrambling_opportunities else 'Not provided'}
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
            - OB/Lost Balls → direct score leak; probe the cause if the story does not explain it.
            - 3-Putts → concrete extra-stroke event; probe distance control/first-putt leave.
            - Failed Up-and-Downs → short-game opportunity; interpret relative to handicap and GIR.
            - Penalty Strokes → direct score leak; identify whether tee strategy or decisions caused them.
            - GIR well below ~30% → possible approach-game leak.
            - Putts at 35+ → investigate only after checking GIR and 3-putts.
            - Fairways below ~50% → investigate only if misses create meaningful scoring damage.
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
            _ob = st.session_state.get("round_ob_lost_balls")
            _3p = st.session_state.get("round_three_putts")
            _ud = st.session_state.get("round_failed_up_downs")
            _scramble_opps = st.session_state.get("round_scrambling_opportunities")

            roi_data = calculate_score_roi(
                _rs, _fh, _gir, _pt, _pen, _ob, _3p, _ud, _scramble_opps,
                st.session_state.get("round_handicap")
            )

            # ---------------------------------------------------------
            # VISIBLE HANDICAP-RELATIVE ROI BREAKDOWN
            # ---------------------------------------------------------
            st.markdown("### 📊 Where Your Strokes Are Actually Leaking")
            st.caption(
                "Handicap-relative model estimate. These are diagnostic estimates, not measured Strokes Gained."
            )

            total_excess = roi_data["total_excess_strokes"]
            priority_col, total_col = st.columns([2, 1])
            with priority_col:
                st.markdown(f"**ROI Priority:** {roi_data['tier']}")
                st.progress(min(1.0, roi_data["score"] / 100.0))
                st.caption(f"Practice ROI score: {roi_data['score']:.1f} / 100")
            with total_col:
                st.metric("Estimated Excess Strokes", f"+{total_excess:.1f}")

            # Show only categories that have usable evidence, while retaining
            # zero-value categories when the golfer supplied the corresponding stat.
            category_labels = {
                "Penalty / Trouble": "Penalty / Trouble",
                "3-Putting": "3-Putting",
                "Approach / GIR": "Approach / GIR",
                "Short Game / Scrambling": "Short Game / Scrambling",
                "Putting / Total": "Putting / Total",
                "Driving / FIR": "Driving / FIR",
            }
            visible_rows = []
            for key, label in category_labels.items():
                value = roi_data["excess_strokes"].get(key, 0.0)
                if value > 0 or key in {"Driving / FIR"} and _fh is not None:
                    visible_rows.append({
                        "Category": label,
                        "Estimated Excess Strokes": round(float(value), 2),
                    })

            if visible_rows:
                roi_df = pd.DataFrame(visible_rows).sort_values(
                    "Estimated Excess Strokes", ascending=False
                )
                st.dataframe(
                    roi_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Category": st.column_config.TextColumn("Scoring Category"),
                        "Estimated Excess Strokes": st.column_config.NumberColumn(
                            "Est. Excess Strokes", format="+%.2f"
                        ),
                    },
                )

                positive_rows = roi_df[roi_df["Estimated Excess Strokes"] > 0]
                if not positive_rows.empty:
                    top = positive_rows.iloc[0]
                    st.info(
                        f"**Largest modeled leak:** {top['Category']} at approximately "
                        f"+{top['Estimated Excess Strokes']:.2f} excess stroke(s) versus your handicap benchmark."
                    )

            if roi_data["reasons"]:
                with st.expander("Why the model reached this conclusion", expanded=False):
                    for reason in roi_data["reasons"]:
                        st.write(f"• {reason}")

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
            OB/Lost Balls={_ob if _ob else 'N/A'}, 3-Putts={_3p if _3p else 'N/A'}, Failed Up-and-Downs={_ud if _ud else 'N/A'}, Scrambling Opportunities={_scramble_opps if _scramble_opps else 'N/A'},
            Handicap={st.session_state.get('round_handicap') or 'N/A'}
            Score-ROI Engine: {roi_data['tier']} | {roi_data['score']}/100
            Score-ROI Evidence: {'; '.join(roi_data['reasons']) if roi_data['reasons'] else 'No strong numerical leak detected'}
            Estimated Excess Strokes: {roi_data['excess_display']} | Total model estimate: {roi_data['total_excess_strokes']:.1f}
            """

            system_prompt = f"""
            {active_persona['system_instruction']}

            Act as an expert biomechanical, sports psychology, and strategic golf instructor AI.
            Analyze the user's round narrative, decision tree answers, and round numbers through a
            **Golf Value Chain ROI Lens** — the same "where does the value actually leak" logic used
            in a business value chain, applied to a round of golf. Every fault belongs to exactly one
            of these four sequential stages:

            1. **Off-the-Tee Strategy (Primary Drive):** driver/tee shot accuracy and strategy. If this
               stage is leaking (e.g. low Fairways Hit), probe whether those misses create actual
               scoring damage. Do not assume tee shots are the highest-ROI fix without score evidence.
            2. **Approach Precision (Mid Game):** iron/approach shot accuracy into greens (GIR).
            3. **Scoring/Scrambling (Short Game/Putting):** chipping, pitching, sand, and putting —
               converting positions already gained into a low score.
            4. **Mental Infrastructure (Support Systems):** routine, composure, decision-making, and
               recovery after a bad shot or hole — the system that supports the other three stages.

            **Score-ROI Evidence Hierarchy:** Direct score events (OB/lost balls, penalty strokes, 3-putts)
            are stronger evidence of lost strokes than broad accuracy statistics. Failed up-and-downs
            are then interpreted against handicap/GIR context. FIR is only elevated when misses create
            meaningful trouble. Total putts are weak evidence unless supported by 3-putt frequency.

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
              "estimated_excess_strokes": "string — report the handicap-relative model estimate by category when supported; explicitly label it as an estimate, not measured Strokes Gained",
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
                    ob_lost_balls=_zero_to_blank(st.session_state.get("round_ob_lost_balls")),
                    three_putts=_zero_to_blank(st.session_state.get("round_three_putts")),
                    failed_up_downs=_zero_to_blank(st.session_state.get("round_failed_up_downs")),
                    scrambling_opportunities=_zero_to_blank(st.session_state.get("round_scrambling_opportunities")),
                    problem_area=st.session_state.get("club_category", ""),
                    miss_freq=st.session_state.get("miss_freq", ""),
                    confidence=diag_data.get("confidence_score", ""),
                    handicap=st.session_state.get("round_handicap"),
                    roi_priority=diag_data.get("roi_priority", roi_data.get("tier", "")),
                    roi_score=diag_data.get("roi_score", roi_data.get("score", "")),
                    estimated_excess_strokes=roi_data.get("excess_display", ""),
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

        st.markdown("**📖 Setup & Execution**")
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

        st.markdown("**📖 Setup & Execution**")
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
