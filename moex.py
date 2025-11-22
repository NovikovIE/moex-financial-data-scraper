import requests
import pandas as pd


def get_moex_tickers():
    """Забирает актуальный состав индекса IMOEX прямо с биржи."""
    print("📡 Запрашиваю состав индекса IMOEX с Мосбиржи...")
    url = "https://iss.moex.com/iss/statistics/engines/stock/markets/index/analytics/IMOEX.json?limit=100"
    response = requests.get(url)
    data = response.json()
        
    columns = data['analytics']['columns']
    rows = data['analytics']['data']
    df = pd.DataFrame(rows, columns=columns)
        
    tickers = df['ticker'].unique().tolist()
    print(f"✅ Найдено {len(tickers)} акций в индексе.")
    
    if 'SBERP' in tickers:
        tickers.remove('SBERP')
        print(f"⚠️ Удаляю привилегированные акции сбера SBERP из списка тикеров, т.к. он не поддерживает API и нерелевантен.")
        
    if 'SNGSP' in tickers:
        tickers.remove('SNGSP')
        print(f"⚠️ Удаляю привилегированные акции Сургутнефтегаз SNGSP из списка тикеров, т.к. он не поддерживает API и нерелевантен.")
    
    if 'TATNP' in tickers:
        tickers.remove('TATNP')
        print(f"⚠️ Удаляю привилегированные акции Татнефть TATNP из списка тикеров, т.к. он не поддерживает API и нерелевантен.")
    
    return tickers


if __name__ == "__main__":
    tickers = get_moex_tickers()
    print(tickers)