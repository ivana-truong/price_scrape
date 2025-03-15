from dataclasses import dataclass, asdict
import requests
from pathlib import Path
import yaml

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time


@dataclass(frozen=True)
class Car():
    cost: float
    vin: str


# headers = {
#     'priority': 'u=0, i',
#     'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
#     'sec-ch-ua-mobile': '?0',
#     'sec-ch-ua-platform': 'Linux',
#     'sec-fetch-dest': 'document',
#     'sec-fetch-mode': 'navigate',
#     'sec-fetch-site': 'none',
#     'sec-fetch-user': '?1',
#     'upgrade-insecure-requests': '1',
#     'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
# }

def assert_one(find_all_result):
    assert len(find_all_result) == 1, f"Length is {len(find_all_result)}, they are:\n{'\n\n'.join([str(f) for f in find_all_result])}"
    return find_all_result[0]

def get_cost(result_card) -> float:
    card_info = assert_one(result_card.find_all("div", attrs={"class": "card-info"}))
    # NOTE: assert_one is not used here since the specs tooltip is also named this. Relying on later checks.
    cost_tooltip_container = card_info.find_all("span",  attrs={"class": "card-info-tooltip-container"})[0]
    cost_span = assert_one(cost_tooltip_container.find_all("span", attrs={"class": "tds-text--medium tds-text--contrast-high"}))

    cost_str = None
    num_seen = 0
    for word in cost_span.span.string.split(" "):
        if "$" in word:
            if num_seen == 0:
                num_seen += 1
            else:
                cost_str = word
    cost_str = cost_str.replace("$", "").replace(",", "")
    cost = float(cost_str)
    full_cost = cost + 6000
    return full_cost

def get_vin(result_card) -> str:
    data_id = result_card.attrs["data-id"]
    assert isinstance(data_id, str)
    vin = data_id.split("-")[0]
    assert len(vin) == 17
    return vin


def get_cars_from_page(url: str) -> list[Car]:
    chrome_options = Options()
    # # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--disable-gpu")  # Optional: disable GPU rendering for headless mode
    # chrome_options.add_argument("--window-size=1920x1080")  # Set viewport size
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")  # Set a realistic window size
    chrome_options.add_argument("--disable-gpu")  # For better compatibility
    chrome_options.add_argument("--no-sandbox")  # Useful for some systems
    chrome_options.add_argument("--disable-dev-shm-usage")  # Improve headless performance
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  # Simulate a normal browser

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(10)
    html = BeautifulSoup(driver.page_source, parser="lxml", features="lxml")

    # print(html.find_all("article", attrs={"class": "result card"}))
    cars: list[Car] = []
    for result_card in html.find_all("article", attrs={"class": "result card vehicle-card"}):
        cars.append(
            Car(
                cost=get_cost(result_card),
                vin=get_vin(result_card),
            )
        )

    return cars


def save_cars(cars: list[Car], filepath: Path) -> None:
    filepath.write_text(yaml.safe_dump([asdict(car) for car in cars]))


def load_cars(filepath: Path) -> list[Car]:
    if not filepath.exists():
        return []
    data = yaml.load(filepath.read_text(), yaml.SafeLoader)
    assert isinstance(data, list)
    cars: list[Car] = []
    for d in data:
        cars.append(Car(**d))

    return cars


def diff_cars(saved_cars: list[Car], page_cars: list[Car]) -> list[Car]:
    diffed_cars: list[Car] = []
    saved_cars_dict = {car.vin: car for car in saved_cars}
    for new_car in page_cars:
        if new_car.vin not in saved_cars_dict:
            diffed_cars.append(new_car)
        elif new_car.vin in saved_cars_dict and new_car.cost != saved_cars_dict[new_car.vin].cost:
            diffed_cars.append(new_car)

    return diffed_cars


def below_rebate(cars: list[Car]) -> bool:
    car = cars[0]
    if car.cost < 25000:
        return True
    return False


def email(url: str, fsd_cars: list[Car]) -> None:
    if len(fsd_cars) == 0:
        return

    import pprint

    import yagmail

    yag = yagmail.SMTP("ivanatruo@gmail.com", "bwmt cpag wdoq rfge")
    yag.send(
        to=["ivanatruo@gmail.com", "bunjake@gmail.com"],
        subject="NEW USED BIG Ts :O",
        contents=f"Link: {url}\n\n\n{pprint.pformat(fsd_cars)}"
    )



# url = "https://www.tesla.com/inventory/used/my?TRIM=PAWD,LRAWD,LRRWD&arrangeby=plh&zip=78521&range=0"

def check_for_new_cars(url: str, saved_cars_path: Path) -> list[Car]:
    saved_cars = load_cars(saved_cars_path)
    page_cars = get_cars_from_page(url)
    diffed_cars = diff_cars(saved_cars, page_cars)

    save_cars(page_cars, saved_cars_path)

    return diffed_cars

fsd_url = "https://www.tesla.com/inventory/used/my?TRIM=PAWD,LRAWD,LRRWD&INTERIOR=PREMIUM_WHITE&CABIN_CONFIG=FIVE&AUTOPILOT=AUTOPILOT_FULL_SELF_DRIVING&arrangeby=plh&zip=78521&range=0"
new_fsd_cars = check_for_new_cars(fsd_url, Path("/home/ivanatruo/fsd_white_int_cars.yaml"))

email(fsd_url, new_fsd_cars)
