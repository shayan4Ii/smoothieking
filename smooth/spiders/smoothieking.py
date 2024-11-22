import scrapy
from scrapy import Request
from scrapy.http import Response
import json
import html
from json.decoder import JSONDecoder
from datetime import datetime
import re

class SmoothiekingSpider(scrapy.Spider):
    name = "smoothieking"
    allowed_domains = ["locations.smoothieking.com"]
    start_urls = ["https://locations.smoothieking.com/ll/us/"]

    def parse(self, response: Response):
        states = response.xpath('//a[contains(@class, "itemList")]/@href').getall()
        yield from response.follow_all(states, self.parse_states)
        
    def parse_states(self, response: Response):
        cities = response.xpath('//a[contains(@class, "itemList")]/@href').getall()
        yield from response.follow_all(cities, self.parse_city)
    
    def parse_city(self, response: Response):
        stores = response.xpath("//a[@class='location-city']/@onclick").getall()
        for store in stores:
            url = store.split("window.open('")[1].split("',")[0]
            yield response.follow(url, self.parse_stores)
            
    def get_uid(self, response: Response):
        script_content = response.xpath('//script[contains(text(), "W2GI.collection.poi")]/text()').get()
        if script_content:
            uid_values = re.findall(r'uid\s*:\s*(\d+)', script_content)
        else:
            self.logger.info("no uid for this store!")
            return None
        return uid_values[0]
    
    def parse_hours(self, response: Response):
        hours_dict = {}
        script_content = re.search("'(\[\[.+?\]\])'", response.body.decode("utf-8"), re.S)
        if script_content:
            hours_content = re.findall(r'\[(\d{4}),(\d{4})\]', script_content.group(1))
            days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
            for idx, hours in enumerate(hours_content):
                open_hour, close_hour = hours
                try:
                    t_open = datetime.strptime(str(open_hour).zfill(4), "%H%M").strftime("%I:%M %p").lower()
                    t_close = datetime.strptime(str(close_hour).zfill(4), "%H%M").strftime("%I:%M %p").lower()
                    hours_dict[days[idx]] = {
                        'open_time' : t_open,
                        'close_time' : t_close
                    }
                except ValueError as e:
                    self.logger.info(f"error in getting hour of {days[idx]} : {e}")
        else:
            self.info.logger("No hour data for this Store!")
        return hours_dict
    def parse_raw(self, response: Response):
        raw_content = response.xpath('//script[contains(@type, "application/ld+json")][2]/text()').get().strip()
        if raw_content:
            raw_content = raw_content.replace('\n', '').replace('\r', '').replace('\t', '').replace('\\', '')
            try:
                json_data = json.loads(raw_content)
            except json.JSONDecodeError:
                self.logger.info("no raw for this store")
                return None
        else:
            self.logger.info("No raw Data for this store!")
        return json_data
        
        
                                    
        
    def parse_stores(self, response: Response):
        name = response.xpath('//div[contains(@class, "location-title")]/h3/text()').get()
        phone_number = response.xpath('//meta[@property="restaurant:contact_info:phone_number"]/@content').get()
        street = response.xpath('//meta[@property="restaurant:contact_info:street_address"]/@content').get()
        locality = response.xpath('//meta[@property="restaurant:contact_info:locality"]/@content').get()
        region = response.xpath('//meta[@property="restaurant:contact_info:region"]/@content').get()
        postal_code = response.xpath('//meta[@property="restaurant:contact_info:postal_code"]/@content').get()
        latitude = response.xpath('//meta[@property="place:location:latitude"]/@content').get()
        longitude = response.xpath('//meta[@property="place:location:longitude"]/@content').get()
        uid_values = self.get_uid(response)
        hours_dict = self.parse_hours(response)
        raw_dict = self.parse_raw(response)
        loc_dict = {
            "type" : "Point",
            "coordinates" : [latitude,longitude]
        }
        yield{
            'number' : uid_values,
            'name' : name,
            'phone_number' : phone_number,
            'address' : f"{street}, {locality}, {region}, {postal_code}",
            'location' : loc_dict,
            'url' : response.url,
            'hours' : hours_dict,
            'raw' : raw_dict          
        }
        
        
        