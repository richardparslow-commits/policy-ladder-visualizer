import io
import subprocess
from unittest.mock import Mock
import pandas as pd
from pypdf import PdfReader
import pytest
import pdf_report as report


def frame():
    values={key:[0]*41 for key in report.SHORT}
    values['Year']=list(range(41))
    values['Net Gap - Required Insurance ($)']=[500000]*41
    return pd.DataFrame(values)


def test_pdf_is_readable_three_pages_and_handles_literal_math():
    data=report.build_client_pdf(frame(),500000,0,0,r'Synthetic $\\unknown$ text')
    assert data.startswith(b'%PDF')
    assert len(data)<report.MAX_OUTPUT_BYTES
    pdf=PdfReader(io.BytesIO(data))
    assert len(pdf.pages)==3
    assert 'Worst-Year Shortfall' in pdf.pages[0].extract_text()
    assert 'years 21' in pdf.pages[2].extract_text()
    assert report._RENDER_SLOT.acquire(False)
    report._RENDER_SLOT.release()


@pytest.mark.parametrize('bad',[lambda f:f.iloc[:1],lambda f:pd.concat([f]*1000),
                               lambda f:f.drop(columns=['Year']),lambda f:f.assign(Year=0)])
def test_bad_frames_rejected_before_spawning(monkeypatch,bad):
    spawn=Mock(); monkeypatch.setattr(report.subprocess,'Popen',spawn)
    with pytest.raises(report.ReportError): report.build_client_pdf(bad(frame()),0,0,0,'Synthetic')
    spawn.assert_not_called()


def test_identifiers_and_unbounded_text_rejected():
    with pytest.raises(report.ReportError): report.build_client_pdf(frame(),0,0,0,'Synthetic',client_name='Client')
    with pytest.raises(report.ReportError): report.build_client_pdf(frame(),0,0,0,'x'*801)


def test_busy_renderer_fails_without_a_queue():
    assert report._RENDER_SLOT.acquire(False)
    try:
        with pytest.raises(report.ReportError,match='busy'): report.build_client_pdf(frame(),0,0,0,'Synthetic')
    finally: report._RENDER_SLOT.release()


def test_timeout_kills_worker_and_releases_slot(monkeypatch):
    worker=Mock()
    worker.communicate.side_effect=[subprocess.TimeoutExpired('worker',20),(b'',b'')]
    monkeypatch.setattr(report.subprocess,'Popen',Mock(return_value=worker))
    with pytest.raises(report.ReportError): report.build_client_pdf(frame(),0,0,0,'Synthetic')
    worker.kill.assert_called_once()
    assert report._RENDER_SLOT.acquire(False)
    report._RENDER_SLOT.release()


def test_renderer_failure_does_not_expose_worker_text(monkeypatch):
    worker=Mock(returncode=1)
    worker.communicate.return_value=(b'',b'SENSITIVE CLIENT DATA')
    monkeypatch.setattr(report.subprocess,'Popen',Mock(return_value=worker))
    with pytest.raises(report.ReportError) as exc: report.build_client_pdf(frame(),0,0,0,'Synthetic')
    assert 'SENSITIVE' not in str(exc.value)
