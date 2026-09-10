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
        Analyze shot errors using Jedi terminology and wise guidance.
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
        Analyze shot errors using wizarding world terminology and spell metaphors.
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
        Analyze shot errors as if evaluating high-stakes tactical intelligence.
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
        Analyze shot errors using nautical pirate metaphors.
        """,
    },
}

# -------------------------------------------------------------
# EXPANDED PGA TOUR KNOWLEDGE BASE & SCHEMATICS
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
        ),
        "analogy": (
            "🚂 **The Railroad Track & Slanted Roof:** Think of your swing as a"
            " bullet train moving through a narrow glass tunnel. If you swing"
            " over-the-top, you shatter the glass on the upper slanted roof"
            " (Stick #2)."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Keep 60% of your weight grounded in your"
            " lead heel during impact. Do not fight to hit the ball—focus purely"
            " on sweeping the turf cleanly."
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
            " loaded, chest pointed away from the target before starting the"
            " downswing."
        ),
        "analogy": (
            "🏹 **The Coiled Archer's Bow:** Pulling the bowstring back is your"
            " backswing. Holding the pause at the top is holding your aim"
            " steady before release."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Count 'One-One-Thousand' silently at the"
            " top before starting down to initiate downswing with lower body."
        ),
    },
    "Tee Gate Drill": {
        "equipment": "4 Standard Golf Tees",
        "image_url": "https://images.unsplash.com/photo-1593111774601-dfbce3206564?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Step up to the ball on the turf and press two tees flush into the"
            " ground just 1/4 inch beyond the toe and heel of your clubhead."
            " Then, move 3 inches down the target line and plant two more tees"
            " spaced exactly one ball-width apart to create a tight exit corridor."
        ),
        "analogy": (
            "🛩️ **Aircraft Runway:** Your clubhead is an airplane landing on a"
            " narrow runway. If your club path drifts in or out, you clip the"
            " runway guardrails (the tees)."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Soften wrist grip pressure to 4/10. Let"
            " the weight of the clubhead drop through the gate organically."
        ),
    },
    "Towel Under Armpits Drill": {
        "equipment": "1 Microfiber Golf Towel",
        "image_url": "https://images.unsplash.com/photo-1535131749006-b7f58c99034b?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Tuck a single golf towel horizontally across your chest, clamping it"
            " snugly under both armpits. Take half-swings focusing on keeping"
            " your lead and trail upper arms pinned against your torso"
            " throughout rotation. If your arms disconnect or 'chicken-wing',"
            " the towel drops instantly."
        ),
        "analogy": (
            "📦 **The Solid Core Cylinder:** Your arms and torso form a single"
            " solid unit like a spinning turbine. The arms do not flap"
            " independently."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Focus on turning your sternum toward the"
            " target rather than pulling the club through with your hands."
        ),
    },
    "Coin Strike Low-Point Drill": {
        "equipment": "1 Small Coin (Quarter or Ball Marker)",
        "image_url": "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Place a quarter flat on the turf exactly 2 inches in front of"
            " where your ball would sit. Make smooth, three-quarter iron swings"
            " with the goal of brushing the turf so your divot starts AT the"
            " coin, sending the coin skipping forward."
        ),
        "analogy": (
            "🔪 **Chopping Wood vs. Shoveling:** Stop trying to scoop the ball"
            " into the air. Think of compressing the ball down into the turf"
            " ahead."
        ),
        "pro_tip": (
            "🏆 **PGA Tour Pro Tip:** Ensure your chest buttons are positioned"
            " directly over or slightly ahead of the coin at the moment of"
            " impact."
        ),
    },
    "Split-Hands Release Drill": {
        "equipment": "Mid-Iron (7-Iron)",
        "image_url": "https://images.unsplash.com/photo-1592919505780-303950717480?q=80&w=1000&auto=format&fit=crop",
        "vivid_description": (
            "Grip your 7-iron normally with your lead hand at the top, but"
            " separate your trail hand 3 inches lower down the grip (like"
            " holding a hockey stick). Take slow waist-high swings to feel your"
            " lead forearm rotate naturally over the trail forearm."
        ),
        "analogy": (
            "🏒 **The Hockey Slap Shot:** Splitting your hands exaggerates forearm"
            " crossover andSorry, something went wrong. Please try your request again.
