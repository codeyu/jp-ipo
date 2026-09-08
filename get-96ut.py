import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime

def get_ipo_data(year):
    url = f"https://96ut.com/ipo/list.php?year={year}"
    
    try:
        response = requests.get(url)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the table
        table = soup.find('table', id='summarylist')
        if not table:
            return []
        
        # Get headers
        headers = []
        for th in table.find_all('th'):
            text = th.get_text(strip=True).split('\n')[0]
            if text == 'code':
                headers.append('code')
            elif text == '銘柄名':
                headers.append('company_name')
            elif text == '主幹':
                headers.append('lead_underwriter')
            elif text == '上場':
                headers.append('listing_date') 
            elif text == '市場':
                headers.append('market')
            elif text == '想定':
                headers.append('expected_price')
            elif text == '公募':
                headers.append('offering_price')
            elif text == '吸収金額':
                headers.append('absorption_amount')
            elif text == '評価':
                headers.append('evaluation')
            elif text == '初値':
                headers.append('initial_price')
            elif text == '(騰落率)':
                headers.append('price_change_rate')
            elif text == '現在値':
                headers.append('current_price')
                
        # Get data rows
        data = []
        for tr in table.find('tbody').find_all('tr'):
            row = {}
            cells = tr.find_all('td')
            
            for i, cell in enumerate(cells):
                if i >= len(headers):
                    break
                    
                header = headers[i]
                value = cell.get_text(strip=True)
                
                # Clean up the data
                if header == 'code':
                    row[header] = value
                elif header == 'company_name':
                    row[header] = value
                elif header == 'lead_underwriter':
                    row[header] = value
                elif header == 'listing_date':
                    row[header] = f"{year}/{value}"
                elif header == 'market':
                    row[header] = value
                elif header == 'expected_price':
                    row[header] = value.replace(',', '').split('(')[0]
                elif header == 'offering_price':
                    row[header] = value.replace(',', '')
                elif header == 'absorption_amount':
                    row[header] = value
                elif header == 'evaluation':
                    row[header] = value
                elif header == 'initial_price':
                    row[header] = value.replace(',', '')
                elif header == 'price_change_rate':
                    row[header] = value.split('(')[1].split(')')[0].replace('%', '') if '(' in value else ''
                elif header == 'current_price':
                    row[header] = value.split('\n')[0].replace(',', '')
                    
            data.append(row)
            
        return data
        
    except Exception as e:
        print(f"Error scraping year {year}: {str(e)}")
        return []

def main():
    all_data = {}
    
    # Scrape data from 2001 to 2024
    for year in range(2001, 2025):
        print(f"Scraping year {year}...")
        year_data = get_ipo_data(year)
        if year_data:
            all_data[str(year)] = year_data
        time.sleep(1)  # Add delay between requests
        
    # Save to JSON file
    output_file = '96ut_data_20250826.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
        
    print(f"Data saved to {output_file}")

if __name__ == "__main__":
    main()