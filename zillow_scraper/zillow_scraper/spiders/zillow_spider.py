import json
import urllib.parse
import scrapy
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError, TCPTimedOutError

from scrapy_selenium import SeleniumRequest
from ..items import HomeItem


class ZillowSpider(scrapy.Spider):
    name = 'zillow'
    BASE_URL = "https://www.zillow.com"

    def start_requests(self):
        yield scrapy.Request(self._get_proxied_ulr(self.zillow_url), callback=self.parse, errback=self.error_handler)

    def parse(self, response):
        # Parse list of homes on this page
        for listing_item in response.css('article'):
            try:
                # First get basic home data shown on the list
                item = self._parse_listing_item(listing_item)

                # Then visit each home details page to get extra data
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
        print(next_page)
        if next_page is not None:
            next_url = urllib.parse.urljoin(ZillowSpider.BASE_URL, next_page)
            yield scrapy.Request(url=self._get_proxied_ulr(next_url), callback=self.parse, errback=self.error_handler)

    def _parse_listing_item(self, listing_item):
        item = HomeItem()
        item['address'] = listing_item.css('a.list-card-link::attr(aria-label)').get()
        item['price'] = listing_item.css('div.list-card-price::text').get()
        item['type'] = listing_item.css('div.list-card-type::text').get()
        card_details = listing_item.css('ul.list-card-details > li::text').extract()
        item['number_of_bedrooms'] = card_details[0]
        item['number_of_bathrooms']  = card_details[1]
        item['sqft'] = card_details[2]
        item['home_details_link'] = listing_item.css('a.list-card-link::attr(href)').get()
        return item

    def _parse_item_details(self, response, item):
        item['elementary_school_name'] = response.css('div.ds-school-row:nth-child(1) > div:nth-child(2) > a:nth-child(1)::text').get()
        item['high_school_name'] = response.css('div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::text').get()
        item['median_zestimate'] = response.css('div.ds-standard-label:nth-child(2)::text').get()
        item['agent_name'] = response.css('span.listing-field:nth-child(1)::text').get()
        if item['agent_name'] is None:
            item['agent_name'] = response.css('.cf-listing-agent-display-name::text').get()
        item['agent_phone'] = response.css('span.listing-field:nth-child(3)::text').get()
        if item['agent_phone'] is None:
            item['agent_phone'] = response.css('li.cf-listing-agent-info-text:nth-child(4)::text').get()
        # Save screenshoot
        # screenshoot_file = '%s.png' % response.request.url.split('/')[-3]
        # with open(screenshoot_file, 'wb') as image_file:
        #     image_file.write(response.meta['screenshot'])
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

