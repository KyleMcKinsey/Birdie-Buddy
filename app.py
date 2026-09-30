from datetime import datetime
import base64
import hashlib
import html
import io
import json
import os
import time
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import google.generativeai as genai
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

st.set_page_config(
    page_title="Birdie Buddy", page_icon="⛳", layout="wide"
)

st.markdown(
    """
    <style>
    /* Birdie Buddy dashboard canvas:
       wide enough for the approved drill layout without becoming edge-to-edge. */
    .stMainBlockContainer,
    [data-testid="stMainBlockContainer"] {
        max-width: 1160px !important;
        padding-left: 1.6rem !important;
        padding-right: 1.6rem !important;
        padding-top: 1.15rem !important;
    }

    /* Give dashboard cards separation without making the page feel oversized. */
    [data-testid="stHorizontalBlock"] {
        gap: 1rem;
    }

    /* A little breathing room around bordered Streamlit panels.
       The bottom margin is important when wrapped/multi-line content
       makes a card taller than neighboring cards. */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        margin-bottom: .55rem !important;
    }

    /* Expanders are bordered controls too; keep a small safety gap
       so their outline never kisses the card immediately above/below. */
    [data-testid="stExpander"] {
        margin-top: .20rem !important;
        margin-bottom: .55rem !important;
    }

    /* Tabs: segmented-control feel, matching the approved drill preview. */
    [data-baseweb="tab-list"] {
        gap: 0 !important;
        border-bottom: 1px solid rgba(100,116,139,.42);
    }
    button[data-baseweb="tab"] {
        min-height: 42px;
        padding-left: .85rem !important;
        padding-right: .85rem !important;
        border: 1px solid rgba(100,116,139,.42) !important;
        border-bottom: none !important;
        border-radius: 9px 9px 0 0 !important;
        background: rgba(15,23,42,.34) !important;
    }
    button[data-baseweb="tab"] p {
        font-size: .88rem !important;
        font-weight: 750 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
        color: white !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p {
        color: white !important;
    }

    /* Let action-button labels wrap so full caddie names stay visible. */
    div[data-testid="stButton"] button {
        height: auto !important;
        min-height: 2.3rem !important;
    }
    div[data-testid="stButton"] button p {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.15 !important;
        text-align: center !important;
    }

    /* Prevent metric-card content from looking like stacked narrow towers. */
