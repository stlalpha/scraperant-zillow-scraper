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
    listing_provided_by = scrapy.Field()
    listing_provider_name = scrapy.Field()
    listing_provider_phone = scrapy.Field()
    property_taxes_last_year = scrapy.Field()
    estimated_monthly_cost = scrapy.Field()
    property_taxes_monthly = scrapy.Field()
    hoa_fees = scrapy.Field()
    zestimate_sell_price = scrapy.Field()
    zestimate_rent_price = scrapy.Field()
    elementary_school_name = scrapy.Field()
    elementary_school_rating = scrapy.Field()
    elementary_school_link = scrapy.Field()
    middle_school_name = scrapy.Field()
    middle_school_rating = scrapy.Field()
    middle_school_link = scrapy.Field()
    high_school_name = scrapy.Field()
    high_school_rating = scrapy.Field()
    high_school_link = scrapy.Field()

