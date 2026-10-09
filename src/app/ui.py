"""Streamlit UI: thin wiring of widgets to the pipeline.

Run: ``uv run streamlit run src/app/ui.py``.

German is the default GUI language (sidebar toggle); every user-facing string comes from ``i18n``.
Layout and look follow the summarizer (PRD §5.5).
"""

import os
import signal
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from app import auth, llm_ollama, theme
from app.config import Config, load_config
from app.glossary import (
    GLOSSARY_TEMPLATE_CSV,
    Glossary,
    GlossaryError,
    GlossaryResult,
    build_glossary,
)
from app.i18n import DEFAULT_LANG, LANGUAGES, language_name, t
from app.models import ModelStatus, annotate, resolve_default
from app.pipeline import (
    JobResult,
    UploadInfo,
    failed_excerpts,
    inspect_upload,
    preview_markdown,
    report_csv,
    run_job,
)
from app.prompt import SUPPORTED_LANGUAGES
from app.readers import read_glossary_rows
from app.runner import JobHandle, Progress
from app.writers import glossary_template_xlsx, mime_type, output_name

ACCEPTED = ["docx", "md", "txt", "pdf"]
GLOSSARY_TYPES = ["csv", "tsv", "xlsx", "md"]
_GB = 2**30
_PREVIEW_HEIGHT = 500
_MAX_LISTED = 10


def _stars(n: int) -> str:
    return "★" * n + "☆" * (3 - n)


def _state() -> Any:
    return st.session_state


def _language_toggle(container: Any) -> None:
    """A button that switches the GUI to the other language."""
    other = next(code for code in LANGUAGES if code != _state()["ui_lang"])
    if container.button(f"🌐 {LANGUAGES[other]}", key="lang_btn"):
        _state()["ui_lang"] = other
        st.rerun()


def _login_gate(cfg: Config, lang: str) -> None:
    """Show the sign-in form and stop the script until a user is signed in."""
    if _state().get("user"):
        return
    try:
        auth.ensure_seeded(cfg.data_dir, os.environ)
    except RuntimeError:
        st.error(t("seed_missing", lang, vars=" / ".join(auth.SEED_USERS.values())))
        st.stop()
    _left, mid, _right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(f"## 🌐 {t('app_title', lang)}")
        st.caption(t("sign_in_hint", lang))
        with st.form("login_form"):
            username = st.text_input(t("username", lang))
            password = st.text_input(t("password", lang), type="password")
            submitted = st.form_submit_button(t("sign_in", lang), type="primary")
        if submitted and auth.verify(cfg.data_dir, username, password):
            _state()["user"] = username
            st.rerun()
        elif submitted:
            st.error(t("bad_credentials", lang))
        _language_toggle(mid)
    st.stop()


def _client(cfg: Config) -> llm_ollama.OllamaClient:
    return llm_ollama.make_client(cfg.host, cfg.timeout_s)


@st.cache_data(ttl=30, show_spinner=False)
def _installed(host: str, timeout_s: float) -> set[str]:
    """Pulled models; cached because every widget click reruns the script."""
    return llm_ollama.installed_tags(llm_ollama.make_client(host, timeout_s), host)


@st.cache_data(ttl=10, show_spinner=False)
def _loaded(host: str, timeout_s: float) -> list[tuple[str, int]]:
    return llm_ollama.loaded_models(llm_ollama.make_client(host, timeout_s))


def _sidebar(cfg: Config, lang: str) -> None:
    st.sidebar.markdown(f"## 🌐 {t('app_title', lang)}")
    st.sidebar.markdown("---")
    with st.sidebar.expander(t("advanced_options", lang), expanded=False):
        _vram_panel(cfg, lang)
    st.sidebar.markdown("---")
    user = _state()["user"]
    st.sidebar.caption(t("signed_in_as", lang, user=user))
    if st.sidebar.button(t("logout", lang), key="logout_btn"):
        _cancel_job()
        _state().clear()
        _state()["ui_lang"] = lang
        st.rerun()
    _language_toggle(st.sidebar)
    if user in cfg.admins:
        _exit_control(lang)


def _vram_panel(cfg: Config, lang: str) -> None:
    st.caption(t("vram_status", lang))
    loaded = _loaded(cfg.host, cfg.timeout_s)
    for name, size in loaded:
        st.caption(t("vram_model", lang, name=name, gb=f"{size / _GB:.1f}"))
    if not loaded:
        st.caption(t("vram_empty", lang))
    if st.button(t("clear_vram", lang), key="clear_vram_btn"):
        st.success(t("vram_cleared", lang, n=len(llm_ollama.unload_all(_client(cfg)))))
        _loaded.clear()


def _exit_control(lang: str) -> None:
    """Admin only: stop this process (never by port) after a confirmation."""
    if st.sidebar.button(t("exit_app", lang), key="exit_btn"):
        _state()["confirm_exit"] = True
    if not _state().get("confirm_exit"):
        return
    st.sidebar.warning(t("exit_confirm", lang))
    yes, no = st.sidebar.columns(2)
    if yes.button(t("exit_yes", lang), key="exit_yes_btn"):
        os.kill(os.getpid(), signal.SIGTERM)
    if no.button(t("exit_no", lang), key="exit_no_btn"):
        _state()["confirm_exit"] = False
        st.rerun()


def _model_selector(col: Any, cfg: Config, lang: str) -> ModelStatus:
    col.caption(t("model_caption", lang))
    installed: set[str]
    try:
        installed = _installed(cfg.host, cfg.timeout_s)
    except llm_ollama.OllamaUnavailableError:
        installed = set()
        col.error(t("ollama_down", lang, host=cfg.host))
    statuses = annotate(installed)
    default, warning = resolve_default(cfg.default_model)
    if warning:
        col.warning(warning)
    tags = [s.info.tag for s in statuses]

    def label(tag: str) -> str:
        return f"{statuses[tags.index(tag)].info.label} ({tag})"

    tag = col.selectbox(
        t("model_label", lang),
        tags,
        index=tags.index(default),
        format_func=label,
        label_visibility="collapsed",
    )
    status = statuses[tags.index(tag)]
    stars = (_stars(status.info.speed), _stars(status.info.quality))
    col.caption(t("speed_quality", lang, speed=stars[0], quality=stars[1]))
    if not status.installed:
        col.warning(t("not_installed", lang, tag=tag, hint=status.pull_hint))
    return status


def _language_select(col: Any, caption: str, label: str, default: str, key: str, lang: str) -> str:
    col.caption(t(caption, lang))

    def name(code: str) -> str:
        return language_name(code, lang)

    return str(
        col.selectbox(
            t(label, lang),
            list(SUPPORTED_LANGUAGES),
            index=SUPPORTED_LANGUAGES.index(default),
            format_func=name,
            key=key,
            label_visibility="collapsed",
        )
    )


def _upload_key(upload: Any) -> str:
    return f"{upload.name}:{upload.size}:{getattr(upload, 'file_id', '')}"


def _cancel_job() -> None:
    handle = _state().pop("job", None)
    if handle is not None:
        handle.request_cancel()


def _inspect(upload: Any, cfg: Config, lang: str) -> tuple[str, UploadInfo | None]:
    """The upload's key and its info; a new upload clears the old job and results."""
    key = _upload_key(upload)
    if _state().get("upload_key") != key:
        _cancel_job()
        for name in ("result", "job_error", "info"):
            _state().pop(name, None)
        _state()["upload_key"] = key
    if upload.size > cfg.max_upload_mb * 1024 * 1024:
        st.error(t("too_large", lang, mb=cfg.max_upload_mb))
        return key, None
    if "info" not in _state():
        _state()["info"] = inspect_upload(upload.name, upload.getvalue())
    info: UploadInfo = _state()["info"]
    if info.error:
        st.error(t("read_error", lang, error=info.error))
        return key, None
    return key, info


def _glossary(upload: Any, source: str, target: str, lang: str) -> Glossary | None:
    """The glossary for the pair (empty if no file); None if the file is unusable."""
    if upload is None:
        return Glossary(source, target, ())
    try:
        result = build_glossary(read_glossary_rows(upload.name, upload.getvalue()), source, target)
    except GlossaryError as exc:
        st.error(str(exc))
        return None
    _glossary_summary(result, source, target, lang)
    return result.glossary


def _glossary_summary(result: GlossaryResult, source: str, target: str, lang: str) -> None:
    n = len(result.glossary.entries)
    pair = {"n": n, "src": source, "tgt": target}
    if n:
        st.markdown(t("glossary_summary", lang, **pair))
    else:
        st.warning(t("glossary_empty", lang))
    if result.issues:
        with st.expander(t("glossary_issues", lang, n=len(result.issues))):
            for issue in result.issues:
                kind = t(f"issue_{issue.kind}", lang)
                st.caption(
                    t("glossary_issue_row", lang, row=issue.row, kind=kind, detail=issue.detail)
                )


def _start(cfg: Config, upload: Any, status: ModelStatus, glossary: Glossary) -> None:
    for name in ("result", "job_error"):
        _state().pop(name, None)
    llm = llm_ollama.make_llm(_client(cfg), status.info.tag, cfg.host)
    name, data, user = upload.name, upload.getvalue(), _state()["user"]

    def work(progress: Progress, cancel: Any) -> JobResult:
        return run_job(
            name,
            data,
            glossary,
            llm,
            user=user,
            progress=progress,
            cancel=cancel,
            segment_chars=cfg.segment_chars or status.info.segment_chars,
        )

    handle = JobHandle(work, label=status.info.tag)
    handle.start()
    _state()["job"] = handle


def _collect_finished_job() -> None:
    handle: JobHandle | None = _state().get("job")
    if handle is None or not handle.finished:
        return
    del _state()["job"]
    if handle.error is not None:
        _state()["job_error"] = str(handle.error)
    else:
        _state()["result"] = handle.result


@st.fragment(run_every=1)
def _job_panel(lang: str) -> None:
    handle: JobHandle = _state()["job"]
    if handle.finished:
        st.rerun()
    if handle.total:
        text = t("progress", lang, done=handle.done, total=handle.total)
        text += f" · {handle.label} · {handle.elapsed}"
        st.progress(handle.done / handle.total, text=text)
    else:
        st.progress(0.0, text=t("preparing", lang))
    if st.button(t("cancel_button", lang), key="cancel_btn"):
        handle.request_cancel()
    if handle.cancel_requested:
        st.caption(t("cancelling", lang))


def _show_result(result: JobResult, lang: str) -> None:
    st.markdown("---")
    st.subheader(t("result_heading", lang))
    if result.cancelled:
        st.warning(t("cancelled_notice", lang))
    _result_notices(result, lang)
    files = {"md": result.md, "docx": result.docx, "pdf": result.pdf}
    for col, (ext, data) in zip(st.columns(3), files.items(), strict=True):
        col.download_button(
            t(f"download_{ext}", lang),
            data=data,
            file_name=output_name(result.stem, result.target, ext),
            mime=mime_type(ext),
            key=f"dl_{ext}",
            use_container_width=True,
        )
    with st.container(height=_PREVIEW_HEIGHT, border=True):
        st.markdown(preview_markdown(result))
    _term_report(result, lang)


def _result_notices(result: JobResult, lang: str) -> None:
    """What stayed in the source language, above the downloads so it cannot be missed."""
    excerpts = failed_excerpts(result)
    if excerpts:
        listed = "\n".join(f"- {e}" for e in excerpts[:_MAX_LISTED])
        more = len(excerpts) - _MAX_LISTED
        tail = "\n" + t("and_more", lang, n=more) if more > 0 else ""
        st.warning(t("failed_blocks", lang, n=len(excerpts)) + "\n\n" + listed + tail)
    if result.untouched:
        names = ", ".join(t(f"feature_{f}", lang) for f in result.untouched)
        st.info(t("untouched_features", lang, features=names))


def _term_report(result: JobResult, lang: str) -> None:
    with st.expander(t("term_report", lang), expanded=bool(result.translation.misses)):
        st.markdown(t("term_counts", lang, hits=result.hits, enforced=result.enforced))
        if result.translation.misses:
            st.caption(t("term_misses", lang))
            st.dataframe(  # pyright: ignore[reportUnknownMemberType]
                [
                    {
                        t("col_excerpt", lang): m.excerpt,
                        t("col_source", lang): m.entry.source,
                        t("col_expected", lang): m.entry.target,
                    }
                    for m in result.translation.misses
                ]
            )
        st.download_button(
            t("download_report", lang),
            data=report_csv(result),
            file_name=f"{result.stem}_report.csv",
            mime="text/csv",
            key="dl_report",
        )


def _main_panel(cfg: Config, lang: str) -> None:
    st.caption(t("intro", lang))
    st.markdown("---")
    left, right = st.columns(2)
    status = _model_selector(left, cfg, lang)
    target = _language_select(
        right, "target_caption", "target_label", cfg.default_target, "target", lang
    )
    doc_col, gloss_col = st.columns(2)
    doc_col.caption(t("document_caption", lang))
    upload = doc_col.file_uploader(
        t("document_label", lang), type=ACCEPTED, label_visibility="collapsed"
    )
    gloss_col.caption(t("glossary_caption", lang))
    gloss_upload = gloss_col.file_uploader(
        t("glossary_label", lang), type=GLOSSARY_TYPES, label_visibility="collapsed"
    )
    gloss_col.download_button(
        t("glossary_template", lang),
        GLOSSARY_TEMPLATE_CSV,
        "glossar_vorlage.csv",
        "text/csv",
        key="dl_template",
    )
    gloss_col.download_button(
        t("glossary_template_xlsx", lang),
        glossary_template_xlsx(),
        "glossar_vorlage.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_template_xlsx",
    )
    if upload is not None:
        _upload_flow(cfg, lang, upload, gloss_upload, status, target)
    _collect_finished_job()
    _outcome(lang)


def _upload_flow(
    cfg: Config, lang: str, upload: Any, gloss_upload: Any, status: ModelStatus, target: str
) -> None:
    key, info = _inspect(upload, cfg, lang)
    if info is None:
        return
    detected = info.language
    src_col, gloss_col = st.columns(2)
    source = _language_select(
        src_col, "source_caption", "source_label", detected or "de", f"src_{key}", lang
    )
    src_col.caption(
        t("source_detected", lang, name=language_name(detected, lang))
        if detected
        else t("source_unknown", lang)
    )
    with gloss_col:
        glossary = _glossary(gloss_upload, source, target, lang)
    if source == target:
        st.error(t("same_language", lang))
    reason = _block_reason(source == target, glossary is None, status.installed, lang)
    clicked = st.button(
        t("translate_button", lang), type="primary", disabled=bool(reason), key="start_btn"
    )
    if reason:
        st.caption(reason)
    if clicked and glossary is not None:
        _start(cfg, upload, status, glossary)
        st.rerun()


def _block_reason(same: bool, bad_glossary: bool, installed: bool, lang: str) -> str:
    """Why "Übersetzen" is disabled; empty if it is not."""
    if "job" in _state():
        return t("reason_busy", lang)
    if not installed:
        return t("reason_model", lang)
    if bad_glossary:
        return t("reason_glossary", lang)
    if same:
        return t("reason_same", lang)
    return ""


def _outcome(lang: str) -> None:
    if "job" in _state():
        _job_panel(lang)
    elif error := _state().get("job_error"):
        st.error(t("job_failed", lang, error=error))
    elif result := _state().get("result"):
        _show_result(result, lang)


def main() -> None:
    load_dotenv()
    _state().setdefault("ui_lang", DEFAULT_LANG)
    lang: str = _state()["ui_lang"]
    st.set_page_config(
        page_title=t("app_title", lang),
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(theme.build_css(), unsafe_allow_html=True)
    try:
        cfg = load_config(os.environ)
    except ValueError as exc:
        st.error(t("config_error", lang, error=exc))
        st.stop()
    _login_gate(cfg, lang)
    _sidebar(cfg, lang)
    st.title(t("app_title", lang))
    _main_panel(cfg, lang)


if __name__ == "__main__":
    main()
