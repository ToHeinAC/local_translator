"""Forest theme: palette + injectable CSS (copied from local_summarizer, see THIRD_PARTY_NOTICES).

Colors mirror ``.streamlit/config.toml``; the CSS re-asserts them because Streamlit's config alone
does not reach every widget.
"""

from string import Template

FOREST: dict[str, str] = {
    "bg": "#f6f7f2",
    "sidebar_bg": "#eaf0ec",
    "widget_bg": "#ffffff",
    "text": "#1a1f1c",
    "text_muted": "#5a6b5e",
    "primary": "#234637",
    "border": "#d4dbd6",
    "hover": "rgba(35,70,55,0.10)",
}

_FONTS = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600"
    "&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap"
)

_CSS = Template(
    """    <style>
    @import url('${fonts}');

    html, body {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 15px;
    }
    /* Catch ALL elements' color — overrides Streamlit's inline textColor from
       config.toml. Do NOT set font-family here: it breaks icon ligatures. */
    .stApp, .stApp * {
        color: ${text} !important;
    }
    [data-testid="stIconMaterial"],
    span.material-icons,
    span.material-icons-outlined,
    .material-symbols-rounded,
    .material-symbols-outlined,
    [class*="material-symbols"] {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }

    .stApp { background-color: ${bg} !important; }
    [data-testid="stSidebar"] { background-color: ${sidebar_bg} !important; }
    [data-testid="block-container"],
    [data-testid="stVerticalBlock"],
    section.main > div {
        background-color: ${bg} !important;
    }

    h1, h2, h3 {
        font-family: 'Libre Baskerville', Georgia, serif !important;
        font-weight: 700;
    }
    h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
    [data-testid="stSidebar"] h2 { white-space: nowrap; font-size: 1.25rem; }

    .stSelectbox > div > div,
    .stSelectbox > div > div > div {
        background-color: ${widget_bg} !important;
        color: ${text} !important;
        border-color: ${border} !important;
        border-radius: 6px !important;
    }

    .stButton > button {
        border-radius: 6px !important;
        font-weight: 500 !important;
        text-transform: none !important;
        font-size: 0.875rem !important;
        border: 1px solid ${border} !important;
        background-color: ${widget_bg} !important;
        color: ${text} !important;
        transition: background-color 0.15s ease, box-shadow 0.15s ease !important;
    }
    .stButton > button:hover {
        background-color: ${hover} !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.15) !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[kind="primary"]:hover {
        background-color: ${primary} !important;
        color: #ffffff !important;
        border-color: ${primary} !important;
    }
    /* The label lives in a nested <p>, which `.stApp *` would paint dark. */
    .stButton > button[kind="primary"] *,
    .stButton > button[kind="primary"]:hover * {
        color: #ffffff !important;
    }
    .stDownloadButton > button {
        background-color: ${widget_bg} !important;
        color: ${text} !important;
        border: 1px solid ${border} !important;
        border-radius: 6px !important;
    }

    /* File uploader (dropzone uses config secondaryBackgroundColor — force theme) */
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploader"] section {
        background-color: ${widget_bg} !important;
        border: 1px solid ${border} !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"],
    [data-testid="stFileUploaderDropzoneInstructions"] * {
        color: ${text_muted} !important;
    }
    [data-testid="stFileUploader"] button {
        background-color: ${bg} !important;
        color: ${text} !important;
        border: 1px solid ${border} !important;
    }

    /* Sidebar lang/logout: identical boxed buttons (not the transparent nav style) */
    [data-testid="stSidebar"] .st-key-lang_btn button,
    [data-testid="stSidebar"] .st-key-logout_btn button {
        background-color: ${widget_bg} !important;
        border: 1px solid ${border} !important;
        text-align: center !important;
        padding: 0.35rem 0.75rem !important;
        border-radius: 6px !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] .st-key-lang_btn button:hover,
    [data-testid="stSidebar"] .st-key-logout_btn button:hover {
        background-color: ${hover} !important;
        border-color: ${primary} !important;
    }

    [data-testid="stAlert"], [data-testid="stAlert"] * { color: ${text} !important; }

    hr { border: none; border-top: 1px solid ${border}; margin: 1.25rem 0; }

    [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-color: ${border} !important;
        background-color: ${widget_bg} !important;
    }

    .stSpinner > div { border-top-color: ${primary} !important; }
    [data-testid="stProgressBarTrack"] { background-color: ${border} !important; }
    [data-testid="stProgressBarTrack"] > div {
        background-color: ${primary} !important;
    }

    .trns-spinner {
        display: inline-block; width: 1rem; height: 1rem; margin-right: 0.5rem;
        vertical-align: -0.15rem; border-radius: 50%;
        border: 3px solid ${border}; border-top-color: ${primary};
        animation: trns-spin 0.8s linear infinite;
    }
    @keyframes trns-spin { to { transform: rotate(360deg); } }

    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    </style>
    """
)


def build_css(t: dict[str, str] = FOREST) -> str:
    """Return the ``<style>`` block for the given palette."""
    return _CSS.substitute(t, fonts=_FONTS)
