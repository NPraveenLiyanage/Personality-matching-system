"""Chart kit for the Overview report.

Rules followed (from the dataviz guidance and the research on reports for non-technical readers):
  * Bars by default; a donut only for one simple share (at most 4 slices, number in the middle);
    a heatmap for a grid of magnitudes; labelled spectrum bars instead of a radar for 4 personality axes.
  * Emphasis, not rainbow: one accent colour for "the point", grey for context, one-hue ramps for magnitude.
  * Thin bars (<= 24px, rounded data end), 2px gap between touching marks, direct labels on the values that
    matter (never a number on every point), recessive grid, colour is never the only cue.
  * Every chart can be shown as a table (accessibility relief for the light-mode aqua/yellow contrast warning).
Palette: validated with the dataviz skill's validate_palette.js in light and dark (slots 1-4 pass all checks).
"""
from __future__ import annotations

import html

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

LIGHT = dict(
    surface="#ffffff", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", base="#c3c2b7",
    accent="#2a78d6", track="#cde2fb", context="#c3c2b7", bad="#d03b3b", good="#0ca30c", warn="#fab219",
    cat=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"], other="#b4b2a9", neutral="#f0efec",
    seq=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    up="#2a78d6", down="#e34948",
)
DARK = dict(
    surface="#0e1117", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", base="#383835",
    accent="#3987e5", track="#104281", context="#4a4a46", bad="#d03b3b", good="#0ca30c", warn="#fab219",
    cat=["#3987e5", "#d95926", "#199e70", "#c98500"], other="#6b6a64", neutral="#383835",
    seq=["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
    up="#3987e5", down="#e66767",
)


def is_dark() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:                                   # older Streamlit or no theme info
        return False


def P() -> dict:
    return DARK if is_dark() else LIGHT


def _style(ch: alt.Chart | alt.LayerChart) -> alt.Chart:
    p = P()
    return (ch.configure(background="rgba(0,0,0,0)")
              .configure_view(stroke=None)
              .configure_axis(labelColor=p["ink2"], titleColor=p["ink2"], gridColor=p["grid"], domainColor=p["base"],
                              tickColor=p["base"], labelFontSize=12, titleFontSize=12, gridWidth=1)
              .configure_legend(labelColor=p["ink2"], titleColor=p["ink2"], labelFontSize=12, symbolType="square"))


def show(chart, df: pd.DataFrame | None = None, key: str = "", table_cols: list[str] | None = None,
         container: bool = True) -> None:
    """Render a chart, with a 'show as table' switch so no information is colour-only.

    container=False keeps the chart at its natural size (donuts: a fixed ring must not be stretched or clipped).
    """
    as_table = bool(df is not None and st.toggle("Show as table", key=f"tbl_{key}", help="Same numbers, as a table"))
    if as_table:
        st.dataframe(df[table_cols] if table_cols else df, hide_index=True, width="stretch")
    else:
        st.altair_chart(_style(chart), use_container_width=container, theme=None)


# ---------------------------------------------------------------------------------------------- bars
def ranked_bars(df: pd.DataFrame, n_top: int = 10, n_context: int = 5, label: str = "name", value: str = "score",
                extra_tooltip: list[str] | None = None) -> alt.Chart:
    """Top n in the accent colour with the value at the tip; the next few in grey for context."""
    p = P()
    d = df.head(n_top + n_context).copy()
    d["group"] = np.where(np.arange(len(d)) < n_top, "In the top " + str(n_top), "Next best")
    order = list(d[label])
    tips = [alt.Tooltip(f"{label}:N", title="Area"), alt.Tooltip(f"{value}:Q", title="Match", format=".0f")]
    tips += [alt.Tooltip(f"{c}:N") for c in (extra_tooltip or [])]
    base = alt.Chart(d).encode(y=alt.Y(f"{label}:N", sort=order, title=None,
                                       axis=alt.Axis(labelLimit=300, ticks=False, domain=False, labelColor=p["ink"],
                                                     labelPadding=6)))
    bars = base.mark_bar(cornerRadiusEnd=4, size=18).encode(
        x=alt.X(f"{value}:Q", title=None, scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(values=[0, 25, 50, 75, 100])),
        color=alt.condition(alt.datum.group == f"In the top {n_top}", alt.value(p["accent"]), alt.value(p["context"])),
        tooltip=tips)
    labels = base.mark_text(align="left", dx=6, fontSize=12, color=p["ink2"]).encode(
        x=alt.X(f"{value}:Q"), text=alt.Text(f"{value}:Q", format=".0f"),
        opacity=alt.condition(alt.datum.group == f"In the top {n_top}", alt.value(1), alt.value(0)))
    return (bars + labels).properties(height=len(d) * 27 + 12)


def simple_bars(df: pd.DataFrame, label: str, value: str, highlight: set | None = None, title_x: str = "",
                fmt: str = ".0f", height_per: int = 28, extra: list[str] | None = None,
                domain: list[float] | None = None) -> alt.Chart:
    """Horizontal bars, sorted, with the highlighted rows in the accent colour and the rest grey."""
    p = P()
    d = df.sort_values(value, ascending=False).copy()
    d["hl"] = d[label].isin(highlight or set())
    order = list(d[label])
    base = alt.Chart(d).encode(y=alt.Y(f"{label}:N", sort=order, title=None,
                                       axis=alt.Axis(labelLimit=300, ticks=False, domain=False, labelColor=p["ink"])))
    scale = alt.Scale(domain=domain) if domain else alt.Undefined
    tips = [alt.Tooltip(f"{label}:N"), alt.Tooltip(f"{value}:Q", format=fmt)] + [alt.Tooltip(f"{c}:N") for c in (extra or [])]
    bars = base.mark_bar(cornerRadiusEnd=4, size=18).encode(
        x=alt.X(f"{value}:Q", title=title_x or None, scale=scale, axis=alt.Axis(tickCount=5)),
        color=alt.condition(alt.datum.hl, alt.value(p["accent"]), alt.value(p["context"])),
        tooltip=tips)
    labels = base.mark_text(align="left", dx=6, fontSize=12, color=p["ink2"]).encode(
        x=alt.X(f"{value}:Q", scale=scale), text=alt.Text(f"{value}:Q", format=fmt))
    return (bars + labels).properties(height=len(d) * height_per + 12)


# ---------------------------------------------------------------------------------------------- donut
def donut_colors(labels: list[str]) -> list[str]:
    p = P()
    return [p["other"] if f in ("Other fields", "Not recognised") else p["cat"][min(i, 3)] for i, f in enumerate(labels)]


def donut(df: pd.DataFrame, field: str = "field", count: str = "areas", center: str = "",
          value_fmt: str = "{:.0f}") -> alt.Chart:
    """One simple share: at most 4 slices (3 fields + 'Other fields'), the headline number in the middle.

    Slot colours follow slice rank, not field identity: fields are not colour-coded anywhere else in the
    report, so nothing has to stay consistent across charts. Identity is carried by the legend drawn under
    the chart (see show_donut) and by the tooltip.
    """
    p = P()
    d = df.copy().reset_index(drop=True)
    d["label"] = d[field] + " (" + d[count].map(value_fmt.format) + ")"
    arc = alt.Chart(d).mark_arc(innerRadius=66, outerRadius=104, stroke=p["surface"], strokeWidth=2).encode(
        theta=alt.Theta(f"{count}:Q", stack=True),
        color=alt.Color("label:N", scale=alt.Scale(domain=list(d["label"]), range=donut_colors(list(d[field]))), legend=None),
        tooltip=[alt.Tooltip(f"{field}:N", title="Field"), alt.Tooltip(f"{count}:Q", title="Value")])
    mid = alt.Chart(pd.DataFrame({"t": [center]})).mark_text(fontSize=30, fontWeight=500, color=p["ink"]).encode(text="t:N")
    return (arc + mid).properties(width=230, height=230)


def show_donut(df: pd.DataFrame, field: str = "field", count: str = "areas", center: str = "",
               value_fmt: str = "{:.0f}", key: str = "", table_cols: list[str] | None = None) -> None:
    """Fixed-size donut with a plain legend underneath (colour square, name, value) and a table switch."""
    d = df.reset_index(drop=True)
    if st.toggle("Show as table", key=f"tbl_{key}", help="Same numbers, as a table"):
        st.dataframe(d[table_cols] if table_cols else d, hide_index=True, width="stretch")
        return
    st.altair_chart(_style(donut(d, field, count, center, value_fmt)), use_container_width=False, theme=None)
    rows = []
    for c, f, n in zip(donut_colors(list(d[field])), d[field], d[count]):
        rows.append("<div style='display:flex;align-items:center;gap:8px;margin:3px 0;font-size:14px'>"
                    f"<span style='width:12px;height:12px;border-radius:3px;background:{c};flex:none'></span>"
                    f"<span>{html.escape(str(f))} <b>({value_fmt.format(n)})</b></span></div>")
    st.markdown("".join(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------------------------------------- meter
def meter(value_pct: float, limit_pct: float, passed: bool, caption_left: str = "") -> alt.Chart:
    """One ratio against a limit: lighter track, accent fill (red if over the limit), a tick at the limit."""
    p = P()
    fill_color = p["accent"] if passed else p["bad"]
    track = alt.Chart(pd.DataFrame({"a": [0], "b": [100]})).mark_bar(cornerRadius=4, size=18).encode(
        x=alt.X("a:Q", scale=alt.Scale(domain=[0, 100]), axis=None), x2="b:Q", color=alt.value(p["track"]))
    fill = alt.Chart(pd.DataFrame({"a": [0], "b": [max(value_pct, 0.6)]})).mark_bar(cornerRadius=4, size=18).encode(
        x="a:Q", x2="b:Q", color=alt.value(fill_color), tooltip=[alt.Tooltip("b:Q", title="Share suitable (%)", format=".0f")])
    tick = alt.Chart(pd.DataFrame({"x": [limit_pct]})).mark_tick(thickness=2, size=26, color=p["ink"]).encode(x="x:Q")
    lab = alt.Chart(pd.DataFrame({"x": [limit_pct], "t": [f"limit {limit_pct:.0f}%"]})).mark_text(
        dy=-21, fontSize=12, color=p["ink2"]).encode(x="x:Q", text="t:N")
    # the value sits BELOW the bar so it can never collide with the limit label above it
    val = alt.Chart(pd.DataFrame({"x": [max(value_pct, 0.6)], "t": [f"{value_pct:.0f}% suitable"]})).mark_text(
        dy=25, fontSize=13, fontWeight=500, color=p["ink"], align="left" if value_pct < 70 else "right").encode(x="x:Q", text="t:N")
    return (track + fill + tick + lab + val).properties(height=78)


# ---------------------------------------------------------------------------------------------- spectrum
def spectrum_bars(rows: list[dict]) -> alt.Chart:
    """Four labelled spectrums (a radar would be harder to read for four axes). pct = % toward the left label."""
    p = P()
    d = pd.DataFrame(rows)
    d["x"] = 100 - d["pct"]                               # left label = first pole, so a high % sits to the left
    d["lean_pct"] = d.pct.where(d.pct >= 50, 100 - d.pct).round(0).astype(int)
    d["kind"] = np.where(d.balanced, "No clear preference", "Leans")
    d["zero"], d["hundred"] = 0, 100
    order = list(d["name"])
    xs = alt.Scale(domain=[0, 100])
    y = alt.Y("name:N", sort=order, title=None, axis=None)
    track = alt.Chart(d).mark_bar(size=6, cornerRadius=3).encode(
        y=y, x=alt.X("zero:Q", scale=xs, axis=None), x2="hundred:Q", color=alt.value(p["track"]))
    left = alt.Chart(d).mark_text(align="left", dy=-17, fontSize=12, color=p["ink2"]).encode(
        y=y, x=alt.X("zero:Q", scale=xs), text="left:N")
    right = alt.Chart(d).mark_text(align="right", dy=-17, fontSize=12, color=p["ink2"]).encode(
        y=y, x=alt.X("hundred:Q", scale=xs), text="right:N")
    dot = alt.Chart(d).mark_point(size=260, filled=True, strokeWidth=2, stroke=p["surface"]).encode(
        y=y, x=alt.X("x:Q", scale=xs),
        color=alt.condition(alt.datum.balanced, alt.value(p["muted"]), alt.value(p["accent"])),
        tooltip=[alt.Tooltip("name:N", title="Dimension"), alt.Tooltip("kind:N", title=""),
                 alt.Tooltip("lean:N", title="Leans toward"), alt.Tooltip("lean_pct:Q", title="Strength (%)")])
    layers = track + left + right + dot
    if d.balanced.any():
        layers = layers + alt.Chart(d[d.balanced]).mark_text(dy=20, fontSize=11, color=p["muted"]).encode(
            y=y, x=alt.X("x:Q", scale=xs), text=alt.value("no clear preference"))
    return layers.properties(height=len(d) * 64)


# ---------------------------------------------------------------------------------------------- heatmap
def heatmap(long: pd.DataFrame, row: str, col: str, value: str, row_order: list[str], col_order: list[str],
            label_min: float = 50) -> alt.Chart:
    """Grid of magnitudes, one hue (light to dark). Only the 'suitable' cells carry a number."""
    p = P()
    d = long.copy()
    d["light_text"] = d[value] >= 60 if not is_dark() else d[value] < 55    # cells dark enough to need white text
    base = alt.Chart(d).encode(
        y=alt.Y(f"{row}:N", sort=row_order, title=None, axis=alt.Axis(labelLimit=260, ticks=False, domain=False, labelColor=p["ink"])),
        x=alt.X(f"{col}:N", sort=col_order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=170, ticks=False, domain=False,
                                                                       orient="top", labelColor=p["ink"])))
    cells = base.mark_rect(stroke=p["surface"], strokeWidth=2, cornerRadius=3).encode(
        color=alt.Color(f"{value}:Q", scale=alt.Scale(domain=[0, 100], range=[p["seq"][0], p["seq"][-1]]), legend=alt.Legend(title="Best match in field", format=".0f")),
        tooltip=[alt.Tooltip(f"{row}:N", title="Field"), alt.Tooltip(f"{col}:N", title="Person"),
                 alt.Tooltip(f"{value}:Q", title="Best match", format=".0f")])
    other_text = "#0b0b0b" if is_dark() else p["ink"]
    text = base.mark_text(fontSize=12).encode(
        text=alt.condition(alt.datum[value] >= label_min, alt.Text(f"{value}:Q", format=".0f"), alt.value("")),
        color=alt.condition(alt.datum.light_text, alt.value("#ffffff"), alt.value(other_text)))
    return (cells + text).properties(height=len(row_order) * 32 + 20)


# ---------------------------------------------------------------------------------------------- dumbbell
def dumbbell(movers: pd.DataFrame, before_title: str = "Before", after_title: str = "After") -> alt.Chart:
    """Rank before -> after per area. Blue = moved up, red = moved down (the blue-red polarity pair)."""
    p = P()
    d = movers.copy()
    d["direction"] = np.where(d.move > 0, "Moved up", np.where(d.move < 0, "Moved down", "Same"))
    order = list(d.sort_values("after").area)
    hi = int(max(d.before.max(), d.after.max())) + 1
    y = alt.Y("area:N", sort=order, title=None, axis=alt.Axis(labelLimit=300, ticks=False, domain=False, labelColor=p["ink"]))
    xs = alt.Scale(domain=[1, hi], reverse=False)
    colors = alt.Scale(domain=["Moved up", "Moved down", "Same"], range=[p["up"], p["down"], p["muted"]])
    rule = alt.Chart(d).mark_rule(strokeWidth=2, color=p["base"]).encode(
        y=y, x=alt.X("before:Q", scale=xs, title="Rank (1 = best match)"), x2="after:Q")
    old = alt.Chart(d).mark_point(size=90, filled=False, strokeWidth=2).encode(
        y=y, x=alt.X("before:Q", scale=xs), color=alt.value(p["muted"]),
        tooltip=[alt.Tooltip("area:N"), alt.Tooltip("before:Q", title=before_title + " rank"),
                 alt.Tooltip("after:Q", title=after_title + " rank")])
    new = alt.Chart(d).mark_point(size=110, filled=True, stroke=p["surface"], strokeWidth=2).encode(
        y=y, x=alt.X("after:Q", scale=xs), color=alt.Color("direction:N", scale=colors,
                                                           legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("area:N"), alt.Tooltip("before:Q", title=before_title + " rank"),
                 alt.Tooltip("after:Q", title=after_title + " rank")])
    return (rule + old + new).properties(height=len(d) * 30 + 40)


# ---------------------------------------------------------------------------------------------- funnel
def funnel(stages: list[tuple[str, int]]) -> alt.Chart:
    """Centred bars that narrow: many scored, few shortlisted, a handful shown. The last stage is the accent."""
    p = P()
    top = max(n for _, n in stages)
    rows = [dict(stage=s, n=n, lo=(top - n) / 2, hi=(top + n) / 2, last=(i == len(stages) - 1)) for i, (s, n) in enumerate(stages)]
    d = pd.DataFrame(rows)
    order = [s for s, _ in stages]
    y = alt.Y("stage:N", sort=order, title=None, axis=alt.Axis(labelLimit=320, ticks=False, domain=False, labelColor=p["ink"]))
    bars = alt.Chart(d).mark_bar(size=26, cornerRadius=4).encode(
        y=y, x=alt.X("lo:Q", axis=None, scale=alt.Scale(domain=[0, top])), x2="hi:Q",
        color=alt.condition(alt.datum.last, alt.value(p["accent"]), alt.value(p["context"])),
        tooltip=[alt.Tooltip("stage:N", title="Stage"), alt.Tooltip("n:Q", title="Areas")])
    lab = alt.Chart(d).mark_text(fontSize=14, fontWeight=500, color=p["ink"], align="left", dx=8).encode(
        y=y, x=alt.X("hi:Q", scale=alt.Scale(domain=[0, top])), text="n:Q")
    return (bars + lab).properties(height=len(d) * 44 + 8)


# ---------------------------------------------------------------------------------------------- diverging stack
def diverging_stack(counts: pd.DataFrame, group: str = "band") -> alt.Chart:
    """Likert accuracy ratings 1-5 per group, centred on the neutral middle (3 = partly accurate).

    counts: columns [group, 1, 2, 3, 4, 5] holding the NUMBER of ratings. Left arm red (inaccurate), right arm blue.
    """
    p = P()
    labels = {1: "1 Very inaccurate", 2: "2 Inaccurate", 3: "3 Partly accurate", 4: "4 Accurate", 5: "5 Highly accurate"}
    cols = {1: "#e34948", 2: "#f0a39d", 3: p["neutral"], 4: "#9ec5f4", 5: p["accent"]} if not is_dark() else \
           {1: "#e66767", 2: "#a24545", 3: p["neutral"], 4: "#256abf", 5: p["accent"]}
    rows = []
    for _, r in counts.iterrows():
        tot = sum(r[k] for k in (1, 2, 3, 4, 5)) or 1
        pct = {k: 100 * r[k] / tot for k in (1, 2, 3, 4, 5)}
        left_edge = -(pct[1] + pct[2] + pct[3] / 2)
        x = left_edge
        for k in (1, 2, 3, 4, 5):
            rows.append(dict(group=r[group], rating=labels[k], x0=x, x1=x + pct[k], pct=pct[k]))
            x += pct[k]
    d = pd.DataFrame(rows)
    order = list(counts[group])
    return alt.Chart(d).mark_bar(size=22, stroke=p["surface"], strokeWidth=2).encode(
        y=alt.Y("group:N", sort=order, title=None, axis=alt.Axis(ticks=False, domain=False, labelColor=p["ink"])),
        x=alt.X("x0:Q", title="Share of ratings (%)", axis=alt.Axis(format="~s")), x2="x1:Q",
        color=alt.Color("rating:N", scale=alt.Scale(domain=list(labels.values()), range=[cols[k] for k in labels]),
                        legend=alt.Legend(title=None, orient="bottom", columns=3)),
        tooltip=[alt.Tooltip("group:N", title="Score band"), alt.Tooltip("rating:N"), alt.Tooltip("pct:Q", title="Share (%)", format=".0f")]
    ).properties(height=len(order) * 44 + 40)


# ---------------------------------------------------------------------------------------------- small meters
def three_meters(rows: list[tuple[str, float, str]]) -> alt.Chart:
    """'Why this score': a few labelled meters (0-1) with a plain word at the end of each."""
    p = P()
    d = pd.DataFrame(rows, columns=["label", "v", "word"])
    d["pct"], d["zero"], d["hundred"] = d.v * 100, 0, 100
    order = list(d["label"])
    xs = alt.Scale(domain=[0, 175])
    y = alt.Y("label:N", sort=order, title=None,
              axis=alt.Axis(labelLimit=260, ticks=False, domain=False, labelColor=p["ink"], labelPadding=8))
    track = alt.Chart(d).mark_bar(size=14, cornerRadius=4).encode(
        y=y, x=alt.X("zero:Q", scale=xs, axis=None), x2="hundred:Q", color=alt.value(p["track"]))
    fill = alt.Chart(d).mark_bar(size=14, cornerRadius=4).encode(
        y=y, x=alt.X("zero:Q", scale=xs, axis=None), x2="pct:Q", color=alt.value(p["accent"]),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("word:N", title="Reading")])
    word = alt.Chart(d).mark_text(align="left", dx=8, fontSize=13, color=p["ink"]).encode(
        y=y, x=alt.X("hundred:Q", scale=xs), text="word:N")
    return (track + fill + word).properties(height=len(d) * 40 + 8)
