"""Exercise full layout, sidebar and scenario controls at mobile breakpoints."""
import os
import sys
from itertools import combinations
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from browser_checks import CheckError, load_app, run_checks, screenshot

VIEWPORTS = [("desktop",1440,900,False), ("tablet",768,1024,True),
             ("small-phone",320,568,True), ("phone",390,844,True),
             ("landscape",844,390,True), ("below-breakpoint",699,900,False),
             ("at-breakpoint",700,900,False), ("above-breakpoint",701,900,False)]
MEASURE_JS = """() => {
  const box = e => { const r=e.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}; };
  const main=document.querySelector('[data-testid="stMainBlockContainer"]');
  const header=document.querySelector('.app-header');
  return {width:window.innerWidth, scroll:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth),
    content:main ? box(main) : null,
    elements:header ? [...header.querySelectorAll('.flag,.title-wrap,.app-cta')].map(box) : [],
    flags:header ? [...header.querySelectorAll('img')].every(e=>e.complete && e.naturalWidth>0) : false,
    chart:document.querySelector('[data-testid="stPlotlyChart"]') ? box(document.querySelector('[data-testid="stPlotlyChart"]')) : null};
}"""


def overlap(a,b):
    return min(a['right'],b['right'])-max(a['left'],b['left'])>2 and min(a['bottom'],b['bottom'])-max(a['top'],b['top'])>2


def audit_viewport(app):
    m=app.evaluate(MEASURE_JS)
    issues=[]
    if m['scroll']>m['width']+1: issues.append('horizontal document overflow')
    if len(m['elements'])!=4 or not m['content'] or not m['chart']:
        return issues+['missing layout elements']
    if not m['flags']: issues.append('flag images are not loaded')
    for box in m['elements']+[m['chart']]:
        if box['width']<=0 or box['left'] < -1 or box['right']>m['width']+1:
            issues.append('element escapes viewport')
        if box['left']<m['content']['left']-2 or box['right']>m['content']['right']+2:
            issues.append('element escapes content')
    for a,b in combinations(m['elements'],2):
        if overlap(a,b): issues.append('header elements overlap')
    tx,title,cta,us=m['elements']
    if m['width']<=700:
        if abs(tx['top']-us['top'])>2 or tx['right']>=us['left']: issues.append('phone flags are not at opposite corners')
        if title['top']<tx['bottom']-1 or cta['top']<title['bottom']-1: issues.append('phone header rows collide')
    return issues


def exercise_controls(app):
    sidebar=app.locator('[data-testid="stSidebar"]')
    if sidebar.get_attribute('aria-expanded') == 'false':
        app.locator('[data-testid="stSidebarCollapsedControl"] button').click()
        app.wait_for_function("document.querySelector('[data-testid=stSidebar]').getAttribute('aria-expanded') === 'true'", timeout=5000)
    # A collapsed mobile sidebar is also tested by the base layout checks.
    family=sidebar.get_by_role('tab',name='1 · Family',exact=True)
    family.click()
    sidebar.get_by_label('Yearly income your family would need',exact=True).fill('80000')
    sidebar.get_by_label('Yearly income your family would need',exact=True).press('Enter')
    sidebar.locator('[data-testid="stSidebarCollapseButton"] button').click()
    app.wait_for_function("document.querySelector('[data-testid=stSidebar]').getAttribute('aria-expanded') === 'false'", timeout=5000)
    app.get_by_role('button',name='📌 Save this scenario',exact=True).click()
    app.get_by_text('Compare with saved',exact=True).click()
    app.get_by_role('button',name='🧹 Clear this session',exact=True).click()
    app.get_by_role('button',name='Prepare PDF report',exact=True).click()
    app.get_by_role('button',name='📕 Download PDF report',exact=True).wait_for(timeout=30000)


def main():
    browser_name=os.environ.get('TEST_BROWSER','chromium')
    if browser_name not in {'chromium','webkit'}: raise CheckError('Unsupported browser')
    with sync_playwright() as p:
        browser=getattr(p,browser_name).launch()
        failed=False
        try:
            for name,w,h,mobile in VIEWPORTS:
                context=browser.new_context(viewport={'width':w,'height':h},is_mobile=mobile,has_touch=mobile,
                                            device_scale_factor=2 if mobile else 1)
                page=context.new_page()
                try:
                    app=load_app(page)
                    page.wait_for_timeout(200)  # one bounded layout stabilization
                    issues=run_checks(app)+audit_viewport(app)
                    if name in {'desktop','phone'}:
                        exercise_controls(app)
                    if issues: raise CheckError('; '.join(issues))
                    print(f'PASS: {browser_name} {name} {w}x{h}')
                except Exception as exc:
                    failed=True
                    print(f'FAIL: {browser_name} {name} ({type(exc).__name__})')
                    if isinstance(exc, CheckError): print(str(exc))
                finally:
                    try: screenshot(page,name,os.environ.get('SCREENSHOT_DIR','audit_shots'))
                    except Exception: print('Screenshot unavailable')
                    context.close()
        finally:
            browser.close()
        return int(failed)


if __name__=='__main__':
    raise SystemExit(main())
