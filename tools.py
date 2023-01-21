import re
import sys
import yaml
import random
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# Random function to ensure that the random values generated by function are truly random and not predictable:
def randomMe(my_lists, seed=None):
    # Seed the random number generator
    random.seed(seed, version=2)
    # Shuffle the list to prevent any bias
    random.shuffle(my_lists)
    # Randomly select and item from the list
    return random.choice(my_lists)


# Random time interval between each requests made to server.
# You can decrease the time interval for faster scraping, however I discourage you to do so as it may hurt the server and Amazon may ban your IP address.
# Scrape responsibly:
def randomTime(val):
    ranges = [i for i in range(3, val+1)]
    return randomMe(ranges)


# Hundreds of thousands of user agents for server:
def userAgents():
    with open('user-agents.txt') as f:
        agents = f.read().split("\n")
        return randomMe(agents)


# function for yaml selectors:
def yamlMe(selectors):
    with open(f"{selectors}.yaml") as file:
        sel = yaml.load(file, Loader=yaml.SafeLoader) 
        return sel


# Try except to return the value when there is no element. This helps to avoid throwing an error when there is no element.
class TryExcept:
    def text(self, element):
        try:
            return element.inner_text().strip()
        except AttributeError:
            return "N/A"

    def attributes(self, element, attr):
        try:
            return element.get_attribute(attr)
        except AttributeError:
            return "N/A"


def amazonMe(head):
    print(f"Initiating the Amazon automation | Powered by Playwright.")
    amazon_dicts = []
    catchClause = TryExcept()
    selectors = yamlMe('selector')

    user_input = str(input("Enter a URL:> "))   
    
    # regex pattern to verify if the entered link is correct Amazon link:
    # Below regex pattern is to verify certain pattern on amazon link after clicking products, it may look confusing.
    amazon_link_pattern = re.search("^https://www.amazon\.(com|co\.uk)/s\?.+", user_input)
    if amazon_link_pattern == None:
        print(f"Invalid link. Please enter an amazon link including product category of your choice.")
        sys.exit()

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=head, slow_mo=3*1000)
        context = browser.new_context(user_agent=userAgents())
        page = context.new_page()
        page.goto(user_input)

        page.wait_for_timeout(timeout=randomTime(4)*1000)
        
        # Below variable is for the searched product, there could be more that two elements for it.
        try:
            product_name = page.query_selector(selectors['product_name_one']).inner_text().strip()
        except AttributeError:
            product_name = page.query_selector(selectors['product_name_two']).inner_text().strip()        
        
        try:
            page.wait_for_selector(selectors['main_content'], timeout=10*1000)
        except PlaywrightTimeoutError:
            print(f"Content loading error. Please try again in few minute.")        
        
        try:
            last_page = page.query_selector(
                selectors['total_page_number_first']).inner_text().strip()
        except AttributeError:
            last_page = page.query_selector_all(selectors['total_page_number_second'])[-2].get_attribute('aria-label').split()[-1]

        print(f"Number of pages | {last_page}.")
        print(f"Scraping | {product_name}.")

        for click in range(1, int(last_page)):
            print(f"Scraping page | {click}")
            page.wait_for_timeout(timeout=randomTime(8)*1000)
            for content in page.query_selector_all(selectors['main_content']):
                data = {
                    "Product": catchClause.text(content.query_selector(selectors['hyperlink'])),
                    "ASIN": catchClause.attributes(content, 'data-asin'),
                    "Price": catchClause.text(content.query_selector(selectors['price'])),
                    "Original price": catchClause.text(content.query_selector(selectors['old_price'])),
                    "Review": catchClause.text(content.query_selector(selectors['review'])),
                    "Review count": re.sub(r"[()]", "", catchClause.text(content.query_selector(selectors['review_count']))),
                    "Hyperlink": f"""http://www.amazon.com{catchClause.attributes(content.query_selector(selectors['hyperlink']), 'href')}""",
                    "Image": f"""{catchClause.attributes(content.query_selector(selectors['image']), 'src')}""",
                }
                amazon_dicts.append(data)

            try:
                page.query_selector(selectors['next_button']).click()
            except AttributeError:
                print(f"Oops content loading error beyond this page. Issue on url {page.url} | number:> {click}")
                break

        browser.close()

    print(f"Scraping done. Now exporting to excel database.")

    df = pd.DataFrame(amazon_dicts)
    df.to_excel(f"{product_name}-Amazon database.xlsx", index=False)
    print(f"{product_name} is saved.")

