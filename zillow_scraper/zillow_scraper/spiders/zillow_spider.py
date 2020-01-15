import json
import urllib.parse
import scrapy
import logging
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError, TCPTimedOutError

from scrapy_selenium import SeleniumRequest
from ..items import HomeItem


class ZillowSpider(scrapy.Spider):
    name = 'zillow'
    BASE_URL = "https://www.zillow.com"

    def __init__(self, name=None, **kwargs):
        super().__init__(name=None, **kwargs)
        self.zillow_query_params = self.zillow_url.split('?')[1]

    def start_requests(self):
        yield scrapy.Request(
            self._get_proxied_ulr(self.zillow_url),
            callback=self.parse,
            errback=self.error_handler
        )

    def parse(self, response):
        # Save screenshoot
        # screenshoot_file = '%s.png' % response.request.url.split('/')[-3]
        # with open(screenshoot_file, 'wb') as image_file:
        #     image_file.write(response.meta['screenshot'])

        # Parse list of homes on this page
        for listing_item in response.css('article'):
            try:
                # First get basic home data shown on the list
                item = self._parse_listing_item(listing_item)

                # Then visit each home details page to get extra data
                logging.debug("Getting {}".format(item['home_details_link']))
                yield scrapy.Request(
                    url=self._get_proxied_ulr(item['home_details_link']),
                    callback=self._parse_item_details,
                    errback=self.error_handler,
                    cb_kwargs={'item': item}
                )
            except Exception as e:
                continue

        # Move to next page and repeat
        next_page = response.xpath('//a[@aria-label="NEXT Page"]/@href').get()
        if next_page is not None:
            next_url = urllib.parse.urljoin(ZillowSpider.BASE_URL, next_page)+"?{}".format(self.zillow_query_params)
            print("REQUESTING NEXT PAGE:\n {}".format(next_url))
            yield scrapy.Request(
                url=self._get_proxied_ulr(next_url),
                callback=self.parse,
                errback=self.error_handler
            )

    def _parse_listing_item(self, listing_item):
        item = HomeItem()
        try:
            item['address'] = listing_item.css('a.list-card-link::attr(aria-label)').get()
            item['price'] = listing_item.css('div.list-card-price::text').get()
            item['type'] = listing_item.css('div.list-card-type::text').get()
            card_details = listing_item.css('ul.list-card-details > li::text').extract()
            if len(card_details) == 3:
                item['number_of_bedrooms'] = card_details[0]
                item['number_of_bathrooms']  = card_details[1]
                item['sqft'] = card_details[2]
            elif len(card_details) == 1:
                item['sqft'] = card_details[0]
            item['home_details_link'] = listing_item.css('a.list-card-link::attr(href)').get()
        except Exception as e:
            pass
        return item

    def _parse_item_details(self, response, item):
        try:  # Parse each data field and add it to the item
            logging.debug("Parsing details from: {}".format(item['home_details_link']))
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

    def _parse_listing_provider_name(self, response, item):
        item['listing_provider_name'] = self._get_element(
            response,
            css_selectors=[
                'span.listing-field:nth-child(1)::text',
                '.cf-listing-agent-display-name::text'
            ]
        )
        return item

    def _parse_listing_provider_phone(self, response, item):
        item['listing_provider_phone'] = self._get_element(
            response,
            css_selectors=[
                'span.listing-field:nth-child(3)::text',
                'li.cf-listing-agent-info-text:nth-child(4)::text'
            ]
        )
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
            self.logger.error('Retrying HttpError on %s. ', response.url)
            yield scrapy.Request(
                response.url,
                callback=self.parse,
                errback=self.error_handler,
                dont_filter=True
            )

        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)
