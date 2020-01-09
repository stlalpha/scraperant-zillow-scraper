import json
import urllib.parse
import scrapy
from scrapy_selenium import SeleniumRequest
from ..items import HouseListingItem


class ZillowSpider(scrapy.Spider):
    name = 'zillow'

    def start_requests(self):
        yield SeleniumRequest(url=self.zillow_url, callback=self.parse)

    def parse(self, response):
        # Parse list of homes on this page
        for listing in response.css('article'):
            # Parse home data shown on the list
            try:
                price = listing.css('div.list-card-price::text').get()
                address = listing.css('a.list-card-link::attr(aria-label)').get()
                details_url = listing.css('a.list-card-link::attr(href)').get()
                zpid = int(details_url.split('/')[-2].split('_')[0])  # Extract zpid number from url
                item = HouseListingItem(
                    zpid=zpid,
                    price=price,
                    address=address,
                    details_url=details_url
                )
                # Get more data from each details page
                yield SeleniumRequest(
                    url=response.urljoin(item['details_url']),
                    callback=self.parse_item_details,
                    cb_kwargs={'item': item},
                    #screenshot=True,  # Capture screen with selenium
                    wait_time=3  # Wait for context to be loaded using javascript
                )
            except Exception as e:
                continue


        # Move to next page and repeat
        next_page = response.xpath('//a[@aria-label="NEXT Page"]/@href').get()
        print(next_page)
        if next_page is not None:
            yield response.follow(url=next_page, callback=self.parse)

    def parse_item_details(self, response, item):
        item['sqft'] = response.css('.ds-chip > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > header:nth-child(2) > h3:nth-child(1) > span:nth-child(5) > span:nth-child(1)::text').get()
        item['elementary_school_name'] = response.css('div.ds-school-row:nth-child(1) > div:nth-child(2) > a:nth-child(1)::text').get()
        item['high_school_name'] = response.css('div.ds-school-row:nth-child(2) > div:nth-child(2) > a:nth-child(1)::text').get()
        item['median_zestimate'] = response.css('div.ds-standard-label:nth-child(2)::text').get()
        item['agent_name'] = response.css('span.listing-field:nth-child(1)::text').get()
        item['agent_phone'] = response.css('span.listing-field:nth-child(4)::text').get()
        # Save screenshoot
        # screenshoot_file = '%s.png' % response.request.url.split('/')[-3]
        # with open(screenshoot_file, 'wb') as image_file:
        #     image_file.write(response.meta['screenshot'])
        return item

