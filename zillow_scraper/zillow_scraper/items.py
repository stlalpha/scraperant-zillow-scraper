# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class HouseListingItem(scrapy.Item):
    # Listings
    zpid = scrapy.Field()
    price = scrapy.Field()
    address = scrapy.Field()
    details_url = scrapy.Field()
    # Details
    sqft = scrapy.Field()
    elementary_school_name = scrapy.Field()
    high_school_name = scrapy.Field()
    median_zestimate = scrapy.Field()
    agent_name = scrapy.Field()
    agent_phone = scrapy.Field()

