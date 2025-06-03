import os
import json
import ast
from urllib.parse import urlparse
import tempfile
import nodriver
import requests
import nodriver as uc
import random
from nodriver import cdp
import shutil
import sounddevice as sd
import soundfile as sf
import re
import undetected_chromedriver
import threading
from pyshadow.main import Shadow
import time
import sys, os
from twocaptcha import TwoCaptcha
from pydub import AudioSegment 
from nodriver.cdp.dom import Node
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from asyncio import iscoroutine, iscoroutinefunction
import logging
import json
import asyncio
import itertools

logger = logging.getLogger("uc.connection")

async def listener_loop(self):
    while True:
        try:
            msg = await asyncio.wait_for(
                self.connection.websocket.recv(), self.time_before_considered_idle
            )
        except asyncio.TimeoutError:
            self.idle.set()
            # breathe
            # await asyncio.sleep(self.time_before_considered_idle / 10)
            continue
        except (Exception,) as e:
            # break on any other exception
            # which is mostly socket is closed or does not exist
            # or is not allowed

            logger.debug(
                "connection listener exception while reading websocket:\n%s", e
            )
            break

        if not self.running:
            # if we have been cancelled or otherwise stopped running
            # break this loop
            break

        # since we are at this point, we are not "idle" anymore.
        self.idle.clear()

        message = json.loads(msg)
        if "id" in message:
            # response to our command
            if message["id"] in self.connection.mapper:
                # get the corresponding Transaction
                tx = self.connection.mapper[message["id"]]
                logger.debug("got answer for %s", tx)
                # complete the transaction, which is a Future object
                # and thus will return to anyone awaiting it.
                tx(**message)
                self.connection.mapper.pop(message["id"])
        else:
            # probably an event
            try:
                event = cdp.util.parse_json_event(message)
                event_tx = uc.connection.EventTransaction(event)
                if not self.connection.mapper:
                    self.connection.__count__ = itertools.count(0)
                event_tx.id = next(self.connection.__count__)
                self.connection.mapper[event_tx.id] = event_tx
            except Exception as e:
                logger.info(
                    "%s: %s  during parsing of json from event : %s"
                    % (type(e).__name__, e.args, message),
                    exc_info=True,
                )
                continue
            except KeyError as e:
                logger.info("some lousy KeyError %s" % e, exc_info=True)
                continue
            try:
                if type(event) in self.connection.handlers:
                    callbacks = self.connection.handlers[type(event)]
                else:
                    continue
                if not len(callbacks):
                    continue
                for callback in callbacks:
                    try:
                        if iscoroutinefunction(callback) or iscoroutine(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        logger.warning(
                            "exception in callback %s for event %s => %s",
                            callback,
                            event.__class__.__name__,
                            e,
                            exc_info=True,
                        )
                        raise
            except asyncio.CancelledError:
                break
            except Exception:
                raise
            continue
        
#call this after imported nodriver
#uc_fix(*nodriver module*)
def uc_fix(uc: uc):
    uc.core.connection.Listener.listener_loop = listener_loop

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = '12Leg4iVj2rKwloYfrHWQZL9vRt1jwPgn2hBFdNsHB_o'


class ProxyExtension:
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {"scripts": ["background.js"]},
        "minimum_chrome_version": "76.0.0"
    }
    """

    background_js = """
    var config = {
        mode: "fixed_servers",
        rules: {
            singleProxy: {
                scheme: "http",
                host: "%s",
                port: %d
            },
            bypassList: ["localhost"]
        }
    };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        { urls: ["<all_urls>"] },
        ['blocking']
    );
    """

    def __init__(self, host, port, user, password):
        self._dir = os.path.normpath(tempfile.mkdtemp())

        manifest_file = os.path.join(self._dir, "manifest.json")
        with open(manifest_file, mode="w") as f:
            f.write(self.manifest_json)

        background_js = self.background_js % (host, port, user, password)
        background_file = os.path.join(self._dir, "background.js")
        with open(background_file, mode="w") as f:
            f.write(background_js)

    @property
    def directory(self):
        return self._dir

    def __del__(self):
        shutil.rmtree(self._dir)
    

def download_wav(url, file_name):
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Write the content of the response to a file
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f"File downloaded successfully and saved as {file_name}")
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")


def extract_numbers(code):
    # Define a mapping of number words to digits
    number_map = {
        "zero": "0", "one": "1", "on":"1", "two": "2", "to":"2", "three": "3", "tree": "3", "four": "4",
        "five": "5","fi":"5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
    }
    
    # Use regex to find all number words in the code
    words = re.findall(r'\b(?:' + '|'.join(number_map.keys()) + r')\b', code)
    
    # Convert the words to their corresponding digits and join them
    result = ''.join(number_map[word] for word in words)
    
    return result


async def wait_for_captcha(page, driver):
    try:
        for i in range(1, 4):
            # iframe = await page.query_selector('')
            # print(iframe)
            # iframe_id = iframe.node_id
            # print(iframe_id)
            # el = await page.find('Ми хочемо переконатися, що це справді ви, а не робот.')
            # id =  await page.send(cdp.dom.perform_search('html'))
            iframe = await custom_wait(page, "iframe")
            # Get required tab. Not safe in case when tab not found
            iframe_tab: uc.Tab = next(
                filter(
                    lambda x: str(x.target.target_id) == str(iframe.frame_id), driver.targets
                )
            )
            # Fixing websocket url
            iframe_tab.websocket_url = iframe_tab.websocket_url.replace("iframe", "page")
            button = await iframe_tab.select(
                'button[id="captcha__audio__button"]'
            )
            await button.click()
            audio = await iframe_tab.select('audio[src]')
            print(audio)
            audio_attrs = audio.attrs
            audio_src = audio_attrs['src']
            print(audio_src)
            captcha_id = random.randint(1, 99)
            input_file = f"captcha{captcha_id}.wav"
            output_file = f"captcha{captcha_id}.mp3"
            download_wav(audio_src, input_file)
            sound = AudioSegment.from_wav(input_file) 
            sound.export(output_file, format="mp3")
            # el = await page.send(cdp.dom.Node.shadow_root_type(iframe))
            
            # print(audio_link)
            solver = TwoCaptcha('29ada3bf8a7df98cfa4265ea1145c77b')
            result = solver.audio(f'./{output_file}', lang='en')
            play_button = await iframe_tab.select('button[class="audio-captcha-play-button push-button"]')
            await play_button.click()
            time.sleep(6)
            print(result['code'])
            numbers = extract_numbers(result['code'])
            print(numbers)
            os.remove(input_file)
            os.remove(output_file)
            time.sleep(5)
            # govna = await iframe_tab.query_selector('div[class="audio-captcha-input-container"]')
            # await govna.send_keys(numbers)
            audio_input = await iframe_tab.query_selector_all('input[class="audio-captcha-inputs"]')
            print(audio_input)
            for i in range(0, 6):
                audio_input_el = await audio_input[i]
                await audio_input_el.focus()
                await audio_input_el.send_keys(numbers[i]) 
                time.sleep(1)
            # await audio_input.send_keys(numbers)
            time.sleep(20)
    except Exception as e:
        print('wait for captcha', e)


async def custom_wait(page, selector, timeout=10):
    for _ in range(0, timeout):
        try:
            element = await page.query_selector(selector)
            if element: return element
            time.sleep(1)
        except Exception as e: 
            time.sleep(1)
            print(selector, e)
    return False


async def custom_wait_elements(page, selector, timeout=10):
    print('in custom wait')
    for _ in range(0, timeout):
        try:
            element = await page.query_selector_all(selector)
            if element: return element
            time.sleep(1)
        except Exception as e: 
            time.sleep(1)
            print(selector, e)
    return False
    

async def check_for_element(page, selector, click=False, debug=False):
    try:
        element = await page.query_selector(selector)
        if click:
            await element.click()
        return element
    except Exception as e:
        if debug: print("selector", selector, '\n', e)
        return False
    

def get_data_from_google_sheets():
    try:
        # Authenticate with Google Sheets API using the credentials file
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())

        # Connect to Google Sheets API
        service = build("sheets", "v4", credentials=creds)

        # Define the range to fetch (assuming the data is in the first worksheet and starts from cell A2)
        range_name = "main!A2:I"

        # Fetch the data using batchGet
        request = service.spreadsheets().values().batchGet(spreadsheetId=SPREADSHEET_ID, ranges=[range_name])
        response = request.execute()

        # Extract the values from the response
        values = response['valueRanges'][0]['values']

        return values

    except HttpError as error:
        print(f"An HTTP error occurred: {error}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    

def post_request(data):
    try:
        json_data = json.dumps(data)
        
    except Exception as e:
        print(e)
    # Set the headers to specify the content type as JSON
    headers = {
        "Content-Type": "application/json"
    }

    # Send the POST request
    try:
        response = requests.post(f"http://localhost:8000/book", data=json_data, headers=headers)
        print(response)
    except Exception as e:
        print(e)
    # Check the response status code
    if response.status_code == 200:
        print("POST request successful!")
    else:
        print("POST request failed.")


def parse_random_category(value):
    if value == '':
        return ['']
    elif '-' in value:
        return list(map(int, value.split('-')))
    else:
        return [int(value)]
    



async def change_proxy(tab):
    try:
        await tab.get('chrome://extensions/')
        script = """
                (async () => {let data = await chrome.management.getAll(); return data;})();
        """

        extensions = await tab.evaluate(expression=script, await_promise=True)
        # print("extensions", extensions)
        if extensions is None:
            print('Проксі розширення не встановлене!')
            return None
        filtered_extensions = [extension for extension in extensions if "BP Proxy Switcher" in extension['name']]

        vpn_id = [extension['id'] for extension in filtered_extensions if 'id' in extension][0]
        vpn_url = f'chrome-extension://{vpn_id}/popup.html'
        await tab.get(vpn_url)
        time.sleep(2)
        # edit = await tab.select('#editProxyList > small > b')
        # await edit.mouse_click()
        # time.sleep(1)
        # ok_button = await tab.select('#addProxyOK')
        # await ok_button.mouse_click()
        # time.sleep(2)
        select_button = await tab.select('#proxySelectDiv > div > button')
        await select_button.mouse_click()
        time.sleep(2)
        proxy_switch_list = await tab.find_all('#proxySelectDiv > div > div > ul > li')
        if len(proxy_switch_list) == 3:
            await proxy_switch_list[2].scroll_into_view()
            await proxy_switch_list[2].mouse_click()
        else:
            certain_proxy = proxy_switch_list[random.randint(2, len(proxy_switch_list)-1)]
            await certain_proxy.scroll_into_view()
            await certain_proxy.mouse_click()
        time.sleep(5)

        return True
    except Exception as e:
        print('change_proxy function error:', e)
        return False


async def configure_proxy(tab, proxyList):
    try:
        await tab.get('chrome://extensions/')
        script = """
                (async () => {let data = await chrome.management.getAll(); return data;})();
        """

        extensions = await tab.evaluate(expression=script, await_promise=True)
        # print("extensions", extensions)
        if extensions is None: 
            print('Проксі розширення не встановлене!')
            return None
        filtered_extensions = [extension for extension in extensions if "BP Proxy Switcher" in extension['name']]

        vpn_id = [extension['id'] for extension in filtered_extensions if 'id' in extension][0]
        vpn_url = f'chrome-extension://{vpn_id}/popup.html'
        await tab.get(vpn_url)
        # await tab.get(vpn_url)
        delete_tab = await tab.select('#deleteOptions')
        # driver.evaluate("arguments[0].scrollIntoView();", delete_tab)
        await delete_tab.mouse_click()
        time.sleep(1)
        temp = await tab.select('#privacy > div:first-of-type > input')
        await temp.mouse_click()
        time.sleep(1)
        temp1 = await tab.select('#privacy > div:nth-of-type(2) > input')
        await temp1.mouse_click()
        time.sleep(1)
        temp2 = await tab.select('#privacy > div:nth-of-type(4) > input')
        await temp2.mouse_click()
        time.sleep(1)
        temp3 = await tab.select('#privacy > div:nth-of-type(7) > input')
        await temp3.mouse_click()


        optionsOK = await tab.select('#optionsOK')

        # driver.execute_script("arguments[0].scrollIntoView();", optionsOK)
        await optionsOK.mouse_click()
        time.sleep(1)
        edit = await tab.select('#editProxyList > small > b')
        # driver.execute_script("arguments[0].scrollIntoView();", edit)
        await edit.mouse_click()
        time.sleep(1)
        text_area = await tab.select('#proxiesTextArea')
        for proxy in proxyList:
            js_function = f"""
            (elem) => {{
                elem.value += "{proxy}\\n";
                return elem.value;
            }}
            """
            await text_area.apply(js_function)
        time.sleep(1)
        ok_button = await tab.select('#addProxyOK')
        await ok_button.mouse_click()
        
        proxy_auto_reload_checkbox = await tab.select('#autoReload')
       
        await proxy_auto_reload_checkbox.mouse_click()
        time.sleep(2)

        await change_proxy(tab)

        return True
    except Exception as e:
        print('configure_proxy function error:', e)
        return False


async def create_driver(open_url=None, proxy_list=None):
    """
    Create and return an undetected-chromedriver driver (with extensions and optional remote Selenium host).
    """
    print("[DEBUG] Creating driver…")
    cwd = os.getcwd()
    nopecha_dir='NopeCha'
    extension_path = os.path.join(cwd, nopecha_dir)
    host, port = None, None

    if open_url:
        print(f"[DEBUG] Fetching remote Selenium info from {open_url}")
        resp = requests.get(open_url).json()
        if resp.get("code", 1) != 0:
            print(f"[ERROR] {resp.get('msg', 'Unknown error')} – please check ads_id")
            sys.exit(1)
        host_port = resp['data']['ws']['selenium']
        host, port = host_port.split(':')

    # Build nodriver.Config
    if host and port:
        config = nodriver.Config(
            user_data_dir=None,
            headless=False,
            browser_executable_path=None,
            browser_args=None,
            sandbox=True,
            lang='en-US',
            host=host,
            port=int(port)
        )
        print(f"[DEBUG] Using remote Selenium at {host}:{port}")
    else:
        config = nodriver.Config(
            user_data_dir=None,
            headless=False,
            browser_executable_path=None,
            browser_args=None,
            sandbox=True,
            lang='en-US'
        )

    # Add extensions
    print(f"[DEBUG] Adding extension from {extension_path}")
    config.add_extension(extension_path=extension_path)
    print("[DEBUG] Adding EditThisCookieChrome.crx and BPProxySwitcher.crx")
    config.add_extension(extension_path="./EditThisCookieChrome.crx")
    config.add_extension(extension_path="./BPProxySwitcher.crx")

    driver = await uc.Browser.create(config=config)
    print("[DEBUG] Driver created successfully")

    # If using proxies, configure them on the main tab
    if proxy_list:
        print(f"[DEBUG] Configuring proxies: {proxy_list}")
        tab = driver.main_tab
        await configure_proxy(tab, proxy_list)

    return driver

async def login_if_captcha(page, username=None, password=None):
    """
    If a login form is shown, fill in username/password. Otherwise, wait 10 seconds.
    """
    print("[DEBUG] Checking for login/captcha form…")
    try:
        # Wait for the Gigya login form to appear
        form_selector = 'div.idp-static-page div.gigya-composite-control > input[name="username"]'
        username_el = await custom_wait(page, form_selector, timeout=5)
        if username_el and username and password:
            print("[DEBUG] Login form detected—filling credentials")
            # Fill username
            for ch in username:
                await username_el.send_keys(ch)
                time.sleep(0.1)
            # Fill password
            pwd_selector = 'div.idp-static-page div.gigya-composite-control > input[name="password"]'
            password_el = await page.query_selector(pwd_selector)
            for ch in password:
                await password_el.send_keys(ch)
                time.sleep(0.1)
            # Click Submit
            submit_selector = 'div.idp-static-page div.gigya-composite-control > input[type="submit"]'
            submit_el = await page.query_selector(submit_selector)
            await submit_el.mouse_click()
            print("[DEBUG] Submitted login form—waiting 2 seconds")
            time.sleep(2)
        else:
            print("[DEBUG] No login form or missing credentials—sleeping 10s")
            time.sleep(10)
    except Exception as e:
        print(f"[WARN] login_if_captcha encountered exception: {e}")
        time.sleep(10)


async def handle_captcha_dialog(page):
    """
    If there’s a standalone captcha form (not the login form), click to resolve/continue.
    Return True if we handled a captcha-dialog click; False otherwise.
    """
    try:
        captcha_form = await custom_wait(page, 'form[id="form_captcha"]', timeout=3)
        if captcha_form:
            print("[DEBUG] Captcha form detected—attempting to resolve")
            button = await page.query_selector('div#form_input_buttons> #submit_button')
            await button.click()
            # Wait for the “continue” button inside #action
            cont_btn = await custom_wait(page, '#action > #actionButtonSpan', timeout=10)
            if cont_btn:
                await cont_btn.click()
                print("[DEBUG] Clicked continue on captcha dialog")
            return True
    except Exception as e:
        print(f"[WARN] handle_captcha_dialog exception: {e}")
    return False


async def wait_for_initial_page(page, initial_link, username=None, password=None):
    """
    Navigate to initial_link and loop until we hit the “#isolated_header_iframe” marker.
    Handle login and captcha as needed.
    Handle datadome if exists
    """
    print(f"[DEBUG] Navigating to main page {initial_link}")
    await page.get(initial_link)


    # Loop until we find the “#isolated_header_iframe” marker
    while True:
        print("[DEBUG] Checking for main page load…")
        # First: check if login/captcha form is present
        if await custom_wait(page, '#root_content', timeout=5):
            await login_if_captcha(page, username, password)
            continue
        if await custom_wait(page, 'iframe[src^="https://geo.captcha-delivery.com"]', timeout=2):
            user_part    = f"User: {os.getlogin()}."
            browser_part = f"Browser: {adspower_id if adspower_id else browser_id}"
            text = f"CAPTCHA"
            message = "\n".join([user_part + " " + browser_part, text])
            send_slack_message(message)
            # print('trying to delete cookies')
            # delete_cookies('datadome')
            print(Fore.YELLOW + f"Browser {adspower_id if adspower_id else browser_id}: 403!\n")

        # Second: check for standalone captcha form
        if await handle_captcha_dialog(page):
            continue

        # Third: check if “#isolated_header_iframe” is present
        if await custom_wait(page, '#isolated_header_iframe', timeout=10):
            print("[DEBUG] Isolated header iframe found—page ready")
            break

    # Finally, re-navigate to the main page once more
    await page.get(initial_link)
    print("[DEBUG] Final navigation to initial link complete")


async def click_buy_and_inner_buttons(page):
    """
    On the main page, attempt to click the “Buy ticket” button and any nested action button.
    Return once the #performance_container appears.
    """
    print("[DEBUG] Attempting to click Buy buttons…")
    while True:
        try:
            buy_button = await custom_wait(page, "a.btn-main", timeout=2)
            if buy_button:
                print("[DEBUG] Found main Buy button – clicking")
                await buy_button.mouse_click()
        except Exception as e:
            print(f"[WARN] Error clicking main Buy button: {e}")

        try:
            inner_button = await custom_wait(page, 'span.button.action_buttons_0', timeout=2)
            if inner_button:
                print("[DEBUG] Found inner “Buy” action button – hovering & clicking")
                await inner_button.mouse_move()
                await inner_button.mouse_click()
        except Exception as e:
            print(f"[WARN] Error clicking inner Buy button: {e}")

        is_menu = await custom_wait(page, '#performance_container', timeout=5)
        if is_menu:
            print("[DEBUG] Performance container located – proceeding")
            break


async def get_available_matches(page, match_names):
    """
    Scan the performances list and return a list of dicts { match_name: <li_handle> }
    for any match whose availability != “Sold out” and whose name is in match_names.
    """
    print("[DEBUG] Scanning available matches…")
    ul_elements = await page.query_selector_all('ul.performances_group_container.semantic-no-styling')
    found = []

    for ul in ul_elements:
        lis = await ul.query_selector_all('li')
        for li in lis:
            # Grab availability bullet
            try:
                avail_el = await li.query_selector('div.perf_details div.ticket_availability span.availability_bullet')
                availability = avail_el.attrs.get('aria-label') or avail_el.attrs.get('aria-description')
            except:
                availability = None

            if availability == "Sold out":
                continue

            # Grab team names
            team_spans = await li.query_selector_all('div.perf_details p span.name')
            if len(team_spans) >= 2:
                match_str = team_spans[0].text + ' vs ' + team_spans[1].text
            else:
                continue

            if match_str in match_names:
                print(f"[DEBUG] Match available: {match_str}")
                found.append({match_str: li})

    return found


async def select_random_match(page, match_list, reload_time):
    """
    Loop until we find at least one available match; then pick one at random, click it, and return its key.
    """
    print("[DEBUG] Selecting a random available match…")
    match_names = [m[0] for m in match_list]

    while True:
        available = await get_available_matches(page, match_names)
        if not available:
            print("[DEBUG] No available match – reloading after sleep")
            time.sleep(random.randint(reload_time[0], reload_time[1]))
            continue

        # Pick a random match from the list of dicts
        choice = random.choice(available)
        match_key, li_handle = next(iter(choice.items()))
        print(f"[DEBUG] Chosen match: {match_key}")
        await li_handle.scroll_into_view()
        await li_handle.mouse_click()
        return match_key


async def get_categories_for_match(match_list, selected_match_key):
    """
    Given the list [(match_name, categories_dict), ...], return the categories_dict for the selected match.
    """
    print(f"[DEBUG] Fetching categories for selected match '{selected_match_key}'")
    for name, categories in match_list:
        if name == selected_match_key:
            return categories
    return None


async def find_and_select_category(page, categories_dict, reload_time):
    """
    On the event page, scan the “table > tbody > tr[data-conditionalrateid]” elements to find 
    any category that’s available (selectable <select>), matches our categories_dict, and pick a valid quantity.
    Returns (quantity_selector_handle, desired_quantity_str) if found, else None.
    """
    print("[DEBUG] Entering category-selection loop…")

    # Check if all values in categories_dict are empty strings => treat as “take first available category”
    is_empty = all(value == '' for value in categories_dict.values())

    while True:
        # Reload/back to ensure the table is loaded fresh
        await page.get()
        await page.back()
        event_form = await custom_wait(page, '#event_form', timeout=60)
        if not event_form:
            print("[DEBUG] Event form not found – retrying")
            continue

        table_rows = await page.query_selector_all('table > tbody > tr[data-conditionalrateid]')
        if not table_rows:
            print("[DEBUG] No table rows found – retrying")
            time.sleep(1)
            continue

        last_seen_cat_name = None
        candidate_options = []

        for row in table_rows:
            # Determine the “category text” (some rows inherit from above)
            category_cell = await row.query_selector('.category')
            cell_text = category_cell.text.strip() if category_cell else ''
            if cell_text:
                last_seen_cat_name = cell_text

            # Skip if the row has class “category_unavailable”
            row_classes = row.attrs.get('class_', '')
            if 'category_unavailable' in row_classes:
                continue

            # Check if a <select> is inside “td.quantity”
            select_el = await row.query_selector('td.quantity > select')
            if not select_el:
                continue  # no availability to pick

            # Determine which category name to compare against
            compare_name = cell_text or last_seen_cat_name
            if not compare_name:
                continue

            # If we’re matching categories explicitly
            if compare_name in categories_dict:
                desired_quantity_str = categories_dict[compare_name]
                if not is_empty and desired_quantity_str == '':
                    continue  # user said “don’t pick this category”
                # Add to candidates: (row_handle, desired_quantity_str)
                candidate_options.append((row, desired_quantity_str))

        if not candidate_options:
            print("[DEBUG] No available categories matched – sleeping before retry")
            time.sleep(random.randint(reload_time[0], reload_time[1]))
            continue

        # Randomly pick one of the candidate categories
        row_handle, qty_str = random.choice(candidate_options)
        print(f"[DEBUG] Selected category row with desired qty '{qty_str}'")
        await row_handle.scroll_into_view()

        # Find the <select> and decide which <option> to pick
        select_el = await row_handle.query_selector('td.quantity > select')
        parsed_values = parse_random_category(qty_str)  # e.g. "1-2" => [1,2]

        option_to_select = None
        options_list = await select_el.query_selector_all('option')
        max_option_val = len(options_list) - 1

        if parsed_values:
            if len(parsed_values) > 1:
                min_val, max_val = parsed_values
                if min_val <= max_option_val <= max_val:
                    option_to_select = await select_el.query_selector(f'option[value="{max_option_val}"]')
                elif max_option_val >= max_val:
                    option_to_select = await select_el.query_selector(f'option[value="{max_val}"]')
            else:
                single_val = parsed_values[0]
                if single_val != 0 and single_val <= max_option_val:
                    option_to_select = await select_el.query_selector(f'option[value="{single_val}"]')

        if option_to_select:
            await select_el.click()
            await option_to_select.scroll_into_view()
            await option_to_select.select_option()
            print(f"[DEBUG] Selected quantity option '{option_to_select.attrs.get('value')}'")
            return select_el  # Return the <select> handle so caller can click “Book”

        # If we got here, no valid option in this row—remove it and retry
        print("[DEBUG] No valid quantity found in this category—retrying")
        candidate_options.remove((row_handle, qty_str))
        if not candidate_options:
            print("[DEBUG] Exhausted category options—waiting then retry")
            time.sleep(random.randint(reload_time[0], reload_time[1]))
            continue


async def finalize_booking(page, select_el):
    """
    After a category/quantity is selected, click “Book” and wait for success. Play sound and extract info.
    """
    print("[DEBUG] Clicking Book button…")
    book_btn = await page.query_selector('#book')
    await book_btn.scroll_into_view()
    await book_btn.mouse_click()

    # Check if a captcha dialog pops up again
    captcha_dialog = await custom_wait(page, '#captcha_dialog', timeout=5)
    if captcha_dialog:
        print("[DEBUG] Captcha dialog after booking—clicking continue…")
        cont_invis = await custom_wait(captcha_dialog, '#captcha_dialog_continue_invisible', timeout=3)
        await cont_invis.scroll_into_view()
        await cont_invis.mouse_click()
        # Wait longer for success section
        success_section = await custom_wait(page, 'section.message.success', timeout=50)
    else:
        success_section = await custom_wait(page, 'section.message.success', timeout=10)

    if success_section:
        print("[INFO] Booking succeeded—playing notification sound")
        sound, fs = sf.read('notify.wav', dtype='float32')
        sd.play(sound, fs)
        sd.wait()

        # Extract match number, total price, unit price, description
        match_num_el = await custom_wait(page, 'span.match_round_name.perf_info_list_content', timeout=1)
        total_price_el = await custom_wait(page, 'td.stx_tfooter.reservation_amount span.int_part', timeout=1)
        unit_price_el = await custom_wait(page, 'td.unit_price span.int_part', timeout=1)
        desc_el = await custom_wait(page, 'p.semantic-no-styling-no-display.description', timeout=1)

        match_number = match_num_el.text.strip() if match_num_el else ''
        match_amount = f"€ {total_price_el.text.strip()}" if total_price_el else ''
        match_unit_price = f"€ {unit_price_el.text.strip()}" if unit_price_el else ''
        description_text = desc_el.text.strip() if desc_el else ''

        print(f"[INFO] Match: {match_number}, Total: {match_amount}, Unit: {match_unit_price}, Category: {description_text}")

        data_to_post = {
            "match_number": match_number,
            "total_price": match_amount,
            "unit_price": match_unit_price,
            "category": description_text
        }
        try:
            post_request(data_to_post)
            print("[DEBUG] Sent post-request with booking details")
        except Exception as e:
            print(f"[WARN] post_request failed: {e}")

        input("Press Enter to continue after booking…")
        await page.back()

        # Reset quantity back to zero if needed
        zero_option = await select_el.query_selector('option[value="0"]')
        if zero_option:
            await select_el.select_option()
            print("[DEBUG] Reset quantity to 0")
    else:
        print("[WARN] Booking may have failed (no success message)")


async def main(i, data, reload_time, username=None, password=None, proxy_list=None, adspower_api=None, adspower_id=None):
    """
    Top-level orchestration: set up driver, wait for initial page, click buy, select match & category, then finalize booking.
    """
    if adspower_api and adspower_id:
        adspower_link = f"{adspower}/api/v1/browser/start?user_id={adspower_id}"
    initial_link = 'https://nationsleague.tickets.uefa.com/'
    driver = await create_driver(open_url=adspower_link, proxy_list=proxy_list)
    print(f"[DEBUG] Navigating to setup page for NopeCha…")
    await page.get('https://nopecha.com/setup#sub_1NnGb4CRwBwvt6ptDqqrDlul|keys=|enabled=true|disabled_hosts=|hcaptcha_auto_open=true|hcaptcha_auto_solve=true|hcaptcha_solve_delay=true|hcaptcha_solve_delay_time=3000|recaptcha_auto_open=true|recaptcha_auto_solve=true|recaptcha_solve_delay=true|recaptcha_solve_delay_time=1000|funcaptcha_auto_open=true|funcaptcha_auto_solve=true|funcaptcha_solve_delay=true|funcaptcha_solve_delay_time=0|awscaptcha_auto_open=true|awscaptcha_auto_solve=true|awscaptcha_solve_delay=true|awscaptcha_solve_delay_time=0|turnstile_auto_solve=true|turnstile_solve_delay=true|turnstile_solve_delay_time=1000|perimeterx_auto_solve=false|perimeterx_solve_delay=true|perimeterx_solve_delay_time=1000|textcaptcha_auto_solve=true|textcaptcha_solve_delay=true|textcaptcha_solve_delay_time=0|textcaptcha_image_selector=#img_captcha|textcaptcha_input_selector=#secret|recaptcha_solve_method=Image')

    while True:
        try:
            page = driver.main_tab
            await wait_for_initial_page(page, initial_link, username=username, password=password)

            # Step: click buy buttons until performance container appears
            await click_buy_and_inner_buttons(page)

            # Reject cookies if shown, toggle “unavailable matches” if present
            cookie_box = await custom_wait(page, 'div > #onetrust-reject-all-handler', timeout=1)
            if cookie_box:
                print("[DEBUG] Rejecting cookies…")
                await cookie_box.mouse_click()

            toggle_checkbox = await custom_wait(page, "#toggle_unavailable_matches", timeout=1)
            if toggle_checkbox:
                print("[DEBUG] Toggling ‘Show unavailable matches’ checkbox")
                await toggle_checkbox.mouse_click()
            
            page = await page.get(initial_link)
            await click_buy_and_inner_buttons(page)
            # Step: choose a match
            selected_match_key = await select_random_match(page, data, reload_time)

            # Step: get category dictionary for that match
            categories = await get_categories_for_match(data, selected_match_key)
            if categories is None:
                print(f"[ERROR] Could not find categories for match {selected_match_key}")
                return

            # Step: find and select a category/quantity
            select_el = await find_and_select_category(page, categories, reload_time)
            if select_el:
                # Step: finalize booking
                await finalize_booking(page, select_el)
            else:
                print("[WARN] No category was ever selected—exiting main loop")
        except Exception as e:
            print(f"[ERROR] main encountered exception: {e}")
            time.sleep(60)
