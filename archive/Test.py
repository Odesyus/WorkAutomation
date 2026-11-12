import re
from playwright.sync_api import Playwright, sync_playwright, expect
import config

def FUNC_DICT(TEXT, DICT):
    for line in TEXT.strip().split('\n'):
        parts = line.split(None, 1)
        key = parts[0]
        value = parts[1].strip() if len(parts) > 1 else ""
        DICT[key] = value
    return DICT


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    tp_creds = config.get_testportal_credentials()
    tp_url = config.URLS.get('testportal', 'https://testportal')
    page.goto(f"{tp_url}/Login.aspx")
    page.get_by_role("textbox", name="Domain ID").click()
    page.get_by_role("textbox", name="Domain ID").fill(tp_creds.get('user', ''))
    page.get_by_role("textbox", name="Domain ID").press("Tab")
    page.get_by_role("textbox", name="******").fill(tp_creds.get('password', ''))
    page.get_by_role("textbox", name="******").press("Enter")
    page.goto(f"{tp_url}/Otomasyon/Ortak/MusteriBilgisi.aspx")
    page.locator("div").filter(has_text="Müşteri Bilgisi MSISDN: Test").nth(1).click()
    page.locator("#BodyCenter_ddlBSCSServer").select_option("1")
    page.locator("#BodyCenter_txtMSISDN").click()
    page.locator("#BodyCenter_txtMSISDN").fill("5538173272")
    page.locator("#BodyCenter_txtMSISDN").press("Enter")

    main_div= "#BodyCenter_tcMusteriBilgisi_tab"
    if (page.is_visible(main_div+"BSCS_pBSCS") or page.is_visible(main_div+"BSCS_BSCSErrorDiv")):
        BSCS = page.locator(main_div+"BSCS_pBSCS,"+main_div+"BSCS_BSCSErrorDiv").inner_text()

    page.get_by_role("link", name="OCS").click()
    if (page.is_visible(main_div+"OCS_pOCS")):
        OCS = page.locator(main_div+"OCS_pOCS").inner_text()
    OCS_DICT= {}
    OCS_DICT = FUNC_DICT(OCS, OCS_DICT)

    page.get_by_role("link", name="OPERA").click()
    if (page.is_visible(main_div+"OPERA_pOPERA")):
        OPERA = page.locator(main_div+".musteriBilgisiTablo").inner_text()
    #OPERA_DICT= {}
    #OPERA_DICT = FUNC_DICT(OPERA, OPERA_DICT)
#
    #page.get_by_role("link", name="HLR").click()
    #if (page.is_visible(main_div+"EMA_pEMA")):
    #    HLR = page.locator(main_div+"EMA_pEMA").inner_text()
    #HLR_DICT= {}
    #HLR_DICT = FUNC_DICT(HLR, HLR_DICT)
#
    #page.get_by_role("link", name="CUDB").click()
    #if (page.is_visible(main_div+"CUDB_pCUDB") or page.is_visible(main_div+"CUDB_pCUDBErrorDiv")):
    #    CUDB = page.locator(main_div+"CUDB_pCUDB,"+main_div+"CUDB_CUDBErrorDiv").inner_text()
    #CUDB_DICT= {}
    #CUDB_DICT = FUNC_DICT(CUDB, CUDB_DICT)
#
    #page.get_by_role("link", name="SIEBEL").click()
    #if (page.is_visible(main_div+"SIEBEL_pSIEBEL")):
    #    SIEBEL = page.locator(main_div+"SIEBEL_pSIEBEL").inner_text()
    #SIEBEL_DICT= {}
    #SIEBEL_DICT = FUNC_DICT(SIEBEL, SIEBEL_DICT)
    


    print(OPERA)



    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
