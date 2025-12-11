import requests
from bs4 import BeautifulSoup
import re

WIG20 = 20

url = "https://www.bankier.pl/inwestowanie/profile/quote.html?symbol=WIG20"

response = requests.get(url)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
rows = soup.find_all("tr")

wig_number = 0
for row in rows:
    text = str(row)
    if str(row).startswith("<tr "):
        symbol = re.search(r'\?symbol=(\w+)', text).group(1)
        raw_value = re.search(r'>([\d,]+)\d<', text).group(1)
        value = raw_value.replace(',', '.') 

        print(symbol)
        print(value)
        wig_number+=1
    if wig_number == WIG20:
        break