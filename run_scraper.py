import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# This scrapper takes arguments. At least zillow url is required
p = argparse.ArgumentParser()
p.add_argument('--zillow-url', dest='zillow_url', required=True)
p.add_argument('--output-file', dest='output_file', required=True)
p.add_argument('--sample-mode', dest='sample_mode', action='store_true', default=False)
p.add_argument('--post-back-url', dest='post_back_url', required=False)

if __name__ == '__main__':
    args = p.parse_args()
    process = CrawlerProcess(get_project_settings())
    process.crawl('zillow_spider', **vars(args))
    process.start()
