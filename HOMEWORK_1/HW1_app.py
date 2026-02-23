# HW1_app.py
# NYT Articles analysis: understand mass shooting coverage by state.
# Loads NYT article cache on start; run analysis to compare two states' coverage.

from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from HW1_data_reporter import generate_comparison_docx
from HW1_state_analysis import (
    get_all_states_stats,
    get_states_2025,
    run_state_analysis,
)
from HW1_nyt_cache import load_or_build_2025_cache

HW1_DIR = Path(__file__).resolve().parent


def _takeaway_card(state_name: str, data: dict):
    """
    One takeaway card: Covered by NYT (event label + link + headline + pub date per event), Not covered (list).
    reported_events: list of {"label": "City, date", "articles": [{"url", "headline", "pub_date"}, ...]}.
    """
    reported = data.get("reported_events", [])
    not_reported = data.get("not_reported_events", [])
    max_shown = 15
    shown_reported = reported[:max_shown]
    shown_not = not_reported[:max_shown]

    def _one_event(entry):
        if isinstance(entry, str):
            return ui.div(ui.span(entry, class_="text-secondary"), class_="mb-2")
        label = entry.get("label", "")
        articles = entry.get("articles", [])
        kids = [ui.p(label, class_="fw-semibold mb-1", style="font-size: 0.95rem;")]
        article_lines = []
        for art in articles:
            url = art.get("url", "")
            headline = art.get("headline", "") or "(No headline)"
            pub_date = art.get("pub_date", "")
            line_parts = []
            if url:
                line_parts.append(ui.a(headline, href=url, target="_blank", rel="noopener"))
            else:
                line_parts.append(ui.span(headline, class_="text-muted"))
            if pub_date:
                line_parts.append(ui.span(f" (published {pub_date})", class_="text-muted small"))
            article_lines.append(ui.p(*line_parts, class_="small mb-0 ms-2", style="line-height: 1.4;"))
        # Scrollable list of all NYT articles for this shooting
        articles_container = ui.div(
            *article_lines,
            class_="border-start border-2 border-secondary ps-2 mb-3",
            style="max-height: 220px; overflow-y: auto; overflow-x: hidden;",
        )
        kids.append(articles_container)
        return ui.div(*kids)

    covered_list = [ui.div("None", class_="text-muted")] if not shown_reported else [_one_event(e) for e in shown_reported]
    if not shown_not:
        not_list = [ui.p("None", class_="text-muted mb-0")]
    else:
        not_list = [ui.tags.ul(*[ui.tags.li(ev, class_="small text-muted") for ev in shown_not], class_="mb-0 ps-3", style="line-height: 1.5;")]
    if len(not_reported) > max_shown:
        not_list.append(ui.p(f"... and {len(not_reported) - max_shown} more.", class_="small text-muted mt-1"))
    if len(reported) > max_shown:
        covered_list.append(ui.p(f"... and {len(reported) - max_shown} more events.", class_="small text-muted mt-1"))

    return ui.card(
        ui.card_header(ui.h5(f"{state_name} — Takeaway", class_="mb-0")),
        ui.card_body(
            ui.h6("Covered by NYT", class_="text-primary mb-2", style="font-size: 1rem;"),
            ui.div(*covered_list),
            ui.h6("Not covered", class_="text-secondary mb-2 mt-3", style="font-size: 1rem;"),
            ui.div(*not_list),
        ),
        class_="col-12",
    )


def _comparison_table_rows(result: dict):
    """Build list of (metric, state_a_value, state_b_value). Coverage days as one heading row + min/max/mean/median sub-rows."""
    a = result.get("state_a") or {}
    b = result.get("state_b") or {}

    def _fmt(v):
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.1f}"
        return str(v)

    return [
        ("Total mass shootings (2025)", _fmt(a.get("total_shootings")), _fmt(b.get("total_shootings"))),
        ("Events with ≥1 NYT article", _fmt(a.get("reported_count")), _fmt(b.get("reported_count"))),
        ("% reported by NYT", f"{_fmt(a.get('pct_reported'))}%", f"{_fmt(b.get('pct_reported'))}%"),
        ("Coverage duration (days)", "—", "—"),  # header row
        ("  min", _fmt(a.get("coverage_min_days")), _fmt(b.get("coverage_min_days"))),
        ("  max", _fmt(a.get("coverage_max_days")), _fmt(b.get("coverage_max_days"))),
        ("  mean", _fmt(a.get("coverage_mean_days")), _fmt(b.get("coverage_mean_days"))),
        ("  median", _fmt(a.get("coverage_median_days")), _fmt(b.get("coverage_median_days"))),
    ]


# 1. UI ############################

def sidebar():
    states = get_states_2025()
    choices = {s: s for s in states} if states else {"": "(No 2025 data)"}
    default_a = states[0] if states else None
    default_b = (states[1] if len(states) > 1 else states[0]) if states else None
    return ui.sidebar(
        ui.h5("Shooting coverage by state", class_="mt-3"),
        ui.p("NYT articles analysis: compare how two states’ mass shootings were covered in the New York Times.", class_="small text-muted"),
        ui.hr(),
        ui.input_select("state_a", "State A", choices=choices, selected=default_a),
        ui.input_select("state_b", "State B", choices=choices, selected=default_b),
        ui.hr(),
        ui.input_action_button("run_analysis", "Run NYT coverage analysis", class_="btn-primary", width="100%"),
        ui.input_action_button("top10_btn", "Top 10 Statistics", class_="btn-outline-secondary", width="100%"),
        ui.p("Uses cached NYT articles and GVA mass shooting data.", class_="small text-muted mt-2"),
        open="desktop",
    )


def main_content():
    return ui.TagList(
        ui.output_ui("cache_status_ui"),
        ui.output_ui("analysis_error_ui"),
        ui.output_ui("comparison_section"),
        ui.output_ui("top10_section"),
    )


app_ui = ui.page_sidebar(
    sidebar(),
    ui.layout_columns(
        ui.value_box(
            "NYT Articles Analysis",
            "Shooting coverage by state — understand how mass shootings were covered in the New York Times",
            theme="primary",
            class_="col-12",
        ),
        ui.card(
            ui.card_header(
                ui.h4("Shooting coverage by state (NYT articles)", class_="mb-0"),
                class_="bg-primary text-white",
            ),
            main_content(),
            class_="col-12",
        ),
        col_widths=[12],
        row_heights="auto",
    ),
    title="NYT Articles: Shooting Coverage by State",
    fillable=True,
)

# 2. Server ############################


def server(input: Inputs, output: Outputs, session: Session):
    cache_articles = reactive.Value(None)
    cache_error = reactive.Value(None)
    analysis_result = reactive.Value(None)
    top10_result = reactive.Value(None)
    report_path = reactive.Value(None)  # path to last generated .docx in HOMEWORK_1

    # Load cache once when app starts
    @reactive.effect
    def init_cache():
        if cache_articles.get() is not None or cache_error.get() is not None:
            return
        try:
            articles = load_or_build_2025_cache()
            cache_articles.set(articles)
            cache_error.set(None)
        except Exception as e:
            cache_articles.set(None)
            cache_error.set(str(e))

    @output
    @render.ui
    def cache_status_ui():
        err = cache_error.get()
        if err:
            return ui.div(f"Cache error: {err}", class_="alert alert-danger mt-3")
        arts = cache_articles.get()
        if arts is None:
            return ui.div("Loading NYT articles cache...", class_="alert alert-info mt-3")
        return ui.div(f"NYT articles cache ready: {len(arts)} articles.", class_="alert alert-success mt-3")

    @reactive.effect
    @reactive.event(input.run_analysis, ignore_none=False)
    def run_analysis():
        err = cache_error.get()
        if err:
            analysis_result.set({"error": err, "state_a": None, "state_b": None})
            return
        arts = cache_articles.get()
        if arts is None:
            analysis_result.set({"error": "Cache not ready yet.", "state_a": None, "state_b": None})
            return
        try:
            sa = input.state_a()
            sb = input.state_b()
        except Exception:
            analysis_result.set({"error": "Select both states.", "state_a": None, "state_b": None})
            return
        if not sa or not sb:
            analysis_result.set({"error": "Select both states.", "state_a": None, "state_b": None})
            return
        if sa == sb:
            analysis_result.set({"error": "Please select two different states.", "state_a": None, "state_b": None})
            return
        result = run_state_analysis(sa, sb, cache_articles=arts)
        analysis_result.set(result)
        top10_result.set(None)  # close Top 10 when user runs two-state comparison again
        if result.get("error"):
            report_path.set(None)
        elif result.get("state_a") and result.get("state_b"):
            a = result.get("state_a") or {}
            b = result.get("state_b") or {}
            sa_name = a.get("state", "State A")
            sb_name = b.get("state", "State B")
            safe = f"{sa_name.replace(' ', '_')}_vs_{sb_name.replace(' ', '_')}"
            out_path = HW1_DIR / f"HW1_NYT_Comparison_{safe}.docx"
            try:
                generate_comparison_docx(
                    sa_name, sb_name, a, b, out_path,
                    cache_start_date=result.get("cache_start_date"),
                    cache_end_date=result.get("cache_end_date"),
                )
                report_path.set(str(out_path))
            except Exception:
                pass

    @reactive.effect
    @reactive.event(input.top10_btn, ignore_none=False)
    def run_top10():
        err = cache_error.get()
        if err:
            top10_result.set({"error": err})
            return
        arts = cache_articles.get()
        if arts is None:
            top10_result.set({"error": "Cache not ready yet."})
            return
        try:
            out = get_all_states_stats(cache_articles=arts)
            if out.get("error"):
                top10_result.set({"error": out["error"]})
                return
            states_list = out.get("states", [])
            top10_shootings = sorted(states_list, key=lambda x: x.get("total_shootings", 0), reverse=True)[:10]
            top10_coverage = sorted(states_list, key=lambda x: x.get("pct_reported", 0), reverse=True)[:10]
            top10_result.set({
                "error": None,
                "top10_shootings": top10_shootings,
                "top10_coverage": top10_coverage,
                "cache_start_date": out.get("cache_start_date"),
                "cache_end_date": out.get("cache_end_date"),
            })
        except Exception as e:
            top10_result.set({"error": str(e)})

    @output
    @render.ui
    def analysis_error_ui():
        r = analysis_result.get()
        if r is None:
            return None
        if r.get("error"):
            return ui.div(r["error"], class_="alert alert-warning mt-3")
        return None

    @output
    @render.ui
    def comparison_section():
        if top10_result.get() is not None:
            return None  # show only Top 10 when it is displayed
        r = analysis_result.get()
        if r is None:
            return ui.div(
                ui.h5("Ready to analyze", class_="mt-3"),
                ui.p('Select two states and click "Run NYT coverage analysis" to see shooting coverage by state from NYT articles.', class_="text-muted"),
            )
        if r.get("error"):
            return None
        a = r.get("state_a") or {}
        b = r.get("state_b") or {}
        sa_name = a.get("state", "State A")
        sb_name = b.get("state", "State B")
        cache_start = r.get("cache_start_date", "")
        cache_end = r.get("cache_end_date", "")
        date_range_ui = (
            ui.p(
                ui.span("Shootings considered: ", class_="fw-semibold"),
                ui.span(f"{cache_start} to {cache_end} ", class_="text-muted"),
                ui.span("(cache article date range)", class_="small text-muted"),
                class_="mb-2",
            )
            if cache_start and cache_end
            else ui.TagList()
        )
        def _state_box(title: str, value_text: str, subtext: str, theme: str):
            """Snapshot box: same size; larger value and description for better fit."""
            return ui.value_box(
                ui.div(title, style="font-size: 1.5rem; font-weight: 700;"),
                ui.div(
                    ui.span(value_text, style="font-size: 1.35rem; font-weight: 600;"),
                    ui.br(),
                    ui.span(subtext, style="font-size: 0.9rem; white-space: nowrap;"),
                ),
                theme=theme,
                style="min-width: 280px;",
            )

        return ui.TagList(
            date_range_ui,
            ui.div(
                ui.download_button("download_report", "Generate comparison document (.docx)", class_="btn btn-outline-primary mb-3"),
                class_="d-flex",
            ),
            ui.layout_columns(
                _state_box(sa_name, str(a.get("total_shootings", 0)), "total shootings", "blue"),
                _state_box(sb_name, str(b.get("total_shootings", 0)), "total shootings", "purple"),
                col_widths=[6, 6],
                style="gap: 1rem;",
            ),
            ui.layout_columns(
                _state_box(f"{sa_name} Coverage", f"{a.get('pct_reported', 0)}%", "reported", "blue"),
                _state_box(f"{sb_name} Coverage", f"{b.get('pct_reported', 0)}%", "reported", "purple"),
                col_widths=[6, 6],
                style="gap: 1rem;",
            ),
            ui.card(
                ui.card_header(ui.h5("Coverage comparison (NYT articles)", class_="mb-0")),
                ui.card_body(
                    ui.output_table("comparison_table"),
                    class_="p-3",
                ),
                class_="mt-3",
            ),
            ui.div(ui.div(_takeaway_card(sa_name, a), class_="mb-3"), ui.div(_takeaway_card(sb_name, b))),
        )

    def _report_filename():
        r = analysis_result.get()
        if not r or r.get("error"):
            return "NYT_coverage_comparison.docx"
        a = r.get("state_a") or {}
        b = r.get("state_b") or {}
        sa = (a.get("state") or "State_A").replace(" ", "_")
        sb = (b.get("state") or "State_B").replace(" ", "_")
        return f"NYT_coverage_{sa}_vs_{sb}.docx"

    @output
    @render.download(filename=_report_filename)
    def download_report():
        import os
        import tempfile
        saved = report_path.get()
        if saved and os.path.isfile(saved):
            return saved
        r = analysis_result.get()
        if not r or r.get("error"):
            raise RuntimeError("Run NYT coverage analysis first, then generate the document.")
        a = r.get("state_a") or {}
        b = r.get("state_b") or {}
        sa_name = a.get("state", "State A")
        sb_name = b.get("state", "State B")
        fd, path = tempfile.mkstemp(suffix=".docx")
        try:
            os.close(fd)
            generate_comparison_docx(
                sa_name, sb_name, a, b, Path(path),
                cache_start_date=r.get("cache_start_date"),
                cache_end_date=r.get("cache_end_date"),
            )
            return path
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise

    @output
    @render.table
    def comparison_table():
        if top10_result.get() is not None:
            return None
        r = analysis_result.get()
        if r is None or r.get("error"):
            return None
        rows = _comparison_table_rows(r)
        a = r.get("state_a") or {}
        b = r.get("state_b") or {}
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Metric", a.get("state", "State A"), b.get("state", "State B")])
        return df

    @output
    @render.ui
    def top10_section():
        r = top10_result.get()
        if r is None:
            return None
        if r.get("error"):
            return ui.div(
                ui.h5("Top 10 Statistics", class_="mt-4 mb-2"),
                ui.div(r["error"], class_="alert alert-warning"),
            )
        cache_start = r.get("cache_start_date", "")
        cache_end = r.get("cache_end_date", "")
        date_note = f" (shootings in cache date range {cache_start}–{cache_end})" if cache_start and cache_end else ""
        return ui.TagList(
            ui.h5("Top 10 Statistics", class_="mt-4 mb-2"),
            ui.p(f"Based on cached NYT articles and GVA data.{date_note}", class_="small text-muted mb-3"),
            ui.card(
                ui.card_header(ui.h6("Top 10 states by most shootings", class_="mb-0")),
                ui.card_body(
                    ui.div(ui.output_table("top10_shootings_table"), class_="table-responsive"),
                    class_="p-4",
                ),
                class_="mb-4",
            ),
            ui.card(
                ui.card_header(ui.h6("Top 10 states by highest % coverage", class_="mb-0")),
                ui.card_body(
                    ui.div(ui.output_table("top10_coverage_table"), class_="table-responsive"),
                    class_="p-4",
                ),
            ),
        )

    @output
    @render.table(classes="table table-striped table-hover")
    def top10_shootings_table():
        r = top10_result.get()
        if not r or r.get("error") or not r.get("top10_shootings"):
            return None
        import pandas as pd
        return pd.DataFrame([
            {"Rank": i, "State": s["state"], "Total shootings": s["total_shootings"], "Reported": s["reported_count"], "% reported": f"{s['pct_reported']}%"}
            for i, s in enumerate(r["top10_shootings"], start=1)
        ])

    @output
    @render.table(classes="table table-striped table-hover")
    def top10_coverage_table():
        r = top10_result.get()
        if not r or r.get("error") or not r.get("top10_coverage"):
            return None
        import pandas as pd
        return pd.DataFrame([
            {"Rank": i, "State": s["state"], "% reported": f"{s['pct_reported']}%", "Total shootings": s["total_shootings"], "Reported": s["reported_count"]}
            for i, s in enumerate(r["top10_coverage"], start=1)
        ])



# 3. App ############################

app = App(app_ui, server)
