import json
import urllib.parse
import scrapy
from scrapy_selenium import SeleniumRequest
from ..items import HouseListingItem


class ZillowSpider(scrapy.Spider):
    name = 'zillow'
    # allowed_domains = [
    #     "www.zillow.com",
    #     "zillow.com",
    #     "www.zillowstatic.com",
    #     "s.zillowstatic.com",
    # ]

    def start_requests(self):
        yield scrapy.Request(self.zillow_url)
        #Selenium request
        #yield SeleniumRequest(url=self.zillow_url, callback=self.parse)

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
                # Scrapy standard request + proxycloud
                yield response.follow(
                    url=self._get_proxied_ulr(item['details_url']),
                    #url=item['details_url'],
                    callback=self.parse_item_details,
                    cb_kwargs={'item': item}
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
        # Senscrape
        #proxied_url = 'https://app.zenscrape.com/api/v1/get?url=%s&render=true&premium=&location=na&apikey=7aa28d10-3187-11ea-8e5e-49caa5eb4e83' % encoded_url
        # Proxy Crawl
        proxied_url = 'https://api.proxycrawl.com/?token=nzaW1bbXAns4MSpIc8LYYw&country=US&device=desktop&page_wait=5000&ajax_wait=true&url=%s' % encoded_url
        return proxied_url
