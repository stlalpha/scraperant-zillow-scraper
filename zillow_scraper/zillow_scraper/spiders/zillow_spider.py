import json
import random
import re
import os
try:
    from urllib.parse import urlparse
except ImportError:
     from urlparse import urlparse
import logging
from scrapy_proxycrawl import ProxyCrawlRequest
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError, TCPTimedOutError
from scrapy.spiders import Spider
from ..items import HomeItem


class ZillowSpider(Spider):
    name = 'zillow_spider'
    BASE_URL = "https://www.zillow.com"
    custom_settings = {
        'FEED_FORMAT': 'xlsx',
        'FEED_URI': 's3://scraperant-prod/scraping/feeds/%(time)s_%(name)s_results.xlsx',  # Output file
        'FEED_EXPORT_FIELDS': [  # specifies exported fields and order
            "address",
            "price",
            "type",
            "number_of_bedrooms",
            "number_of_bathrooms",
            "sqft",
            "home_details_link",
            "listing_provided_by",
            "listing_provider_name",
            "listing_provider_phone",
            "property_taxes_last_year",
            "estimated_monthly_cost",
            "property_taxes_monthly",
            "hoa_fees",
            "zestimate_sell_price",
            "zestimate_rent_price",
            "elementary_school_name",
            "elementary_school_rating",
            "elementary_school_link",
            "middle_school_name",
            "middle_school_rating",
            "middle_school_link",
            "high_school_name",
            "high_school_rating",
            "high_school_link",
        ],
    }

    def __init__(self, name=None, **kwargs):
        super().__init__(name=None, **kwargs)
        self.start_urls = [self.zillow_url]
        self.zillow_query_params = self.zillow_url.split('?')[1]

    def start_requests(self):
        for url in self.start_urls:
            yield ProxyCrawlRequest(
                url,
                callback=self.parse,
                errback=self.error_handler,
                user_agent=self._get_random_user_agent(),
                #device='desktop',
                country='US',
                page_wait=8000,
                ajax_wait=True,
                screenshot=True
            )

    def _get_pages(self, response):
        # Look for pagination links
        pages = response.xpath('//a[contains(@aria-label, "Page")]/text()').extract()
        if len(pages) <= 1:  # No pagination, it's a single page
            return [response.url, ]

        # Multiple pages with format 1,2,3,4,5...20 next
        last_page_num = int(pages[-2])
        first_page = response.xpath('//a[contains(@aria-label, "Page")]/@href').get()  # page 1 link has special format

        # Second to last page links contain work "Page" in an attribute
        second_page_link = response.xpath('//a[contains(@aria-label, "Page")]/@href').extract()[1] # Minimum 2 pages
        links = [first_page] + [second_page_link.replace('2_p', '{}_p'.format(n)) for n in range(2, last_page_num + 1)]
        full_links = [response.urljoin(lnk) for lnk in links]
        return full_links

    def parse(self, response):
        # Find pagination links
        pagination_links = self._get_pages(response)
        if len(pagination_links) == 0:
            print("NO PAGES FOUND..RETRY")
            yield response.request.replace(dont_filter=True) # Trigger a new request
        else:
            if self.sample_mode:
                logging.debug("SAMPLE MODE ON, PARSING ONLY FIRST PAGE..")
                del pagination_links[1:]  # truncate to first link only
            print("PARSING {} PAGES..".format(len(pagination_links)))
            for i, link in enumerate(pagination_links):
                # Is a listing page different from page 1 like /houses/2_p/?
                pattern = r'.*/\d+_p/$'
                if re.match(pattern, link): # Add query params in url, and update page number if required
                    page_num = link.split('/')[-2].split('_')[0]
                    new_params = self.zillow_query_params.replace("%22pagination%22:{}",
                                                                  '%%22pagination%%22:{"currentPage":%s}' % page_num)
                    link = self._url_with_query_params(link, new_params)
                else:
                    link = self._url_with_query_params(link)
                # Request each listings page to be parsed
                print("REQUESTING PAGE {}..".format(i+1))
                yield ProxyCrawlRequest(
                    link,
                    callback=self.parse_listing_page,
                    errback=self.error_handler,
                    dont_filter=True,  # Important, or the other pages are filtered
                    user_agent=self._get_random_user_agent(),
                    device='desktop',
                    country='US',
                    page_wait=8000,
                    ajax_wait=True,
                    screenshot=True
                )

    def parse_listing_page(self, response):
        # Get listings on this page
        listings = response.css('ul.photo-cards > li > article.list-card')
        print("Found {} listing in page: {}".format(len(listings), response.url))
        print("Screen capture:\n {}".format(response.headers.get('Screenshot_Url', "Header not found")))

        if self.sample_mode:
            logging.debug("SAMPLE MODE ON, PARSING ONLY 3 LISTING ITEMS..")
            listings = listings[0:3]  # truncate to 3 items

        # Parse each listing details
        for listing_item in listings:
            try:
                # First get basic home data shown on the list
                item = self.parse_listing_item(listing_item)

                # Then visit each home details page to get extra data
                logging.debug("Getting {}".format(item['home_details_link']))
                yield ProxyCrawlRequest(
                    item['home_details_link'],
                    callback=self.parse_home_details,
                    cb_kwargs={'item': item},
                    errback=self.error_handler,
                    user_agent=self._get_random_user_agent(),
                    device='desktop',
                    country='US',
                    page_wait=8000,
                    ajax_wait=True,
                    screenshot=True
                )
            except Exception as e:
                continue

    def _parse_listing_price(self, listing_item, item):
        item['price'] = listing_item.css('div.list-card-price::text').get().strip()
        if not item['price']:  # Maybe there is an estimated price
            price_candidates = listing_item.css('div.list-card-price::text').extract()
            for el in price_candidates:
                if el and '$' in el:
                    item['price'] = el
                    break
        return item

    def parse_listing_item(self, listing_item):
        item = HomeItem()
        try:
            # Get address
            item['address'] = listing_item.css('address.list-card-addr::text').get()
            print("House Found:{}".format(item['address']))

            # Try to get price
            self._parse_listing_price(listing_item, item)

            # Get other basic info
            item['type'] = listing_item.css('div.list-card-type::text').get()
            card_details = listing_item.css('ul.list-card-details > li::text').extract()
            if len(card_details) == 3:
                item['number_of_bedrooms'] = card_details[0]
                item['number_of_bathrooms'] = card_details[1]
                item['sqft'] = card_details[2]
            elif len(card_details) == 1:
                item['sqft'] = card_details[0]
            item['home_details_link'] = self._url_with_query_params(  # Keep search params in url
                listing_item.css('a.list-card-link::attr(href)').get()
            )
        except Exception as e:
            pass
        return item

    def parse_home_details(self, response, item):
        try:  # Parse each data field and add it to the item
            logging.debug("Parsing details from: {}".format(item['home_details_link']))
            print("Screen capture:\n {}".format(response.headers.get('Screenshot_Url', "Header not found")))
            # Check for known error loading the page
            ERROR_TEXT = "There was an error retrieving some of the data for this home"
            if ERROR_TEXT in response.text:
                logging.warning("ERROR LOADING PAGE:\n {}\n RETRYING..".format(item['home_details_link']))
                return response.request.replace(dont_filter=True)

            # Extract data
            self._parse_listing_provided_by(response, item)
            self._parse_listing_provider_name(response, item)
            self._parse_listing_provider_phone(response, item)
            self._parse_property_taxes_last_year(response, item)
            self._parse_estimated_monthly_cost(response, item)
            self._parse_property_taxes_monthly(response, item)
            self._parse_hoa_fees(response, item)
            self._parse_zestimate_sell_price(response, item)
            self._parse_elementary_school_name(response, item)
            self._parse_zestimate_rent_price(response, item)
            self._parse_elementary_school_rating(response, item)
            self._parse_elementary_school_link(response, item)
            self._parse_middle_school_name(response, item)
            self._parse_middle_school_rating(response, item)
            self._parse_middle_school_link(response, item)
            self._parse_high_school_name(response, item)
            self._parse_high_school_rating(response, item)
            self._parse_high_school_link(response, item)
        except Exception as e:
            pass
        return item

    def _get_element(self, response, css_selectors=[], xpath_selectors=[], raise_exception=False):
        try:
            # Try css_selectors until the first match
            elem = None
            # CSS selectors first
            for select in css_selectors:
                elem = response.css(select).get()
                if elem is not None:
                    return elem
            # XPath selectors if no CSS selectors
            for select in xpath_selectors:
                elem = response.xpath(select).get()
                if elem is not None:
                    return elem
        except Exception as e:
            if raise_exception:
                raise e
            return None
        else:
            if elem is '':
                return None
            return elem

    def _parse_listing_provided_by(self, response, item):
        listed_by_str = self._get_element(
            response,
            css_selectors=[
                'div.home-details-listing-provided-by > span::text',
            ]
        )
        try:  # Owner or Agent?
            lister = listed_by_str.split('Listing provided by')[1].lower().strip()
        except Exception as e:
            lister = 'agent'

        if not lister:
            lister = 'agent'

        item['listing_provided_by'] = lister
        return item

    def _parse_listing_provider_name(self, response, item):
        # Apply different selectors depending if is owner or agent
        if item['listing_provided_by'] == 'owner':
            item['listing_provider_name'] = self._get_element(
                response,
                css_selectors=[
                    'span.listing-field:nth-child(1)::text'
                ]
            )
        else:  # agent is the default
            item['listing_provider_name'] = self._get_element(
                response,
                css_selectors=[
                    'span.listing-field:nth-child(1)::text',
                    '.cf-listing-agent-display-name::text',
                    '.ds-listing-agent-display-name::text',
                    'span.cf-rpt-display-name-text.name::text',
                    'div.cf-cnt-rpt-container:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > '
                    'span:nth-child(1) > a:nth-child(1) > span:nth-child(1)::text',
                ]
            )

        if item['listing_provider_name'] and \
                (item['listing_provider_name'] == 'Property Owner' or item['listing_provider_name'][0] == '('):
            item['listing_provider_name'] = 'Property Owner - unknown name'

        if item['listing_provider_name'] is None:
            logging.warning("LISTING PROVIDER NAME NOT FOUND:\n {}".format(item['home_details_link']))
        return item

    def _parse_listing_provider_phone(self, response, item):
        # Apply different selectors depending if is owner or agent
        if item['listing_provided_by'] == 'owner':
            item['listing_provider_phone'] = self._get_element(
                response,
                css_selectors=[
                    'div.zsg-content-item > div > span.listing-field:nth-child(4)::text',  # Multiple lines
                    'div.zsg-content-item > div > span.listing-field:nth-child(3)::text',
                    'div.zsg-content-item > div > span.listing-field:nth-child(2)::text',
                    'div.zsg-content-item > div > span.listing-field::text'  # some have phone only
                ]
            )
        else: # agent is the default
            item['listing_provider_phone'] = self._get_element(
                response,
                css_selectors=[
                    'span.listing-field:nth-child(3)::text',
                    'li.ds-listing-agent-info-text::text',
                    'li.cf-listing-agent-info-text:nth-child(4)::text',
                    'div.cf-cnt-rpt-container:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > '
                    'span:nth-child(4)::text',
                    'span.cf-phone:nth-child(3)::text',
                    'div.zsg-content-item > div > span.listing-field::text',
                ]
            )
        # Todo check phone format with regex
        if item['listing_provider_phone'] and item['listing_provider_phone'][0] != '(':
            # Try other selectors
            item['listing_provider_phone'] = self._get_element(
                response,
                css_selectors=[
                    'div.zsg-content-item > div > span.listing-field:nth-child(4)::text',
                    'div.zsg-content-item > div > span.listing-field:nth-child(3)::text',
                    'span.cf-phone:nth-child(3)::text',
                    'div.zsg-content-item > div > span.listing-field:nth-child(2)::text',
                    '.cf-listing-agent-info-text::text',
                ],
                xpath_selectors=[
                    '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[20]/div/div[1]/div[1]/div[2]/div/span[4]/text()',
                    '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[17]/div/div[1]/article/div[1]/form/section/div[1]/div/div[4]/div[1]/div/div[1]/div[2]/span[3]/text()'
                ]
            )
            if item['listing_provider_phone'] and item['listing_provider_phone'][0] != '(':
                item['listing_provider_phone'] = None
        if item['listing_provider_phone'] is None:
            logging.warning("LISTING PROVIDER PHONE NOT FOUND:\n {}".format(item['home_details_link']))
        return item

    def _parse_property_taxes_last_year(self, response, item):
        item['property_taxes_last_year'] = self._get_element(
            response,
            css_selectors=[
                'tr.ds-tax-table-row:nth-child(1) > td:nth-child(2)::text',
            ]
        )
        return item

    def _parse_estimated_monthly_cost(self, response, item):
        item['estimated_monthly_cost'] = self._get_element(
            response,
            css_selectors=[
                '.sc-4m29jb-0::text',
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[9]/div/div[2]/h4/text()',
            ]
        )
        return item

    def _parse_property_taxes_monthly(self, response, item):
        item['property_taxes_monthly'] = self._get_element(
            response,
            css_selectors=[
                'div.sc-1b8bq6y-4:nth-child(3) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > span:nth-child(2)::text',
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[9]/div/div[3]/div[3]/div/div/div/div/span[2]/text()',
            ]
        )
        return item

    def _parse_hoa_fees(self, response, item):
        item['hoa_fees'] = self._get_element(
            response,
            css_selectors=[
                'div.sc-1b8bq6y-4:nth-child(5) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > span:nth-child(2)::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[9]/div/div[3]/div[5]/div/div/div/div/span[2]/text()'
            ]
        )
        return item

    def _parse_zestimate_sell_price(self, response, item):
        item['zestimate_sell_price'] = self._get_element(
            response,
            css_selectors=[
                '.eSvINd > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > p:nth-child(1)::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[7]/div/div/div[1]/div/div[1]/div/div/p/text()'
            ]
        )
        return item

    def _parse_zestimate_rent_price(self, response, item):
        item['zestimate_rent_price'] = self._get_element(
            response,
            css_selectors=[
                '#ds-rental-home-values > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > p:nth-child(1)::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div/div[1]/div/div/div/p/text()'
            ]
        )
        return item

    def _parse_elementary_school_name(self, response, item):
        item['elementary_school_name'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(1) > div:nth-child(2) > a:nth-child(1)::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[1]/div[2]/a/text()'
            ]
        )
        return item

    def _parse_elementary_school_rating(self, response, item):
        item['elementary_school_rating'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(1) > div:nth-child(1) > div:nth-child(1) > span.ds-hero-headline.ds-schools-display-rating::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[1]/div[1]/div/span[1]/text()'
            ]
        )
        return item

    def _parse_elementary_school_link(self, response, item):
        item['elementary_school_link'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(1) > div:nth-child(2) > a:nth-child(1)::attr(href)'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[1]/div[2]/a/@href'
            ]
        )
        return item

    def _parse_middle_school_name(self, response, item):
        item['middle_school_name'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[2]/div[2]/a/text()'
            ]
        )
        return item

    def _parse_middle_school_rating(self, response, item):
        item['middle_school_rating'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(2) > div:nth-child(1) > div:nth-child(1) > span.ds-hero-headline.ds-schools-display-rating::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[2]/div[1]/div/span[1]/text()'
            ]
        )
        return item

    def _parse_middle_school_link(self, response, item):
        item['middle_school_link'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::attr(href)'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[2]/div[1]/div/span[1]/a/@href'
            ]
        )
        return item

    def _parse_high_school_name(self, response, item):
        # item['high_school_name'] = response.css('div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::text').get()
        item['high_school_name'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[3]/div[2]/a/text()'
            ]
        )
        return item

    def _parse_high_school_rating(self, response, item):
        item['high_school_rating'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(3) > div:nth-child(1) > div:nth-child(1) > span.ds-hero-headline.ds-schools-display-rating::text'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[3]/div[1]/div/span[1]/text()'
            ]
        )

    def _parse_high_school_link(self, response, item):
        item['high_school_link'] = self._get_element(
            response,
            css_selectors=[
                'div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::attr(href)'
            ],
            xpath_selectors=[
                '//html/body/div[1]/div[7]/div[1]/div[1]/div/div/div[3]/div/div/div/div[3]/div[4]/div[5]/ul/li[10]/div/div[1]/div[2]/div[3]/div[2]/a/@href'
            ]
        )
        return item

    def _get_proxied_ulr(self, url):
        encoded_url = urllib.parse.quote_plus(url, safe='')
        # Proxy Crawl
        proxied_url = 'https://api.proxycrawl.com/?token=nzaW1bbXAns4MSpIc8LYYw&country=US&device=desktop&page_wait=5000&ajax_wait=true&url=%s' % encoded_url
        return proxied_url

    def error_handler(self, failure):
        # log all failures
        self.logger.error(repr(failure))

        # in case you want to do something special for some errors,
        # you may need the failure's type:

        if failure.check(HttpError):
            # these exceptions come from HttpError spider middleware
            # you can get the non-200 response
            response = failure.value.response
            self.logger.error('RETRYING HttpError on %s. ', response.url)
            yield response.request.replace(dont_filter=True)

        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)

    def _url_with_query_params(self, url, new_params=None):
        base_url = url.split('?')[0]  # Remove current params if present
        params = self.zillow_query_params
        if new_params:
            params = new_params
        new_url = base_url + '?{}'.format(params)  # Keep query params
        return new_url

    def _get_random_user_agent(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/72.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) Gecko/20100101 Firefox/72.0',
            'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/72.0',
        ]
        return random.choice(user_agents)


