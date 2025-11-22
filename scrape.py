import requests
import pandas as pd
import io
import time

from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime

from moex import get_moex_tickers
from constants import PROMPT, COMMON_HEADERS


def get_current_date() -> str:
    """Возвращает текущую дату в формате ДД.ММ.ГГГГ"""
    return datetime.now().strftime("%d.%m.%Y")


def get_cbr_key_rate():
    """Парсит ключевую ставку с главной страницы ЦБ РФ"""
    url = "https://www.cbr.ru/"
    response = requests.get(url, headers=COMMON_HEADERS, timeout=10)
        
    soup = BeautifulSoup(response.text, 'html.parser')
        
    indicators = soup.find_all('div', class_='main-indicator')
        
    for ind in indicators:
        if 'Ключевая ставка' in ind.get_text():
            value_tag = ind.find('div', class_='main-indicator_value')
            if value_tag:
                return value_tag.get_text(strip=True)
        
    raise Exception("Ключевая ставка не найдена")
    

def get_moex_price_api(ticker: str) -> str:
    """
    Получает последнюю цену акции через официальный API Мосбиржи (ISS).
    Режим торгов TQBR (акции и д/р), формат JSON.
    """
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
    
    params = {'iss.meta': 'off', 'iss.only': 'marketdata'}
    response = requests.get(url, params=params, timeout=5)
    data = response.json()
        
    if 'marketdata' in data and 'data' in data['marketdata'] and data['marketdata']['data']:
        columns = data['marketdata']['columns']
        values = data['marketdata']['data'][0]

        if 'LAST' in columns:
            last_idx = columns.index('LAST')
            price = values[last_idx]
            if price is not None:
                return str(price)
            
        if 'PREVPRICE' in columns:
            prev_idx = columns.index('PREVPRICE')
            return str(values[prev_idx])
                
    raise Exception("Ошибка получения цены акции из API Мосбиржи")
            

def get_ticker_data(ticker: str) -> tuple:
    url = f"https://smart-lab.ru/q/{ticker}/f/q/MSFO/"
    headers_browser = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"📡 Запрос данных по {ticker}...")
    response = requests.get(url, headers=headers_browser, timeout=10)
    response.raise_for_status()
        
    dfs = pd.read_html(io.StringIO(response.text), match='202')
        
    soup = BeautifulSoup(response.text, 'html.parser')
    factors_data = get_factors(soup)
        
    df = dfs[0]
        
    header_row_idx = None
        
    for i in range(min(5, len(df))):
        row_str = df.iloc[i].astype(str).values
        if any('LTM' in x for x in row_str) or any('20' in x for x in row_str):
            header_row_idx = i
            break
        
    if header_row_idx is not None:
        new_header = df.iloc[header_row_idx].astype(str).tolist()
            
        new_header[0] = "Metric"
            
        df.columns = new_header
        df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
    else:
        print("⚠️ Внимание: Строка с датами не найдена, использую стандартные индексы.")
        df.rename(columns={0: 'Metric'}, inplace=True)

    key_metrics = [
        'Чистая прибыль', 'OIBDA', 'EBITDA', 'Чистый долг', 'Net Debt', 
        'Наличность', 'Cash', 'ROE', 'P/E', 'Дивиденд', 'FCF', 'EPS',
        'Свободный денежный'
    ]
        
    mask = df['Metric'].astype(str).apply(lambda x: any(k.lower() in x.lower() for k in key_metrics))
    final_df = df[mask].copy()
        
    final_df = final_df.loc[:, final_df.columns.notna()]
    final_df = final_df.loc[:, final_df.columns != 'nan']
    
    for col in final_df.columns:
        if 'smart-lab.ru' in col: 
            final_df.drop(columns=[col], inplace=True)
    
    final_df.reset_index(drop=True, inplace=True)
        
    return final_df, factors_data

def get_factors(soup: BeautifulSoup) -> dict:
    """Выдирает текст 'За' и 'Против' из блока факторов."""
    factors = {'Pros': [], 'Cons': []}
    
    up_div = soup.find('div', class_='reasons-up')
    if up_div:
        factors['Pros'] = [li.get_text(strip=True) for li in up_div.find_all('li')]
            
    down_div = soup.find('div', class_='reasons-down')
    if down_div:
        factors['Cons'] = [li.get_text(strip=True) for li in down_div.find_all('li')]
            
    return factors

def build_portfolio(tickers: list) -> tuple:
    print(f"🚀 Начинаю сканирование портфеля: {tickers}")
    dfs = []
    factors_data = []
    prices = []
    
    for t in tqdm(tickers):
        df, factors = get_ticker_data(t)
        dfs.append(df)
        factors_data.append(factors)
        
        moex_price = get_moex_price_api(t)
        prices += [moex_price]
        
        time.sleep(0.5)
    
    return dfs, factors_data, prices

def combine_data(dfs: list, factors_data: list, prices: list, tickers: list) -> str:
    result = ""

    result += "📊 Портфель по {} тикерам:\n".format(len(dfs))

    for i in range(len(dfs)):
        result += "📊 Портфель {}/{}: {}\n".format(i+1, len(dfs), tickers[i])
        result += dfs[i].to_string(index=False) + "\n"
        result += "Цена акции: {}\n".format(prices[i])
        result += "Замечания с сайта smart-lab.ru\n"
        for factor in factors_data[i]['Pros']:
            result += "✅ {}\n".format(factor)
        for factor in factors_data[i]['Cons']:
            result += "❌ {}\n".format(factor)
        result += "-" * 30 + "\n"

    return result

if __name__ == "__main__":
    today = get_current_date()
    print(f"📅 Сегодня дата: {today}")
    
    cbr_key_rate = get_cbr_key_rate()
    print(f"🏦 Ключевая ставка ЦБ РФ: {cbr_key_rate}")
    
    tickers = get_moex_tickers()
    dfs, factors_data, prices = build_portfolio(tickers)
    str_result = combine_data(dfs, factors_data, prices, tickers)
    
    print(str_result)
    
    promt = PROMPT.format(today, cbr_key_rate, tickers, str_result)

    with open("prompt.txt", "w") as f:
        f.write(promt)

    print("📝 Записал промпт в файл prompt.txt")
