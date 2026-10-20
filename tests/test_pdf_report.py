import io
import subprocess
from unittest.mock import Mock

import pandas as pd
import pytest
from pypdf import PdfReader

import pdf_report as report


def frame():
    values = {key: [0] * 41 for key in report.SHORT}
    values["Year"] = list(range(41))
    values["Net Gap - Required Insurance ($)"] = [500000] * 41
    return pd.DataFrame(values)


def test_pdf_is_readable_three_pages_and_handles_literal_math():
    data = report.build_client_pdf(frame(), 500000, 0, 0, r"Synthetic $\\unknown$ text")
    assert data.startswith(b"%PDF")
    assert len(data) < report.MAX_OUTPUT_BYTES
    pdf = PdfReader(io.BytesIO(data))
    assert len(pdf.pages) == 3
    assert "Worst-Year Shortfall" in pdf.pages[0].extract_text()
    assert "years 21" in pdf.pages[2].extract_text()
    assert report._RENDER_SLOT.acquire(False)
    report._RENDER_SLOT.release()


@pytest.mark.parametrize(
    "bad",
    [
        lambda f: f.iloc[:1],
        lambda f: pd.concat([f] * 1000),
        lambda f: f.drop(columns=["Year"]),
        lambda f: f.assign(Year=0),
    ],
)
def test_bad_frames_rejected_before_spawning(monkeypatch, bad):
    spawn = Mock()
    monkeypatch.setattr(report.subprocess, "Popen", spawn)
    with pytest.raises(report.ReportError):
        report.build_client_pdf(bad(frame()), 0, 0, 0, "Synthetic")
    spawn.assert_not_called()


def test_identifiers_and_unbounded_text_rejected():
    with pytest.raises(report.ReportError):
        report.build_client_pdf(frame(), 0, 0, 0, "Synthetic", client_name="Client")
    with pytest.raises(report.ReportError):
        report.build_client_pdf(frame(), 0, 0, 0, "x" * 801)
    with pytest.raises(report.ReportError):
        report.build_client_pdf(frame(), 0, 0, 0, "Synthetic", real_rate_pct=11)


def test_busy_renderer_fails_without_a_queue():
    assert report._RENDER_SLOT.acquire(False)
    try:
        with pytest.raises(report.ReportError, match="busy"):
            report.build_client_pdf(frame(), 0, 0, 0, "Synthetic")
    finally:
        report._RENDER_SLOT.release()


def test_timeout_kills_worker_and_releases_slot(monkeypatch):
    worker = Mock()
    worker.communicate.side_effect = [
        subprocess.TimeoutExpired("worker", 20),
        (b"", b""),
    ]
    monkeypatch.setattr(report.subprocess, "Popen", Mock(return_value=worker))
    with pytest.raises(report.ReportError):
        report.build_client_pdf(frame(), 0, 0, 0, "Synthetic")
    worker.kill.assert_called_once()
    assert report._RENDER_SLOT.acquire(False)
    report._RENDER_SLOT.release()


def test_renderer_failure_does_not_expose_worker_text(monkeypatch):
    worker = Mock(returncode=1)
    worker.communicate.return_value = (b"", b"SENSITIVE CLIENT DATA")
    monkeypatch.setattr(report.subprocess, "Popen", Mock(return_value=worker))
    with pytest.raises(report.ReportError) as exc:
        report.build_client_pdf(frame(), 0, 0, 0, "Synthetic")
    assert "SENSITIVE" not in str(exc.value)


def sections_frame():
    # Gap falls $10k a year from $500k; coverage is flat at $300k, so the worst shortfall is $200k in year 0.
    values = {key: [0] * 41 for key in report.SHORT}
    values["Year"] = list(range(41))
    values["Net Gap - Required Insurance ($)"] = [
        500000 - 10000 * year for year in range(41)
    ]
    values["Proposed Ladder Coverage ($)"] = [300000] * 41
    values["Income Replacement ($)"] = [1000 * year for year in range(41)]
    return pd.DataFrame(values)


def sections_pdf():
    return report.build_client_pdf(
        sections_frame(),
        500000,
        300000,
        12000,
        "Synthetic insight text.",
        real_rate_pct=2,
    )


def page_texts(data):
    return [page.extract_text() for page in PdfReader(io.BytesIO(data)).pages]


def rgb_op(hex_value, op):
    # Matplotlib writes each channel with up to 10 decimals and trims trailing zeros.
    channels = [
        f"{int(hex_value[i : i + 2], 16) / 255:.10f}".rstrip("0").rstrip(".")
        for i in (1, 3, 5)
    ]
    return " ".join(channels + [op])


def test_client_pdf_summary_page_has_sections_and_metric_cards():
    data = sections_pdf()
    assert (
        PdfReader(io.BytesIO(data)).metadata.title
        == "De-identified insurance planning report"
    )
    summary = " ".join(page_texts(data)[0].split())
    for text in (
        "Life Insurance Gap Analysis",
        "De-identified planning report",
        "Worst-Year Shortfall",
        "$200,000 (year 0)",
        "Current Insurance Gap",
        "$500,000",
        "New Ladder Coverage",
        "$300,000",
        "Annual Premium Roll-Off",
        "$12,000/yr",
        "discounted to today's dollars at a 2% inflation-adjusted return",
        "No inflation or taxes are assumed.",
        "Detailed figures follow on pages 2 and 3.",
        "Synthetic insight text.",
    ):
        assert text in summary, text


def test_client_pdf_summary_chart_has_axes_legend_and_series_colors():
    data = sections_pdf()
    summary = " ".join(page_texts(data)[0].split())
    for text in (
        "Years into Future",
        "Dollar Amount ($)",
        "$400k",
        "Required Insurance (Gap)",
        "Proposed Policy Ladder",
    ):
        assert text in summary, text
    content = (
        PdfReader(io.BytesIO(data)).pages[0].get_contents().get_data().decode("latin1")
    )
    assert rgb_op(report.GAP_FILL, "rg") in content  # shaded gap area
    assert rgb_op(report.PRIMARY_RED, "RG") in content  # policy ladder step line


def test_client_pdf_detail_pages_have_year_tables_with_legend():
    text2, text3 = page_texts(sections_pdf())[1:]
    # The text layer drops en/em dashes, so titles extract as 'years 0 20' rather than 'years 0–20'.
    assert "Year-by-year detail years 0 20" in " ".join(text2.split())
    assert "Year-by-year detail years 21 40" in " ".join(text3.split())
    for text in (text2, text3):
        normalized = " ".join(text.split())
        assert "Net Gap Coverage Premium" in normalized
        assert "Mtg = mortgage balance" in normalized
        assert "Net Gap = required insurance" in normalized
    rows2 = [
        line
        for line in text2.splitlines()
        if line.split() and line.split()[0].isdigit()
    ]
    rows3 = [
        line
        for line in text3.splitlines()
        if line.split() and line.split()[0].isdigit()
    ]
    assert len(rows2) == 21 and len(rows3) == 20
    assert any(
        row.startswith("20 ") and "20,000" in row and "300,000 300,000" in row
        for row in rows2
    )
    assert any(
        row.startswith("40 ") and "40,000" in row and "100,000 300,000" in row
        for row in rows3
    )
