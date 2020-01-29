
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

try:
    # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError:
    # for pip <= 9.0.3
    from pip.req import parse_requirements


def load_requirements(fname):
    reqs = parse_requirements(fname, session="test")
    return [str(ir.req) for ir in reqs]


setup(
    name='zillow_scraper',
    version='1.0',
    python_requires='>=3.6.0',
    install_requires=load_requirements("requirements.txt"),
    packages=find_packages(),
    entry_points={'scrapy': ['settings = zillow_scraper.settings']},
)
