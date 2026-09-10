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
    system_prompt = f"""
        {active_persona['system_instruction']}

        Analyze the user's input regarding a missed shot. Strictly evaluate errors against the 'Path/Face' domain (club path relative to target line, face angle relative to path). 
        Output strictly raw JSON matching this structure with no markdown formatting:
        {{
          "diagnosis_category": "Path/Face",
          "detected_miss": "string",
          "tom_shanks_response": "string (1-2 sentences max, matching your assigned movie character persona)",
          "confidence_score": 0.95,
          "recommended_grind_drill": "string"
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
          response.text.replace("```json", "").replace("
