from tools.tool import TryExcept, yaml_load, randomTime, userAgents, verify_amazon, flat, Response, domain, region
from bs4 import BeautifulSoup
import asyncio
import re


class Amazon:
    """
    The Amazon class provides methods for scraping data from Amazon.com.

    Attributes:
        headers (dict): A dictionary containing the user agent to be used in the request headers.
        catch (TryExcept): An instance of TryExcept class, used for catchig exceptions.
        scrape (yaml_load): An instance of the yaml_load class, used for selecting page elements to be scraped.
    """

    def __init__(self, base_url):
        """
        Initializes an instance of the Amazon class.
        """
        self.rand_time = 2 * 60
        self.country_domain = domain(base_url)
        self.region = region(base_url)
        # Define a regular expression pattern for currencies in different regions
        self.currency = r'["$₹,R$€£kr()%¥\s]'   # Characters representing various currencies
        # Explanation:
        # - '[$₹,R\$€£kr()%¥\s]': Match any of the characters within the square brackets
        #   - '$': Dollar sign
        #   - '₹': Indian Rupee
        #   - '€': Euro
        #   - '£': Pound Sterling
        #   - 'kr': Krona or Krone
        #   - '()%': Parentheses and percent sign
        #   - '¥': Yen
        #   - '\s': Whitespace characters
        # This regex is intended to identify and capture currency-related symbols and characters in a string.
        # It includes a variety of symbols used across different regions.

        # Caution: Adjusting the random time to a value less than the current setting (2 minutes) for faster scraping may increase the risk of getting IP banned.
                                                # Scrape responsibly:
        self.rand_time = 2 * 60
        self.base_url = base_url
        self.headers = {'User-Agent': userAgents()}
        self.catch = TryExcept()
        self.scrape = yaml_load('selector')

    async def status(self):
        response = await Response(self.base_url).response()
        return response


    async def num_of_pages(self, max_retries = 13):
        """
        Returns the number of pages of search results for the given URL.

        Args:
            url (str): The URL to determine the number of search result pages for.

        Returns:
            int: The number of pages of search results.
        """
        for retry in range(max_retries):
            try:
                content = await Response(self.base_url).content()
                soup = BeautifulSoup(content, 'lxml')
                # Try except clause for index error, this happens if there are only one page:
                try:
                    pages = await self.catch.text(soup.select(self.scrape['pages'])[-1])
                except IndexError:
                    pages = '1'
                # the current pages returns "Previous" instead of number, this only happens there only two pages, that's why I have returned the value 2.
                try:
                    return int(pages)
                except ValueError:
                    return 2
            except ConnectionResetError as e:
                print(f"Connection lost: {str(e)}. Retrying... ({retry + 1} / {max_retries})")
                if retry < max_retries - 1:
                    await asyncio.sleep(5)  # Delay before retrying.
            except Exception as e:
                print(f"Retry {retry + 1} failed: {str(e)}")
                if retry < max_retries - 1:
                    await asyncio.sleep(4)  # Delay before retrying.
        raise Exception(f"Failed to retrieve valid data after {max_retries} retries.")


    async def split_url(self):
        """
        Splits a given Amazon URL into multiple URLs, with each URL pointing to a different page of search results.

        Args:
            -url (str): The Amazon URL to be split.

        Returns:
            -list: A list of URLs, with each URL pointing to a different page of search results.
        """
        # Create a list to store the split URLs, and add the orignal URL to it:
        split_url = [self.base_url]

        # Use the 'num_of_pages' method to get the total number of search result pages for the given URL:
        total_pages = await self.num_of_pages()

        # Use the 'static_connection' method to make a static connection to the given URL and get its HTML content:
        content = await Response(self.base_url).content()
        # Making a soup:
        soup = BeautifulSoup(content, 'lxml')

        # Get the URL of the next button on the search result page and costruct the URL of the next search result page:
        next_link = f"""https://www.amazon.{self.country_domain}{await self.catch.attributes(soup.select_one(self.scrape['next_button']), 'href')}"""
        for num in range(1, total_pages):

            # Replace the 'page' number in the URL with curren tpage number increment by 1:
            next_url = re.sub(r'page=\d+', f'page={num+1}' , next_link)

            # Replace the 'sr_pg_' parameter in the URL with current page number:
            next_url = re.sub(r'sr_pg_\d+', f'sr_pg_{num}', next_url)
            split_url.append(next_url)
        return split_url


    async def getASIN(self, url):
        """
        Extracts the ASIN (Amazon Standard Identification Number) from the given URL.

        Args:
            url (str): The URL to extract the ASIN from.

        Return:
            str: The ASIN extracted from the URL.

        Raises:
            IndexError: If the ASIN cannot be extracted from the URL.
        """
        pattern = r"(?<=dp\/)[A-Za-z|0-9]+"
        try:
            asin = (re.search(pattern, url)).group(0)
        except Exception as e:
            asin = "N/A"
        return asin


    async def product_urls(self, url, max_retries = 13):
        """
        Scrapes product data from the Amazon search results page for the given URL.

        Args:
            -list: A list of dictionaries, with each dictionary containing product data for single product.

        Raises:
            -Expecation: If there is an error while loading the content of the Amazon search results page.
        """
        for retry in range(max_retries):
            try:
                # Use the 'static_connection' method to download the HTML content of the search results bage
                content = await Response(url).content()
                soup = BeautifulSoup(content, 'lxml')

                # Check if main content element exists on page:
                try:
                    soup.select_one(self.scrape['main_content'])
                except Exception as e:
                    return f"Content loading error. Please try again in few minutes. Error message: {e}"
                # Get product card contents from current page:
                card_contents = [f"""https://www.amazon.{self.country_domain}{prod.select_one(self.scrape['hyperlink']).get('href')}""" for prod in soup.select(self.scrape['main_content'])]
                return card_contents
            except ConnectionResetError as se:
                print(f"Connection lost: {str(e)}. Retrying... ({retry + 1} / {max_retries})")
                if retry < max_retries - 1:
                    await asyncio.sleep(5)  # Delay before retrying.
            except Exception as e:
                print(f"Retry {retry + 1} failed: {str(e)}")
                if retry < max_retries - 1:
                    await asyncio.sleep(4)  # Delay before retrying.

        raise Exception(f"Failed to retrieve valid data after {max_retries} retries.")


    async def crawl_url(self):
        page_lists = await self.split_url()
        coroutines = [self.product_urls(url) for url in page_lists]
        results = await asyncio.gather(*coroutines)
        return flat(results)


    async def scrape_product_info(self, url, max_retries = 13):
        amazon_dicts = []
        for retry in range(max_retries):
            try:
                # Retrieve the page content using 'static_connection' method:
                content = await Response(url).content()
                soup = BeautifulSoup(content, 'lxml')
                # return soup.prettify()
                product = soup.select_one(self.scrape['name']).text.strip()
                print(product)
                if product == "N/A":
                    raise Exception("Product is 'N/A' retrying...")
                try:
                    # Try to extract the image link using the second first selector.
                    image_link = soup.select_one(self.scrape['image_link_i']).get('src')
                except Exception as e:
                    image_link = await self.catch.attributes(soup.select_one(self.scrape['image_link_ii']), 'src')
                # finally:
                #     # If the image link cannot be extracted, return an error message:
                #     return f'Content loading error. Please try again in few minutes. Error message || {str(e)}.'
                try:
                    availabilities = soup.select_one(self.scrape['availability']).text.strip()
                except AttributeError:
                    availabilities = 'In stock'
                price = await self.catch.text(soup.select_one(self.scrape['price_us']))
                if 'Page' in price.split():
                    price = await self.catch.text(soup.select_one(self.scrape['price_us_i']))
                if price != "N/A":
                    price = re.sub(self.currency, '', price)
                try:
                    deal_price = await self.catch.text(soup.select(self.scrape['deal_price'])[0])
                    if 'Page' in deal_price.split():
                        deal_price = "N/A"
                except Exception as e:
                    deal_price = "N/A"
                if deal_price != "N/A":
                    deal_price = re.sub(self.currency, '', deal_price)
                try:
                    savings = await self.catch.text(soup.select(self.scrape['savings'])[-1])
                except IndexError:
                    savings = "N/A"
                try:
                    ratings = float(soup.select_one(self.scrape['review']).text.strip().replace(" out of 5 stars", ''))
                except Exception as e:
                    ratings = "N/A"
                try:
                    rating_count = float(re.sub(r'[,\sratings]', '', soup.select_one(self.scrape['rating_count']).text.strip()))
                except Exception as e:
                    rating_count = "N/A"
                store = await self.catch.text(soup.select_one(self.scrape['store']))
                store_link = f"""https://www.amazon.{self.country_domain}{await self.catch.attributes(soup.select_one(self.scrape['store']), 'href')}"""
                # Construct the data dictionary containing product information:
                datas = {
                    'Name': product,
                    'ASIN': await self.getASIN(url),
                    'Region': self.region,
                    'Description': ' '.join([des.text.strip() for des in soup.select(self.scrape['description'])]),
                    'Breakdown': ' '.join([br.text.strip() for br in soup.select(self.scrape['prod_des'])]),
                    'Price': price,
                    'Deal Price': deal_price,
                    'You saved': savings,
                    "Reviews": {
                        "Ratings": ratings,
                        "Count": rating_count,
                    },
                    'Availability': availabilities,
                    'Hyperlink': url,
                    'Images': {
                        "URL":image_link,
                        "URLS": [imgs.get('src') for imgs in soup.select(self.scrape['image_lists'])],
                    },
                    'Store': store.replace("Visit the ", ""),
                    'Store link': store_link,
                }
                amazon_dicts.append(datas)
                return amazon_dicts
            except ConnectionResetError as se:
                print(f"Connection lost: {str(e)}. Retrying... ({retry + 1} / {max_retries})")
                if retry < max_retries - 1:
                    await asyncio.sleep(5)  # Delay before retrying.
            except Exception as e:
                print(f"Retry {retry + 1} failed: {str(e)}")
                if retry < max_retries - 1:
                    await asyncio.sleep(4)  # Delay before retrying.
                return amazon_dicts
        raise Exception(f"Failed to retrieve valid data after {max_retries} retries.")


    async def crawl_url(self):
        page_lists = await self.split_url()
        coroutines = [self.product_urls(url) for url in page_lists]
        results = await asyncio.gather(*coroutines)
        return flat(results)

    async def scrape_and_save(self, url):
        """
        Scrapes data from a given URL, saves it to a file, and returns the scarped data as a Pandas Dataframe.

        Args:
            -interval (int): Time interval in seconds to sleep before scraping the data.
            -url (str): The URL to scrape data from.

        Returns:
            -pd.DataFrame: A Pandas DataFrame containing the scraped data.

        Raises:
            -HTTPError: If the HTTP request to the URL returns an error status code.
            -Exception: If there is an error while scraping the data.
        """
        random_sleep = await randomTime(self.rand_time)
        await asyncio.sleep(random_sleep)
        datas = await self.scrape_product_info(url)
        return datas


    async def concurrent_scraping(self):
        if await verify_amazon(self.base_url):
            return "I'm sorry, the link you provided is invalid. Could you please provide a valid Amazon link for the product category of your choice?"
        print(f"-----------------------| Welcome to Amazon {self.region}. |---------------------------------")
        print(f"Scraping datasets.")
        # Pull the number of pages of the category
        number_pages = await self.num_of_pages()
        print(f"Total pages || {number_pages}.")
         # Split the pagination and convert it list of urls
        product_urls = await self.crawl_url()
        print(f"The extraction process has begun and is currently in progress. The web scraper is scanning through all the links and collecting relevant information. Please be patient while the data is being gathered.")
        coroutines = [self.scrape_and_save(url) for url in product_urls]
        dfs = await asyncio.gather(*coroutines)
        return dfs

