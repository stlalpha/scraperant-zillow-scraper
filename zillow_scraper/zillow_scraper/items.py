# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class HomeItem(scrapy.Item):
    # Listing
    address = scrapy.Field()
    price = scrapy.Field()
    type = scrapy.Field()
    number_of_bedrooms = scrapy.Field()
    number_of_bathrooms = scrapy.Field()
    sqft = scrapy.Field()
    home_details_link = scrapy.Field()

    # Home Details
    elementary_school_name = scrapy.Field()
    high_school_name = scrapy.Field()
    median_zestimate = scrapy.Field()
    agent_name = scrapy.Field()
    agent_phone = scrapy.Field()

