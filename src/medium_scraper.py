import os
import sys
from datetime import datetime, timedelta
import time
import numpy as np
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
import re
import string
from tqdm import tqdm
from joblib import Parallel, delayed
import multiprocessing


def get_driver(executable_path, silent=True):
    options = webdriver.ChromeOptions()
    if silent: 
        options.add_argument('--headless')
    driver = webdriver.Chrome(executable_path=executable_path, options=options)
    return driver


def clean_url(user_url):
    return user_url.split('?source=')[0].rstrip("/")


def try_except(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            return None
    return wrapper


def date_description_to_date(string, ref_date=None):
    """
    Turn a string into a date. 

    Examples:
    - "2 days ago" -> date(2022, 12, 23)
    - "Dec 23" -> date(2022, 12, 23)
    - "Dec 23, 2022" -> date(2022, 12, 23)
    - "Pinned" -> None
    """

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    ref_date = ref_date or datetime.now().date()
    string_split = [s for s in re.split('[^a-zA-Z0-9]', string) if s]

    if len(string_split) == 3 and string_split[2] == "ago":
        days_ago = int(string_split[0]) if string_split[1] in ["day", "days"] else 0
        date = ref_date - timedelta(days=days_ago)
    elif string_split[0] in months:
        month = months.index(string_split[0]) + 1
        day = int(string_split[1])
        year = int(string_split[2]) if len(string_split) == 3 else ref_date.year
        date = datetime(year=year, month=month, day=day).date()            
    else:
        date = None
    
    return date

    
def user_url_to_user_name(user_url):
    if "/@" in user_url:
        user_name = user_url.split("/@")[-1]
    elif user_url[-11:] == ".medium.com":
        user_name = user_url.split("//")[-1].split(".medium.com")[0]
    return user_name


class MediumPublicationArchiveWebpage:
    def __init__(self, url, driver):
        self.url = url
        self.date = datetime.strptime(url.split("/archive/")[-1], "%Y/%m/%d")
        self.driver = driver
        driver.get(url)

    def get_articles(self):
        articles = self.driver.find_elements_by_xpath("/html/body/div[1]/div[2]/div/div[3]/div[1]/div[2]/div[.]")
        return articles
    
    def get_article_url(self, article):
        article_url = clean_url(article.find_element_by_xpath("./div/div/div[2]/a").get_attribute("href"))        
        return article_url
        
    def get_article_title(self, article):
        try:
            article_title = article.find_element_by_tag_name("h3").text
        except:
            article_title = article.find_element_by_tag_name("h2").text
        return article_title
    
    def get_user_name(self, article):
        user_url = clean_url(article.find_element_by_xpath("./div/div/div[1]/div/div/div[2]/a[1]").get_attribute("href"))
        user_name = user_url_to_user_name(user_url)
        return user_name
    
    def get_user_desc_name(self, article):
        user_desc_name = article.find_element_by_xpath("./div/div/div[1]/div/div/div[2]/a[1]").text
        return user_desc_name
    
    def get_reading_time(self, article):
        reading_time = int(article.find_element_by_class_name("readingTime").get_attribute("title").split(" ")[0])
        return reading_time
    
    def get_n_claps(self, article):
        n_claps = int(eval(article.find_element_by_xpath("./div/div/div[4]/div[1]/div/span").text.zfill(1).replace("K", "*1000")))
        return n_claps
        
    def get_articles_info(self):
        articles_info = []
        for article in self.get_articles():
            articles_info.append({
                "ref_date": datetime.now().date(),
                "article_date": self.date,
                "article_url": self.get_article_url(article),
                "article_title": self.get_article_title(article),
                "user_name": self.get_user_name(article),
                "user_desc_name": self.get_user_desc_name(article),
                "reading_time": self.get_reading_time(article),
                "n_claps": self.get_n_claps(article)
            })
        return articles_info
    

class MediumUserWebpage:
    
    def __init__(self, url, driver):
        self.url = url
        self.driver = driver
        driver.get(url)
        
    def get_articles(self, n_articles_max):
        articles = self.driver.find_elements_by_xpath("/html/body/div/div/div[3]/div[2]/div/main/div/div[2]/div/div/article[.]")
        n_articles_prev, n_articles_curr = 0, len(articles)
        while n_articles_curr > n_articles_prev and n_articles_curr < n_articles_max:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            articles = self.driver.find_elements_by_xpath("/html/body/div/div/div[3]/div[2]/div/main/div/div[2]/div/div/article[.]")
            n_articles_prev, n_articles_curr = n_articles_curr, len(articles)
        return articles
    
    def get_user_name(self):
        user_name = user_url_to_user_name(self.url)
        return user_name
    
    def get_user_desc_name(self):
        user_desc_name = self.driver.find_element_by_xpath("/html/body/div/div/div[3]/div[2]/div/main/div[2]/div[1]/div/div/div/div/div[1]/div[2]/div[1]/div/a/span").text
        return user_desc_name
    
    def get_followers_approx_count(self):
        followers_approx_count_text = self.driver.find_element_by_xpath("/html/body/div/div/div[3]/div[2]/div/div/div/div/div/div[1]/div[1]/div[2]/span/a").text
        followers_approx_count = int(eval(followers_approx_count_text.split(" Followers")[0].replace("K", "*1000")))
        return followers_approx_count 
    
    def get_article_url(self, article):
        article_url = clean_url(article.find_element_by_xpath("./div/div/div/div/div/div[2]/div/div[1]/div/div/div/div[1]/div[1]/div[1]/a").get_attribute("href"))
        return article_url
    
    def get_article_title(self, article):
        try:
            article_title = article.find_element_by_tag_name("h3").text
        except:
            article_title = article.find_element_by_tag_name("h2").text
        return article_title
    
    def get_article_date(self, article):
        article_date_text = article.find_element_by_xpath("./div/div/div/div/div/div[1]/div[2]/div[2]/span/div/a/p").text
        article_date = date_description_to_date(string=article_date_text)
        return article_date
        
    @try_except
    def get_publication_name(self, article):
        published_in = article.find_element_by_xpath("./div/div/div/div/div/div[1]/div[2]/div[1]/div/span/a/p").text
        publication_name = published_in.lstrip("Published in")
        return publication_name
    
    def get_user_info(self):
        user_info = {
            "ref_date": datetime.now().date(),
            "user_name": self.get_user_name(),
            "user_desc_name": self.get_user_desc_name(),
            "followers_approx_count": self.get_followers_approx_count()
        }
        return user_info   
    
    def get_articles_info(self, n_articles_max=300):
        articles_info = []
        for article in self.get_articles(n_articles_max=n_articles_max):
            articles_info.append({
                "ref_date": datetime.now().date(),
                "user_name": self.get_user_name(),
                "article_url": self.get_article_url(article),
                "article_title": self.get_article_title(article),
                "article_date": self.get_article_date(article),
                "publication_name": self.get_publication_name(article)
            })
        return articles_info