import os
import json
import requests
import nodriver as uc
import random
from nodriver import cdp
import sounddevice as sd
import soundfile as sf
import threading
import time
import sys, os
from utils.sheetsApi import GoogleSheetClient
from utils.helpers import filter_by_dict_value
from filtration import get_nearby_chains, get_random_chain_slice, find_nearby_chains
from asyncio import iscoroutine, iscoroutinefunction
from utils.helpers import extract_domain
import logging
import json
import asyncio
import itertools
import socket
import eel
from colorama import init, Fore

init(autoreset=True)
logger = logging.getLogger("uc.connection")

accounts = []
data = []

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
    
async def check_for_elements(page, selector, debug=False):
    try:
        element = await page.query_selector_all(selector)
        return element
    except Exception as e:
        if debug: print("selector", selector, '\n', e)
        return False
    

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
        response = requests.post(f"http://localhost:8001/book", data=json_data, headers=headers)
        print(response)
    except Exception as e:
        print(e)
    # Check the response status code
    if response.status_code == 200:
        print("POST request successful!")
    else:
        print("POST request failed.")


def send_slack_message(data):
    try:
        json_data = json.dumps({"data": data})
        headers = {
            "Content-Type": "application/json"
        }
        try:
            response = requests.post("http://localhost:8010/book", data=json_data, headers=headers)
            if response.status_code == 200:
                print("POST request successful!")
            else:
                raise Exception("POST request failed with status code: " + str(response.status_code))
        except Exception as e:
            print(e)
    except Exception as e:
        print(e)


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
        time.sleep(2)
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
        if resp["code"] != 0:
            print(resp["msg"])
            print("please check ads_id")
            sys.exit()
        host, port = resp['data']['ws']['selenium'].split(':')

    # Build nodriver.Config
    if host and port:
        config = uc.Config(
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
        config = uc.Config(
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
        tab = driver.main_tab
        await configure_proxy(tab, proxy_list)

    return driver

async def is_available_matches_checked(page):
    try:
        script = """
        (function() {
            return document.querySelector('#toggle_unavailable_matches').checked
        }())
        """
        # await the promise, return the JS value directly
        checkbox_value = await page.evaluate(
            script,
            await_promise=True,
            return_by_value=True
        )
        return checkbox_value
    except:
        return False

async def login_if_captcha(page):
    """
    If a login form is shown, fill in username/password. Otherwise, wait 10 seconds.
    """
    print("[DEBUG] Checking for login/captcha form…")
    try:
        random_account_idx = random.randint(0, len(accounts) - 1)
        username = accounts[random_account_idx][0]
        password = accounts[random_account_idx][1]
        print(username, password)

        form_selector = 'div.idp-static-page div.gigya-composite-control > input[name="username"]'
        username_el = await custom_wait(page, form_selector, timeout=5)
        if username_el and username and password:
            print("[DEBUG] Login form detected—filling credentials")
            await username_el.clear_input()
            # Fill username
            for ch in username:
                await username_el.send_keys(ch)
                time.sleep(0.1)
            # Fill password
            pwd_selector = 'div.idp-static-page div.gigya-composite-control > input[name="password"]'
            password_el = await page.query_selector(pwd_selector)
            await password_el.clear_input()
            for ch in password:
                await password_el.send_keys(ch)
                time.sleep(0.1)
            # Click Submit
            submit_selector = 'div.idp-static-page div.gigya-composite-control > input[type="submit"]'
            submit_el = await page.query_selector(submit_selector)
            await submit_el.mouse_click()
            print("[DEBUG] Submitted login form—waiting 2 seconds")
            time.sleep(2)
            is_error = await check_for_element(page, 'div.idp-static-page div.gigya-composite-control > .gigya-error-msg-active')
            if is_error:
                print("Invalid account was passed, waiting for 60 sec to switch account")
                time.sleep(60)
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


async def wait_for_initial_page(page, actual_link, browser_id=None):
    """
    Navigate to actual_link and loop until we hit the “#isolated_header_iframe” marker.
    Handle login and captcha as needed.
    Handle datadome if exists
    """
    print(f"[DEBUG] Navigating to main page {actual_link}")
    await page.get(actual_link)

    # Loop until we find the “#isolated_header_iframe” marker
    while True:
        print("[DEBUG] Checking for main page load…")
        # First: check if login/captcha form is present
        if await custom_wait(page, '#root_content', timeout=5):
            await login_if_captcha(page)
            continue
        if await custom_wait(page, 'iframe[src^="https://geo.captcha-delivery.com"]', timeout=2):
            user_part    = f"User: {os.getlogin()}."
            text = f"CAPTCHA"
            message = "\n".join([user_part + " " + browser_id, text])
            print('message', message)
            send_slack_message(message)
            # print('trying to delete cookies')
            # delete_cookies('datadome')
            print(Fore.YELLOW + f"{browser_id}: CAPTCHA!\n")

        # Second: check for standalone captcha form
        if await handle_captcha_dialog(page):
            continue

        # Third: check if “#isolated_header_iframe” is present
        if await custom_wait(page, '#isolated_header_iframe', timeout=10):
            print("[DEBUG] Isolated header iframe found—page ready")
            break

    # Finally, re-navigate to the main page once more
    await page.get(actual_link)
    print("[DEBUG] Final navigation to initial link complete")


async def click_buy_and_inner_buttons(page):
    """
    On the main page, attempt to click the “Buy ticket” button and any nested action button.
    Return once the #performance_container appears.
    """
    print("[DEBUG] Attempting to click Buy buttons…")
    while True:
        await reject_cookies(page)
        try:
            buy_button = await custom_wait(page, "a.btn-main", timeout=2)
            if buy_button:
                print("[DEBUG] Found main Buy button – clicking")
                await buy_button.mouse_click()
        except Exception as e:
            print(f"[WARN] Error clicking main Buy button: {e}")
        try:
            link_to_move = await custom_wait(page, '#introduction > p > a:nth-child(2)', timeout=2)
            if link_to_move:
                print('[DEBUG] Found main Link - clicking')
                await link_to_move.mouse_click()
        except Exception as e:
            print(f"[WARN] Error clicking Link: {e}")
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
            return False

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


async def define_page_type(page):
    event_form = await custom_wait(page, '#event_form', timeout=2)
    resale_form = await custom_wait(page, '#ResaleItemFormModel', timeout=2)
    
    page_type = None

    if event_form: page_type = 'event_form'
    elif resale_form: page_type = 'resale_form'
    return page_type


async def find_and_select_category(page, categories_dict, reload_time):
    """
    On the event page, scan the “table > tbody > tr[data-conditionalrateid]” elements to find 
    any category that’s available (selectable <select>), matches our categories_dict, and pick a valid quantity.
    Returns (quantity_selector_handle, desired_quantity_str) if found, else None.
    """
    print("[DEBUG] Entering category-selection loop…")

    # Check if all values in categories_dict are empty strings => treat as “take first available category”
    is_empty = all(value == '' for value in categories_dict.values())

    for _ in range(0, 5):
        # Reload/back to ensure the table is loaded fresh
        await page.get()
        await page.back()

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
                    continue 
                candidate_options.append((row, desired_quantity_str))

        if not candidate_options:
            print("[DEBUG] No available categories matched – sleeping before retry")
            time.sleep(random.randint(reload_time[0], reload_time[1]))
            continue

        row_handle, qty_str = random.choice(candidate_options)
        print(f"[DEBUG] Selected category row with desired qty '{qty_str}'")
        await row_handle.scroll_into_view()

        select_el = await row_handle.query_selector('td.quantity > select')
        parsed_values = parse_random_category(qty_str)

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
            return select_el

       
        print("[DEBUG] No valid quantity found in this category—retrying")
        candidate_options.remove((row_handle, qty_str))
        if not candidate_options:
            print("[DEBUG] Exhausted category options—waiting then retry")
            time.sleep(random.randint(reload_time[0], reload_time[1]))
            continue


async def find_and_select_category_resale2(page, categories_dict, reload_time):
    current_location = await get_location(page)
    print(current_location, 'current_location')
    domain = 'https://' + current_location.split('https://')[1].split('/')[0]
    performance_id = current_location.split('performanceId=')[1].split('&')[0]
    product_id = current_location.split('productId=')[1].split('&')[0]
    desired_location = f'{domain}/ajax/resale/freeSeats?productId={product_id}&performanceId={performance_id}'
    print(desired_location, 'desired_location')
    categories_legend = await check_for_elements(page, '.seat-info-category-legend')

    categories_name = [(await check_for_element(category_legend, 'p > label > span:nth-child(2)')).text for category_legend in categories_legend]
    filtered_categories = filter_by_dict_value(categories_dict, categories_name)
    random_filtered_category = random.choice(filtered_categories)
    seats_response = await request_seats(page, desired_location)
    print(int(categories_dict[random_filtered_category]), random_filtered_category)
    chains = find_nearby_chains(seats_response["features"], int(categories_dict[random_filtered_category]), random_filtered_category)
    print(len(chains))
    if not chains: return False
    chain = random.choice(chains)
    print('chosen chain:', chain)
    for seat in chain:
        seat_info_url = f'https://womenseuro-resale.tickets.uefa.com/ajax/resale/seatInfo?productId={product_id}&perfId={performance_id}&seatId={seat["id"]}&advantageId=&ppid=&reservationIdx=&crossSellId='
        seat_info_response = send_request(seat_info_url)
        
        area_id = seat['properties']['areaId']
        block_id = seat['properties']['blockId']
        tariff_id = seat['properties']['tariffId']
        seat_category_id = seat['properties']['seatCategoryId']
        amount = seat['properties']['amount']

async def find_and_select_category_resale(page, categories_dict, reload_time):
    print('find and select category resale')
    for _ in range(0, 10):
        is_empty = all(value == '' for value in categories_dict.values())
        if is_empty: return False

        categories_legend = await check_for_elements(page, '.seat-info-category-legend')
        categories_checkbox = await check_for_elements(page, 'input[type="checkbox"]')

        categories_name = [(await check_for_element(category_legend, 'p > label > span:nth-child(2)')).text for category_legend in categories_legend]

        # mapping
        category_name_to_color_hex = {
            (await check_for_element(category_legend, 'p > label > span:nth-child(2)')).text:
            (await check_for_element(category_legend, 'p > label > span:nth-child(1)')).attrs.get('style').split(':')[1]
            for category_legend in categories_legend
        }
        category_name_to_linear_gradient_id = {
            (await check_for_element(category_legend, 'p > label > span:nth-child(2)')).text:
            (await check_for_element(category_legend, 'input')).attrs.get('value')
            for category_legend in categories_legend
        }
        print(category_name_to_linear_gradient_id)

        filtered_categories = filter_by_dict_value(categories_dict, categories_name)
        print('[DEBUG] filtered categories', filtered_categories)
        random_filtered_category = random.choice(filtered_categories)
        print('[DEBUG] random_filtered_category', random_filtered_category)
        desired_linear_gradient_id = category_name_to_linear_gradient_id[random_filtered_category]
        print('[DEBUG] desired_linear_gradient_id', desired_linear_gradient_id)

        # logic
        for category_checkbox in categories_checkbox:
            await category_checkbox.mouse_click()
        
        desired_checkbox = await check_for_element(page, f'.categories_table > div[id*="{desired_linear_gradient_id}"]')
        if not desired_checkbox: return False
        await desired_checkbox.mouse_click()
        time.sleep(1)

        available_polygons = await check_for_elements(page, f'polygon[fill*="{desired_linear_gradient_id}"]')
        print('available polygons count', len(available_polygons))
        if not len(available_polygons): return False
        random_available_polygon = random.choice(available_polygons)
        await random_available_polygon.mouse_click()
        time_limit = 10
        while await custom_wait(
            page, '.loading[style="display: block;"]',
            timeout=1) and time_limit > 0: time_limit-=1
        
        time.sleep(2)
        available_circles = await check_for_elements(page, f'circle[fill="{category_name_to_color_hex[random_filtered_category]}"]')
        print(len(available_circles), 'available_circles')
        circles_data = \
        [   
            {
            "x": int(available_circle.attrs.get("cx").split('.')[0]),
            "y": int(available_circle.get("cy").split('.')[0])
            } for available_circle in available_circles
        ]
        print(circles_data, 'circles_data')
        desired_amount_by_category = int(categories_dict[random_filtered_category])
        chains = get_nearby_chains(circles_data, desired_amount_by_category)
        print(chains, 'chains')
        desired_slice = get_random_chain_slice(chains, desired_amount_by_category)
        print(desired_slice, 'desired slice')
        if not desired_slice: 
            for _ in range(0, 4):
                zoom_out = await check_for_element(page, '#zoom-out')
                await zoom_out.mouse_click()
                time.sleep(1)
            continue
        for point in desired_slice:
            desired_circle = await check_for_element(page, f'circle[cx*="{point["x"]}"][cy*="{point["y"]}"]')
            await desired_circle.mouse_click()
            time.sleep(1)
            book_seat = await check_for_element(page, '#add-selected-seat-to-cart')
            await book_seat.mouse_click()
        selection = await check_for_element(page, '#num-tickets')
        print(selection.text)
        if int(selection.text.split('(')[1].split(')')[0])\
        >= desired_amount_by_category:
            return True
        continue
    return False

async def finalize_booking(page, select_el=None):
    """
    After a category/quantity is selected, click “Book” and wait for success. Play sound and extract info.
    """
    print("[DEBUG] Clicking Book button…")
    book_btn = await page.query_selector('#book')
    if not book_btn:
        book_btn = await page.query_selector('#add-to-cart')
    await book_btn.scroll_into_view()
    await book_btn.mouse_click()

    # Check if a captcha dialog pops up again
    captcha_dialog = await custom_wait(page, '#captcha_dialog', timeout=5)
    if captcha_dialog:
        print("[DEBUG] Captcha dialog after booking—clicking continue…")
        time.sleep(2)
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
        
        zero_option = await check_for_element(select_el, 'option[value="0"]')
        if zero_option:
            await select_el.select_option()
            print("[DEBUG] Reset quantity to 0")
    else:
        print("[WARN] Booking may have failed (no success message)")

async def reject_cookies(page):
    cookie_box = await custom_wait(page, 'div > #onetrust-reject-all-handler', timeout=3)
    if cookie_box:
        print("[DEBUG] Rejecting cookies…")
        await cookie_box.mouse_click()


async def main(
    initial_link, browser_id, total_browsers,
    reload_time, slack_push_desired_match=None, proxy_list=None,
    adspower_api=None, adspower_id=None
):
    """
    Top-level orchestration: set up driver, wait for initial page, click buy, select match & category, then finalize booking.
    """
    global data
    global accounts
    time.sleep(5)
    adspower_link = ""
    if adspower_api and adspower_id:
        adspower_link = f"{adspower_api}/api/v1/browser/start?serial_number={adspower_id}"
    
    actual_link = extract_domain(initial_link)
    print(' actual link')
    driver = await create_driver(open_url=adspower_link, proxy_list=proxy_list)
    page = driver.main_tab
    input('continue?')
    print(f"[DEBUG] Navigating to setup page for NopeCha…")
    await page.get('https://nopecha.com/setup#sub_1RWdSzCRwBwvt6ptKAX3W64k|keys=|enabled=true|disabled_hosts=|hcaptcha_auto_open=true|hcaptcha_auto_solve=true|hcaptcha_solve_delay=true|hcaptcha_solve_delay_time=3000|recaptcha_auto_open=true|recaptcha_auto_solve=true|recaptcha_solve_delay=true|recaptcha_solve_delay_time=1000|funcaptcha_auto_open=true|funcaptcha_auto_solve=true|funcaptcha_solve_delay=true|funcaptcha_solve_delay_time=0|awscaptcha_auto_open=true|awscaptcha_auto_solve=true|awscaptcha_solve_delay=true|awscaptcha_solve_delay_time=0|turnstile_auto_solve=true|turnstile_solve_delay=true|turnstile_solve_delay_time=1000|perimeterx_auto_solve=false|perimeterx_solve_delay=true|perimeterx_solve_delay_time=1000|textcaptcha_auto_solve=true|textcaptcha_solve_delay=true|textcaptcha_solve_delay_time=0|textcaptcha_image_selector=#img_captcha|textcaptcha_input_selector=#secret|recaptcha_solve_method=Image')
    browser_part = f"Browser: {adspower_id if adspower_id else browser_id}"

    while True:
        try:
            await wait_for_initial_page(page, actual_link, browser_id=browser_part)

            # Step: click buy buttons until performance container appears
            await click_buy_and_inner_buttons(page)

            await reject_cookies(page)

            toggle_checkbox = await custom_wait(page, "#toggle_unavailable_matches", timeout=1)
            if toggle_checkbox:
                is_checked = await is_available_matches_checked(page)
                if is_checked:
                    print("[DEBUG] Toggling ‘Display only available matches’ checkbox")
                    await check_for_element(page, '#toggle_unavailable_matches', True)
                    time.sleep(1)
            # Step: choose a match
            selected_match_key = await select_random_match(page, data, reload_time)
            if not selected_match_key:
                continue
            
            if slack_push_desired_match:
                user_part    = f"User: {os.getlogin()}."
                text = f"З'явився матч: {selected_match_key}, {actual_link}"
                message = "\n".join([user_part + " " + browser_part, text])
                send_slack_message(message)

            # Step: get category dictionary for that match
            categories = await get_categories_for_match(data, selected_match_key)
            print(categories, 'categories')
            if categories is None:
                print(f"[ERROR] Could not find categories for match {selected_match_key}")
                time.sleep(random.randint(reload_time[0], reload_time[1]))
                return


            # Step: define page type
            page_type = await define_page_type(page)
        
            if not page_type:
                print("[DEBUG] Event form not found – retrying")
                continue

            # Step: find and select a category/quantity
            select_el = None
            if page_type == 'event_form':
                select_el = await find_and_select_category(page, categories, reload_time)
            elif page_type == 'resale_form':
                select_el = await find_and_select_category_resale2(page, categories, reload_time)
            if select_el:
                # Step: finalize booking
                await finalize_booking(page, select_el)
            else:
                print("[WARN] No category was ever selected—exiting main loop")
                time.sleep(random.randint(reload_time[0], reload_time[1]))
        except Exception as e:
            print(f"[ERROR] main encountered exception: {e}")
            time.sleep(60)


def poll_sheet_every(interval: float, sheets_data_link: str, sheets_accounts_link: str):
    """
    Poll the Google Sheet every `interval` seconds.
    """
    global accounts
    global data
    
    data_client = GoogleSheetClient(sheets_data_link, "main")
    accounts_client = GoogleSheetClient(sheets_accounts_link, "main")
     
    while True:
        try:
            data_response = data_client.fetch_sheet_data()
            accounts_response = accounts_client.fetch_sheet_columns("A2:B")
            print(data_response, accounts_response)
            if not data_response or not accounts_response:
                print(f"Data or accounts response is empty, retrying in {interval} seconds...") 
                time.sleep(interval)
                continue
            
            data = data_response
            accounts = accounts_response
        except Exception as e:
            print(f"Error fetching sheet data: {e!r}")
        time.sleep(interval)


@eel.expose
def start_workers(initial_link, browsersAmount, reload_time,
    slack_push_desired_match, proxyInput, adspowerApi, 
    adspowerIds, googleSheetsDataLink=None, googleSheetsAccountsLink=None,
):
    if googleSheetsAccountsLink:
        polling_thread = threading.Thread(
            target=poll_sheet_every,
            args=(60.0, googleSheetsDataLink, googleSheetsAccountsLink),
            daemon=True 
        )
        polling_thread.start()
    
    threads = []
    print('start_workers', initial_link, browsersAmount, reload_time,
     slack_push_desired_match, adspowerApi,adspowerIds,
     googleSheetsDataLink, googleSheetsAccountsLink)

    # Case: using adspower API
    if not browsersAmount and all([adspowerApi, adspowerIds]):
        total = len(adspowerIds)
        for i in range(1, total + 1):
            ads_id = adspowerIds[i - 1]
            # bind i, total, ads_id into lambda defaults
            thread = threading.Thread(
                target=lambda idx=i, tot=total, aid=ads_id:
                    uc.loop().run_until_complete(
                        main(initial_link, idx, tot, reload_time, slack_push_desired_match, proxyInput, adspowerApi, aid)
                    )
            )
            threads.append(thread)
            thread.start()

    # Case: fixed number of browsers
    elif browsersAmount and not any([adspowerApi, adspowerIds]):
        total = int(browsersAmount)
        for i in range(1, total + 1):
            # bind i, total into lambda defaults
            thread = threading.Thread(
                target=lambda idx=i, tot=total:
                    uc.loop().run_until_complete(
                        main(initial_link, idx, tot, reload_time, slack_push_desired_match, proxyInput,)
                    )
            )
            threads.append(thread)
            thread.start()

    # Wait for all to finish
    for thread in threads:
        thread.join()


def is_port_open(host, port):
  try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    sock.connect((host, port))
    return True
  except (socket.timeout, ConnectionRefusedError):
    return False
  finally:
    sock.close()


async def get_location(driver):
    script = f"""
    (function() {{
        return window.location.href
    }}())
    """
    # await the promise, return the JS value directly
    result = await driver.evaluate(
        script,
        await_promise=True,
        return_by_value=True
    )
    return result



async def request_seats(driver, url):
    script = f"""
    (async function() {{
      try {{
        const res = await fetch("{url}");
        if (!res.ok) return null;
        const data = await res.json();
        return JSON.stringify(data);
      }} catch (e) {{
        return null;
      }}
    }})()
    """
    json_str = await driver.evaluate(
        script,
        await_promise=True,
        return_by_value=True
    )
    if json_str is None:
        return None
    return json.loads(json_str)


if __name__ == "__main__":
    eel.init('gui')

    port = 8000
    while True:
        try:
            if not is_port_open('localhost', port):
                eel.start('main.html', size=(600, 800), port=port)
                break
            else:
                port += 1
        except OSError as e:
            print(e)
