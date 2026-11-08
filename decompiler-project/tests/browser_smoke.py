#!/usr/bin/env python3
"""Exercise the generated atlas directly over file:// on desktop and mobile."""
import json
import hashlib
import os
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
os.environ['TMPDIR']=str(ROOT/'runtime/tmp')
os.environ['XDG_CACHE_HOME']=str(ROOT/'runtime/cache')
os.environ['XDG_CONFIG_HOME']=str(ROOT/'runtime/config')
from playwright.sync_api import sync_playwright,expect

summary=json.loads((ROOT/'exports/workspace_complete.json').read_text())
annotated_count=sum(row['seeded'] for row in json.loads((ROOT/'exports/function_index.json').read_text()))
browser_path=shutil.which('chromium') or shutil.which('chromium-browser')
if not browser_path:raise SystemExit('Chromium is required for the optional browser smoke test.')
errors=[];network=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=browser_path,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'],
                            downloads_path=str(ROOT/'runtime/tmp/downloads'))
    context=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:network.append(request.url) if request.url.startswith(('http:','https:')) else None)
    page.goto((ROOT/'report/index.html').as_uri(),wait_until='load')
    expect(page.locator('#function-name')).to_have_text('GetCaptureCcm')
    expect(page.locator('#detail-content')).to_contain_text('illuminant_ccms')
    expect(page.locator('#overview')).to_contain_text(f"{summary['function_count']:,}")
    page.screenshot(path=str(ROOT/'diagnostics/atlas-desktop.png'),full_page=True)
    page.keyboard.press('/');expect(page.locator('#function-search')).to_be_focused()
    page.locator('#function-search').fill('SetScene')
    page.locator('.function-row').filter(has=page.locator('.fn-name',has_text='SetScene')).click();expect(page.locator('#function-name')).to_have_text('SetScene')
    expect(page.locator('#detail-content')).to_contain_text('ApplyCaptureMode')
    page.get_by_role('tab',name='Assembly',exact=True).click()
    expect(page.locator('#detail-content')).to_contain_text('0x0003c5ec')
    page.get_by_role('tab',name='Calls',exact=True).click()
    page.locator('#detail-content').get_by_role('button').filter(has_text='ApplyCaptureMode').first.click()
    expect(page.locator('#function-name')).to_have_text('ApplyCaptureMode')
    page.locator('#function-search').fill('11e142')
    expect(page.locator('#result-count')).to_have_text('1 match')
    page.locator('.function-row').click()
    expect(page.locator('#function-name')).to_have_text('ConfigureCapturePipeline')
    expect(page.locator('#detail-content')).to_contain_text('isp_capture_ccm_word0')
    page.get_by_role('tab',name='Review notes',exact=True).click()
    expect(page.locator('#detail-content')).to_contain_text('Applied compiler model')
    page.locator('[data-section="symbols"]').click();page.locator('#symbol-search').fill('Museum')
    expect(page.locator('#symbols-content')).to_contain_text('Museum=17')
    page.locator('[data-section="strings"]').click();page.locator('#string-search').fill('unlikely_no_match_f80d38')
    expect(page.locator('#strings-content')).to_contain_text('0 matches')
    page.locator('[data-section="coverage"]').click()
    expect(page.locator('#coverage-content')).to_contain_text('not the percentage of original source recovered')
    page.locator('[data-section="findings"]').click()
    expect(page.locator('#findings-content')).to_contain_text('Scene films & settings')
    page.locator('#findings-content').get_by_role('button').filter(has_text='GetCaptureCcm').click()
    expect(page.locator('#function-name')).to_have_text('GetCaptureCcm')
    expect(page.locator('#detail-content')).to_contain_text('illuminant_ccms')
    # A direct link must survive reload without a server or fetch API.
    page.reload(wait_until='load');expect(page.locator('#function-name')).to_have_text('GetCaptureCcm')
    expect(page.locator('#detail-content')).to_contain_text('illuminant_ccms')
    page.locator('#function-filter').select_option('annotated')
    expect(page.locator('#result-count')).to_have_text(f'{annotated_count} matches')
    page.locator('#function-filter').select_option('review')
    expect(page.locator('#function-list')).to_contain_text('review')
    page.locator('#function-filter').select_option('all')
    page.get_by_role('tab',name='Pseudocode',exact=True).focus();page.keyboard.press('End')
    expect(page.get_by_role('tab',name='Review notes',exact=True)).to_have_attribute('aria-selected','true')
    page.keyboard.press('Home');expect(page.get_by_role('tab',name='Pseudocode',exact=True)).to_have_attribute('aria-selected','true')
    mobile_context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1)
    mobile=mobile_context.new_page()
    mobile.on('pageerror',lambda error:errors.append(str(error)))
    mobile.on('request',lambda request:network.append(request.url) if request.url.startswith(('http:','https:')) else None)
    mobile.goto((ROOT/'report/index.html').as_uri(),wait_until='load')
    expect(mobile.locator('#detail-content')).to_contain_text('illuminant_ccms')
    if mobile.evaluate('document.documentElement.scrollWidth > innerWidth + 1'):raise AssertionError('Mobile page overflows horizontally')
    mobile.screenshot(path=str(ROOT/'diagnostics/atlas-mobile.png'),full_page=True)
    for section in ['symbols','coverage','findings']:
        mobile.locator(f'[data-section="{section}"]').click()
        if mobile.evaluate('document.documentElement.scrollWidth > innerWidth + 1'):raise AssertionError(f'Mobile {section} page overflows horizontally')
    browser.close()
if errors:raise AssertionError('Browser errors: '+repr(errors))
if network:raise AssertionError('Offline report attempted network requests: '+repr(network))
result={'passed':True,'desktop_viewport':[1440,1000],'mobile_viewport':[390,844],
        'page_errors':errors,'network_requests':network,'function_count':summary['function_count'],
        'report_assets_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'report/index.html',ROOT/'report/assets/atlas.js',ROOT/'report/assets/atlas.css',ROOT/'report/data.js']},
        'checks':['Offline file protocol','Initial pseudocode','Name and interior-address search','Assembly and call navigation','Compiler-model notes','Annotation search','String empty state','Coverage and field guide','Keyboard search shortcut','Hash reload','Mobile overflow checks']}
(ROOT/'diagnostics/browser_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print('Browser smoke test passed: desktop/mobile, offline navigation, no page errors or network requests.')
