import requests
from bs4 import BeautifulSoup
import re
import db_updater

WIG20 = 20

url = "https://www.bankier.pl/inwestowanie/profile/quote.html?symbol=WIG20"

response = requests.get(url)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
rows = soup.find_all("tr")

symbols = []
values = []

wig_number = 0
for row in rows:
    text = str(row)
    if text.startswith("<tr "):
        symbol = re.search(r'\?symbol=(\w+)', text).group(1)
        raw_value = re.search(r'>((?<=">)[\d]*[ ]?[\d]{1,3}[,][\d]+(?=<))<', text).group(1)
        raw_number = re.search(r'>((?<=">)([\d]{1,3} )+[\d]{1,3}(?=<))<', text).group(1)
        number = raw_number.replace('\xa0', '')
        value = raw_value.replace(',', '.') 
        value = value.replace('\xa0', '') 
        symbols.append(symbol)
        values.append(float(value))
        total_value = int(float(value)*int(number))
        print(symbol+" "+value+" "+number+" "+str(total_value))
        wig_number+=1
    if wig_number == WIG20:
        break

db_updater.insert(values, symbols)