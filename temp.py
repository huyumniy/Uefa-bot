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
from asyncio import iscoroutine, iscoroutinefunction
from utils.helpers import extract_domain
import logging
import json
import asyncio
import itertools
import socket
from pprint import pprint
import eel
from colorama import init, Fore

init(autoreset=True)
logger = logging.getLogger("uc.connection")

accounts = []
data = []
seat_select = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/seat_select.mhtml'
seat_selected = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/seat_selected.mhtml'
seat_selected_2 = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/seat_selected_2.mhtml'
seats = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/seats.mhtml'
seats2 = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/seats2.mhtml'
stadium = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/stadium.mhtml'
stadium_category = 'file:///C:/Users/vladk/OneDrive/%D0%A0%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9%20%D1%81%D1%82%D0%BE%D0%BB/work/uefa-bot/cast/stadium_category.mhtml'


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

    return driver

async def define_page_type(page):
    event_form = await custom_wait(page, '#event_form', timeout=2)
    resale_form = await custom_wait(page, '#ResaleItemFormModel', timeout=2)
    
    page_type = None

    if event_form: page_type = 'event_form'
    elif resale_form: page_type = 'resale_form'
    return page_type


async def find_and_select_category(page, categories_dict, reload_time):
    print(' in find and select category')


async def find_and_select_category_resale(page, categories_dict, reload_time):
    print('find and select category resale')
    global data, accounts, seat_select, seats, seats2, \
    seat_selected, seat_selected_2, stadium, stadium_category

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

    for category_checkbox in categories_checkbox:
        await category_checkbox.click()
    desired_linear_gradient_id = category_name_to_linear_gradient_id[random_filtered_category]
    print('[DEBUG] desired_linear_gradient_id', desired_linear_gradient_id)
    desired_checkbox = await check_for_element(page, f'.categories_table > div[id*="{desired_linear_gradient_id}"]')
    if not desired_checkbox: return False
    await desired_checkbox.click()
    time.sleep(1)
    print('checkbox is checked')
    available_polygons = await check_for_elements(page, f'polygon[fill*="{desired_linear_gradient_id}"]')
    print('available polygons count', len(available_polygons))

    random_available_polygon = random.choice(available_polygons)
    await random_available_polygon.mouse_click()
    time_limit = 10
    while await custom_wait(
        page, '.loading[style="display: block;"]',
        timeout=1) or time_limit > 0: time_limit-=1
    await page.get(seats2)
    time.sleep(2)
    available_circles = await check_for_elements(page, f'circle[fill="{category_name_to_color_hex[random_filtered_category]}"]')
    print(len(available_circles), 'available_circles')
    

async def main(
):
    """
    Top-level orchestration: set up driver, wait for initial page, click buy, select match & category, then finalize booking.
    """
    global data, accounts, seat_select, seats, seats2, \
    seat_selected, seat_selected_2, stadium, stadium_category
    reload_time = [45, 60]
    time.sleep(5)
    adspower_link = None
    proxy_list = []
    driver = await create_driver(open_url=adspower_link, proxy_list=proxy_list)
    page = driver.main_tab
    categories = {'Category 1': '4', 'Category 2': '2', 'Category 3': '2', 'Category 4': '', 'Cat. 1 Restricted View': '2', 'Cat. 2 Restricted View': '4', 'Cat. 3 Restricted View': '', 'Cat. 4 Restricted View': '', 'Fans First': '2', 'Prime Seats': '1'}
    while True:
        try:
            await page.get(stadium)
            # Step: define page type
            page_type = await define_page_type(page)
        
            if not page_type:
                print("[DEBUG] Event form not found – retrying")
                continue

            # Step: find and select a category/quantity
            select_el = None
            if page_type == 'resale_form':
                select_el = await find_and_select_category_resale(page, categories, reload_time)
            if select_el:
                time.sleep(30)
        except Exception as e:
            print(f"[ERROR] main encountered exception: {e}")
            time.sleep(60)

if __name__ == "__main__":
    uc.loop().run_until_complete(main())