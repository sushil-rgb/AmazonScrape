from tools.tool import TryExcept, Response, yaml_load, randomTime, userAgents, verify_amazon, flat, check_domain, export_sheet, domain
from bs4 import BeautifulSoup
import pandas as pd
import asyncio
import re


class Amazon:
    """
    Initializes an instance of the Amazon class.

    Args:
        - base_url (str): The base URL for Amazon.
        - proxy: The proxy to be used for making requests.

    Attributes:
        - proxy: The proxy to be used for making requests.
        - country_domain: The domain of the country derived from the base URL.
        - region: The region derived from the base URL.
        - currency (str): A regular expression pattern for currencies in different regions.
        - rand_time (int): The random time interval in seconds.
        - base_url (str): The base URL for Amazon.
        - headers (dict): A dictionary containing the user agent to be used in the request headers.
        - catch (TryExcept): An instance of TryExcept class, used for catching exceptions.
        - scrape (yaml_load): An instance of the yaml_load class, used for selecting page elements to be scraped.
    """

    def __init__(self, base_url, proxy):
        """
        Initializes an instance of the Amazon class.
        """
        self.proxy = proxy
        self.country_domain = domain(base_url)
        self.region = check_domain(base_url)

        # Define a regular expression pattern for currencies in different regions
        self.currency = r'[$₹,R\$€£kr()%¥\s]'   # Characters representing various currencies
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

        self.rand_time = 3 * 60
        self.base_url = base_url
        self.headers = {'User-Agent': userAgents()}
        self.catch = TryExcept()
        self.scrape = yaml_load('selector')

    async def status(self):
        """
        Retrieves the HTTP response status code for the given Amazon URL.

        Returns:
            - int: The HTTP response status code.
        """
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

    async def category_name(self):
        resp = Response(self.base_url)
        """
        Retrieves the category name of search results on the given Amazon search page URL.

        Args:
            -url (str): The Amazon search page URL to retrive category name.

        Raises:
            -None.
        """
        content = await resp.content()
        soup = BeautifulSoup(content, 'lxml')
        try:
            searches_results = soup.select_one(self.scrape['searches_I']).text.strip()
        except AttributeError:
            try:
                searches_results = re.sub(r'["]', '', soup.select_one(self.scrape['searches_II']).text.strip())
            except AttributeError:
                try:
                    searches_results = soup.select_one(self.scrape['searches_III']).text.strip()
                except AttributeError:
                    searches_results = soup.select_one(self.scrape['searches_IV']).text.strip()
        category_name = f"""{self.region} - {searches_results}."""
        return category_name


    async def product_urls(self, url, max_retries = 13):
        for retry in range(13):
            try:
                await asyncio.sleep(5)
                """
                Scrapes product data from the Amazon search results page for the given URL.

                Args:
                    -list: A list of dictionaries, with each dictionary containing product data for single product.

                Raises:
                    -Expecation: If there is an error while loading the content of the Amazon search results page.
                """
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


    async def scrape_product_info(self, url, max_retries = 13):
        """
        Scrapes product information from the Amazon product page.

        Args:
            - url (str): The URL of the Amazon product page.
            - max_retries (int): The maximum number of retry attempts in case of connection errors.

        Returns:
            - list: A list containing dictionaries with product information.

        Raises:
            - Exception: If valid data cannot be retrieved after the maximum number of retry attempts.
        """
        # List to store product information dictionaries:
        amazon_dicts = []
        for retry in range(max_retries):
            try:

                # Retrieve the page content using 'static_connection' method:
                content = await Response(url).content()
                soup = BeautifulSoup(content, 'lxml')

                # Extract product name:
                product = soup.select_one(self.scrape['name']).text.strip()
                print(product)

                # Raise an exception if the product name is 'N/A':
                if product == "N/A":
                    raise Exception("Product is 'N/A' retrying...")
                try:

                    # Try to extract the image link using the second first selector.
                    image_link = soup.select_one(self.scrape['image_link_i']).get('src')
                except Exception as e:
                    image_link = await self.catch.attributes(soup.select_one(self.scrape['image_link_ii']), 'src')
                try:
                    availabilities = soup.select_one(self.scrape['availability']).text.strip()
                except AttributeError:
                    availabilities = 'In stock'
                price = await self.catch.text(soup.select_one(self.scrape['price_us']))
                if 'Page' in price.split():
                    price = await self.catch.text(soup.select_one(self.scrape['price_us_i']))
                if price != "N/A":
                    price = float(re.sub(self.currency, '', price))
                try:
                    deal_price = await self.catch.text(soup.select(self.scrape['deal_price'])[0])
                    if 'Page' in deal_price.split():
                        deal_price = "N/A"
                except Exception as e:
                    deal_price = "N/A"
                if deal_price != "N/A":
                    deal_price = float(re.sub(self.currency, '', deal_price))
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
                    'Rating': ratings,
                    'Rating count': rating_count,
                    'Availability': availabilities,
                    'Hyperlink': url,
                    'Image': image_link,
                    'Images': [imgs.get('src') for imgs in soup.select(self.scrape['image_lists'])],
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
        """
        Crawls through multiple pages and retrieves a list of product URLs.

        Returns:
            - list: A list of product URLs.
        """
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


    async def csv_sheet(self, url):
        """
            Scrapes data from a given URL, saves it to a file, and returns the scraped data as a Pandas DataFrame.

            Args:
                - url (str): The URL to scrape data from.

            Returns:
                - pd.DataFrame: A Pandas DataFrame containing the scraped data.

            Raises:
                - HTTPError: If the HTTP request to the URL returns an error status code.
                - Exception: If there is an error while scraping the data.
        """
        frames = await self.scrape_and_save(url)
        return pd.DataFrame(frames)


    async def concurrent_scraping(self):
        """
        Performs concurrent scraping of product information from multiple Amazon search result pages.

        Returns:
            - list: A list of DataFrames, each containing scraped product information from a different page.
        """
        # Check if the provided Amazon link is valid:
        if await verify_amazon(self.base_url):
            return "I'm sorry, the link you provided is invalid. Could you please provide a valid Amazon link for the product category of your choice?"

        # Print welcome and category scraping message:
        print(f"----------------------- |Welcome to Amazon {self.region}. |---------------------------------")
        searches = await self.category_name()
        print(f"Scraping category || {searches}.")

        # Pull the total number of pages for the category:
        number_pages = await self.num_of_pages()
        print(f"Total pages || {number_pages}.")

        # Split the pagination and convert it to a list of URLs:
        product_urls = await self.crawl_url()
        print(f"The extraction process has begun and is currently in progress. The web scraper is scanning through all the links and collecting relevant information. Please be patient while the data is being gathered.")

        # Use coroutines to scrape and save data from each URL concurrently:
        coroutines = [self.scrape_and_save(url) for url in product_urls]
        dfs = await asyncio.gather(*coroutines)
        return dfs


    async def export_csv(self):
        """
        Scrapes data from a list of URLs, saves it to CSV files, and prints progress messages.

        Returns:
            - None
        """
        # Check if the provided Amazon link is valid:
        if await verify_amazon(self.base_url):
            return "I'm sorry, the link you provided is invalid. Could you please provide a valid Amazon link for the product category of your choice?"

        # Print welcome and export message:
        print(f"-----------------------| Welcome to Amazon {self.region}. |---------------------------------")
        print(f"Exporting to CSV")

        # Create a category name for the CSV file:
        categ =f"""{self.region} - { await self.category_name()}."""
        url_lists = await self.crawl_url()

        # Print extraction progress message:
        print(f"The extraction process has begun and is currently in progress. The web scraper is scanning through all the links and collecting relevant information. Please be patient while the data is being gathered.")

        # Use coroutines to scrape and save data from each URL:
        coroutines = [self.csv_sheet(url) for url in url_lists]
        dfs = await asyncio.gather(*coroutines)

        # Concatenate the DataFrames obtained from each URL:
        results = pd.concat(dfs)

        # Export the concatenated DataFrame to a CSV file:
        await export_sheet(results, categ)
