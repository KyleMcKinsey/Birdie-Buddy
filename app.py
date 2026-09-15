import json
from datetime import datetime
import google.generativeai as genai
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Birdie Buddy (Phase 1 MVP)", page_icon="⛳", layout="wide"
)

# App Header
st.title("⛳ Birdie Buddy (Phase 1 MVP)")
st.caption(
    "AI Golf Caddie & Practice Asset Allocator powered by Gemini | Strategic AI Assistant"
)

# Initialize Session State
if "df_history" not in st.session_state:
    st.session_state.df_history = pd.DataFrame(
        columns=[
            "Date/Time",
            "Primary Fault",
            "Primary Drill",
            "Secondary Fault",
            "Secondary Drill",
            "Practice Mode",
            "Total Balls",
            "Total Time (mins)",
            "ROI Strategy",
        ]
    )

if "latest_advice" not in st.session_state:
    st.session_state.latest_advice = None

# Sidebar Controls
st.sidebar.header("⚙️ Caddie Configuration")
api_key = st.sidebar.text_input(
    "Gemini API Key", type="password", help="Enter your Google Gemini API key"
)

caddie_persona = st.sidebar.selectbox(
    "Choose Caddie Persona 🧙",
    ["Bogey-Wan Kenobi", "Captain Hack Sparrow", "Dr. Pure Strikeman"],
    help="Select the tone and flavor of your AI Caddie.",
)

st.sidebar.markdown("---")
st.sidebar.header("📁 Log Management")

if st.sidebar.button("🗑️ Clear Practice History"):
    st.session_state.df_history = pd.DataFrame(
        columns=[
            "Date/Time",
            "Primary Fault",
            "Primary Drill",
            "Secondary Fault",
            "Secondary Drill",
            "Practice Mode",
            "Total Balls",
            "Total Time (mins)",
            "ROI Strategy",
        ]
    )
    st.session_state.latest_advice = None
    st.sidebar.success("Practice log cleared!")

if not st.session_state.df_history.empty:
    csv_data = st.session_state.df_history.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="📥 Export History (CSV)",
        data=csv_data,
        file_name="birdie_buddy_practice_log.csv",
        mime="text/csv",
    )

# Main Form Input & AI Caddie Analyzer
st.subheader("🤖 Consult Your AI Caddie")

with st.form("caddie_form"):
    col1, col2 = st.columns(2)

    with col1:
        golfer_issues = st.text_area(
            "What is going wrong with your swing or game today?",
            placeholder="e.g., I'm slicing my driver, missing 5-foot putts to the right, and tilting mentally after bad holes.",
            height=120,
        )
        total_balls = st.number_input(
            "Available Practice Balls ⛳",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
        )

    with col2:
        practice_goals = st.text_area(
            "Target Goals or Upcoming Match Focus (Optional)",
            placeholder="e.g., Preparing for a weekend tournament, need tight iron dispersion.",
            height=120,
        )
        total_time = st.number_input(
            "Available Time (minutes) ⏱️",
            min_value=15,
            max_value=300,
            value=60,
            step=15,
        )

    submit_button = st.form_submit_button("🏌️ Generate Practice Plan")

# Handle AI Generation
if submit_button:
    if not api_key:
        st.error(
            "Please enter a valid Gemini API Key in the sidebar to generate a practice plan."
        )
    elif not golfer_issues.strip():
        st.warning(
            "Please describe what issues or faults you are experiencing in your game."
        )
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")

            persona_prompts = {
                "Bogey-Wan Kenobi": "You are Bogey-Wan Kenobi, a wise, calm, Star Wars-inspired master caddie who speaks with mental clarity and strategic poise.",
                "Captain Hack Sparrow": "You are Captain Hack Sparrow, a witty, chaotic pirate caddie who talks about plundering strokes and green target treasure.",
                "Dr. Pure Strikeman": "You are Dr. Pure Strikeman, an analytical, high-performance tour coach focused on biomechanics and high-ROI practice distribution.",
            }

            system_context = persona_prompts.get(
                caddie_persona, persona_prompts["Bogey-Wan Kenobi"]
            )

            prompt = f"""
{system_context}

Analyze the golfer's issues and allocate practice assets for maximum stroke reduction ROI.

Golfer Issues: {golfer_issues}
Golfer Goals: {practice_goals}
Resource Constraints: {total_balls} balls, {total_time} minutes.

Return ONLY a valid JSON object with exactly these keys (do not swap fault and drill fields):
{{
  "caddie_intro": "Persona response in character analyzing the situation",
  "primary_fault": "Concise name of the primary swing/mental fault identified",
  "primary_drill": "Name and step of the corrective drill for the primary fault",
  "secondary_fault": "Secondary fault identified (or 'N/A' if none)",
  "secondary_drill": "Corrective drill for secondary fault (or 'N/A' if none)",
  "practice_mode": "Pure Grind Mode (100% Technical Drill) OR Pure Game Mode (100% Target Pressure) OR Combination / Hybrid (AI Balanced)",
  "roi_strategy": "1-2 sentence high-level strategic reasoning explaining why this plan yields maximum stroke reduction ROI"
}}
"""

            with st.spinner("Caddie is calculating your practice plan..."):
                response = model.generate_content(prompt)
                clean_json = (
                    response.text.strip()
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )
                data = json.loads(clean_json)

                # Store latest structured advice in session
                st.session_state.latest_advice = data

                # Append entry cleanly to DataFrame
                new_entry = {
                    "Date/Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Primary Fault": data.get("primary_fault", "N/A"),
                    "Primary Drill": data.get("primary_drill", "N/A"),
                    "Secondary Fault": data.get("secondary_fault", "N/A"),
                    "Secondary Drill": data.get("secondary_drill", "N/A"),
                    "Practice Mode": data.get("practice_mode", "Hybrid"),
                    "Total Balls": total_balls,
                    "Total Time (mins)": total_time,
                    "ROI Strategy": data.get("roi_strategy", "N/A"),
                }

                st.session_state.df_history = pd.concat(
                    [st.session_state.df_history, pd.DataFrame([new_entry])],
                    ignore_index=True,
                )
                st.success("Practice plan generated and logged successfully!")

        except Exception as e:
            st.error(f"Error communicating with AI: {str(e)}")

# Render Latest AI Recommendation Banner
if st.session_state.latest_advice:
    advice = st.session_state.latest_advice
    st.markdown("---")
    st.subheader(f"🧙 {caddie_persona}'s Recommendation")
    st.info(advice.get("caddie_intro", ""))

    res_col1, res_col2, res_col3 = st.columns(3)
    with res_col1:
        st.markdown(
            f"**🎯 Primary Fault:** {advice.get('primary_fault', 'N/A')}"
        )
        st.markdown(
            f"**🛠️ Primary Drill:** {advice.get('primary_drill', 'N/A')}"
        )
    with res_col2:
        st.markdown(
            f"**⚠️ Secondary Fault:** {advice.get('secondary_fault', 'N/A')}"
        )
        st.markdown(
            f"**🔧 Secondary Drill:** {advice.get('secondary_drill', 'N/A')}"
        )
    with res_col3:
        st.markdown(
            f"**🎮 Mode:** {advice.get('practice_mode', 'Combination / Hybrid')}"
        )
        st.markdown(
            f"**📈 ROI Strategy:** {advice.get('roi_strategy', 'N/A')}"
        )

st.markdown("---")

# Main Screen Practice History Table
st.subheader("📊 Practice History Log")
df_history = st.session_state.df_history

if df_history.empty:
    st.info(
        "No practice sessions logged yet. Use the form above to consult your caddie!"
    )
else:
    df_display = df_history.copy()

    # 1. Format Date in-place so it stays in column #1 position
    if "Date/Time" in df_display.columns:
        df_display["Date/Time"] = (
            df_display["Date/Time"].astype(str).str.split(" ").str[0]
        )
        df_display = df_display.rename(columns={"Date/Time": "Date"})

    # 2. Clean up unwanted columns
    cols_to_drop = [
        c for c in ["Caddie Persona", "Caddie"] if c in df_display.columns
    ]
    if cols_to_drop:
        df_display = df_display.drop(columns=cols_to_drop)

    def style_practice_log(df):
        def color_mode(val):
            v = str(val)
            if "Grind" in v:
                return "background-color: #ffedd5; color: #9a3412; font-weight: bold;"
            elif "Game" in v:
                return "background-color: #d1fae5; color: #065f46; font-weight: bold;"
            elif "Combination" in v or "Hybrid" in v:
                return "background-color: #dbeafe; color: #1e40af; font-weight: bold;"
            return ""

        def color_drills(val):
            if val and str(val) != "N/A":
                return "background-color: #e0e7ff; color: #3730a3; font-weight: bold;"
            return "color: #9ca3af; font-style: italic;"

        def color_faults(val):
            if val and str(val) != "N/A":
                return "background-color: #fef3c7; color: #92400e; font-weight: bold;"
            return "color: #9ca3af; font-style: italic;"

        try:
            styler = df.style

            if "Practice Mode" in df.columns:
                styler = styler.map(color_mode, subset=["Practice Mode"])

            drill_cols = [
                c
                for c in ["Primary Drill", "Secondary Drill"]
                if c in df.columns
            ]
            if drill_cols:
                styler = styler.map(color_drills, subset=drill_cols)

            fault_cols = [
                c
                for c in ["Primary Fault", "Secondary Fault"]
                if c in df.columns
            ]
            if fault_cols:
                styler = styler.map(color_faults, subset=fault_cols)

            return styler
        except Exception:
            return df

    styled_df = style_practice_log(df_display)

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.TextColumn("Date 📅", width="small"),
            "Primary Fault": st.column_config.TextColumn(
                "Primary Fault 🎯", width="medium"
            ),
            "Primary Drill": st.column_config.TextColumn(
                "Primary Drill 🛠️", width="medium"
            ),
            "Secondary Fault": st.column_config.TextColumn(
                "Secondary Fault ⚠️", width="medium"
            ),
            "Secondary Drill": st.column_config.TextColumn(
                "Secondary Drill 🔧", width="medium"
            ),
            "Practice Mode": st.column_config.TextColumn(
                "Mode 🎮", width="small"
            ),
            "Total Balls": st.column_config.NumberColumn(
                "Balls ⛳", format="%d", width="small"
            ),
            "Total Time (mins)": st.column_config.NumberColumn(
                "Time (m) ⏱️", format="%d", width="small"
            ),
            "ROI Strategy": st.column_config.TextColumn(
                "ROI Fix 📈", width="large"
            ),
        },
    )
