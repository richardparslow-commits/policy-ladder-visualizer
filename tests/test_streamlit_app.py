from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=str(Path(__file__).resolve().parents[1]/'streamlit_app.py')


def test_defaults_render_without_eager_report():
    app=AppTest.from_file(APP,default_timeout=30).run()
    assert not app.exception
    assert len(app.metric)==4
    assert app.metric[1].value=='$1,595,000'
    assert 'pdf_bytes' not in app.session_state
    assert not app.text_input


def test_presets_preserve_edits_and_clear_saved_session():
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.selectbox(key='preset').select('Young family with mortgage').run()
    app.number_input(key='mortgage').set_value(123000).run()
    assert app.number_input(key='mortgage').value==123000
    app.button(key='save_scenario').click().run()
    assert app.session_state['saved_scenario']['mortgage']==123000
    app.toggle(key='compare_toggle').set_value(True).run()
    assert not app.exception
    app.button(key='clear_session').click().run()
    assert app.number_input(key='mortgage').value==400000
    assert 'saved_scenario' not in app.session_state
    assert not app.exception


def test_legacy_url_cannot_inject_session_keys():
    app=AppTest.from_file(APP,default_timeout=30)
    app.query_params['scenario']='{"save_scenario":true,"mortgage":-1}'
    app.run()
    assert not app.exception
    assert 'scenario' not in app.query_params
    assert app.number_input(key='mortgage').value==400000


def test_prepared_pdf_invalidates_on_financial_edit(monkeypatch):
    import pdf_report
    monkeypatch.setattr(pdf_report,'build_client_pdf',lambda *args,**kwargs:b'%PDF-synthetic')
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.button(key='prepare_pdf').click().run()
    assert 'pdf_bytes' in app.session_state
    app.number_input(key='mortgage').set_value(300000).run()
    assert 'pdf_bytes' not in app.session_state
    assert not app.exception


def test_term_after_permanent_preset_is_valid():
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.selectbox(key='preset').select('Empty nester').run()
    app.selectbox(key='existing_life_type').select('Term (expires)').run()
    assert not app.exception
    assert 1<=app.slider(key='existing_life_years').value<=40


def test_zero_today_still_warns_about_future_expiry_gap():
    app=AppTest.from_file(APP,default_timeout=30).run()
    for key in ['mortgage','other_debt','income_req','childcare_annual','college_total','liquid_assets']:
        app.number_input(key=key).set_value(0)
    app.checkbox(key='act1').set_value(False)
    app.run()
    assert app.metric[1].value=='$0'
    assert app.metric[0].value=='$20,000'
    summary=' '.join(m.value for m in app.markdown)
    assert 'The largest remaining shortfall' in summary
    assert 'in year 10' in summary
    assert not app.exception
