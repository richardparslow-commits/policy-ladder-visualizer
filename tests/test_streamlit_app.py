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


def test_real_rate_slider_updates_assumptions_and_snapshot():
    app=AppTest.from_file(APP,default_timeout=30).run()
    assert app.slider(key='real_rate_pct').value==0.0
    assert any('investment return or taxes are assumed' in c.value for c in app.caption)
    app.slider(key='real_rate_pct').set_value(5.0).run()
    assert any('at a 5% inflation-adjusted return' in c.value for c in app.caption)
    app.button(key='save_scenario').click().run()
    assert app.session_state['saved_scenario']['real_rate_pct']==5.0
    assert not app.exception


def test_pdf_request_carries_discount_rate(monkeypatch):
    import pdf_report
    seen={}
    def fake(*args,**kwargs):
        seen.update(kwargs)
        return b'%PDF-synthetic'
    monkeypatch.setattr(pdf_report,'build_client_pdf',fake)
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.slider(key='real_rate_pct').set_value(4.0).run()
    app.button(key='prepare_pdf').click().run()
    assert seen['real_rate_pct']==4.0
    assert not app.exception


def test_zero_vs_five_percent_comparison_charts_render_side_by_side():
    app=AppTest.from_file(APP,default_timeout=30).run()
    assert not app.exception
    charts=app.get('plotly_chart')
    assert len(charts)==2
    spec=charts[1].proto.spec
    assert '0% (no discounting)' in spec and '5% inflation-adjusted return' in spec
    assert 'peak net shortfall $1,345,000' in spec
    assert 'peak net shortfall $986,761' in spec


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


def test_auto_build_ladder_covers_gap_without_shortfall():
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.button(key='auto_ladder').click().run()
    assert not app.exception
    assert any('Ladder built' in m.value for m in app.success)
    assert app.metric[0].value=='$0'
    gap=int(app.metric[1].value.replace('$','').replace(',',''))
    coverage=int(app.metric[2].value.replace('$','').replace(',',''))
    assert coverage>=gap
    assert sum(app.number_input(key=f'amt{i}').value or 0 for i in (1,2,3))>0


def test_invalid_input_clears_gap_so_ladder_cannot_use_stale_inputs():
    app=AppTest.from_file(APP,default_timeout=30).run()
    assert 'ladder_gap' in app.session_state
    app.number_input(key='mortgage').set_value(None).run()
    assert 'ladder_gap' not in app.session_state
    app.button(key='auto_ladder').click().run()
    assert any('Enter the family' in m.value for m in app.error)
    assert not any('Ladder built' in m.value for m in app.success)


def test_blank_mortgage_rate_with_no_mortgage_still_gives_full_report():
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.number_input(key='mortgage').set_value(0)
    app.number_input(key='mtg_rate').set_value(None).run()
    assert not app.exception
    assert not app.error
    assert len(app.metric)==4
    assert len(app.get('plotly_chart'))==2


def test_blank_mortgage_rate_with_a_mortgage_is_still_rejected():
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.number_input(key='mtg_rate').set_value(None).run()
    assert any('Your mortgage interest rate (%) must be a number' in e.value for e in app.error)
    assert not any('mtg_rate' in e.value for e in app.error)
    assert 'ladder_gap' not in app.session_state


def test_income_and_mortgage_sliders_accept_shorter_horizons():
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.slider(key='income_years').set_value(0).run()
    assert app.slider(key='income_years').value==0
    assert not app.exception
    app.slider(key='mtg_years').set_value(1).run()
    assert app.slider(key='mtg_years').value==1
    assert not app.exception
