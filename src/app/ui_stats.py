"""Admin-only usage statistics panel: reads ``data/usage.jsonl`` and plots it with plotly."""

from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from app import usage
from app.i18n import t
from app.usage_chart import daily_figure
from app.usage_stats import METRIC_EVENTS, Event, since, totals, users_in_order

#: period key -> days back (None: the whole log).
PERIODS: dict[str, int | None] = {"period_all": None, "period_month": 30, "period_week": 7}


def stats_panel(data_dir: Path, lang: str) -> None:
    with st.expander(t("stats_heading", lang), expanded=False):
        events = usage.read_events(data_dir)
        if not events:
            st.info(t("stats_empty", lang))
            return
        period, metric, by_user = _controls(lang)
        shown = since(events, PERIODS[period], datetime.now().astimezone())
        _kpis(shown, lang)
        order = users_in_order(events) if by_user else None
        fig = daily_figure(shown, metric, order=order, total_label=t("stats_total", lang))
        st.plotly_chart(fig, use_container_width=True, key="stats_chart")  # pyright: ignore[reportUnknownMemberType]
        _table(shown, lang)


def _controls(lang: str) -> tuple[str, str, bool]:
    left, mid, right = st.columns([2, 2, 1])
    period: str = left.select_slider(
        t("stats_period", lang),
        options=list(PERIODS),
        value="period_all",
        format_func=lambda key: t(key, lang),
        key="stats_period",
    )
    metric: str = mid.selectbox(
        t("stats_metric", lang),
        options=list(METRIC_EVENTS),
        format_func=lambda key: t(f"metric_{key}", lang),
        key="stats_metric",
    )
    by_user = right.toggle(t("stats_by_user", lang), value=True, key="stats_by_user")
    return period, metric, by_user


def _kpis(events: list[Event], lang: str) -> None:
    rows = totals(events)
    values: list[tuple[str, Any]] = [
        (t("stats_users", lang), len(rows)),
        (t("metric_logins", lang), sum(r.logins for r in rows)),
        (t("metric_jobs", lang), sum(r.jobs for r in rows)),
        (t("metric_minutes", lang), f"{sum(r.minutes for r in rows):.1f}"),
        (t("metric_downloads", lang), sum(r.downloads for r in rows)),
    ]
    for col, (label, value) in zip(st.columns(len(values)), values, strict=True):
        col.metric(label, value)
    failed = sum(e["event"] == "login_failed" for e in events)
    st.caption(t("stats_failed", lang, n=failed))


def _table(events: list[Event], lang: str) -> None:
    st.dataframe(  # pyright: ignore[reportUnknownMemberType]
        [
            {
                t("col_user", lang): r.user,
                t("metric_logins", lang): r.logins,
                t("metric_jobs", lang): r.jobs,
                t("metric_minutes", lang): round(r.minutes, 1),
                t("metric_downloads", lang): r.downloads,
                t("col_errors", lang): r.errors,
                t("col_last_seen", lang): r.last_seen[:16].replace("T", " "),
            }
            for r in totals(events)
        ],
        hide_index=True,
        use_container_width=True,
    )
