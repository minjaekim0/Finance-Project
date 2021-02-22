import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import gridspec, rc, rcParams
from datetime import datetime, timedelta
from tqdm import tqdm
import pymysql
from selenium import webdriver
from bs4 import BeautifulSoup
from ChartTool import candlestick_chart


class PriceUpdate:

    def __init__(self, db_pw):
        self.connection = pymysql.connect(
            host='localhost', user='root', db='trading_db', password=db_pw, charset='utf8')
        with self.connection.cursor() as cursor:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_info (
                code VARCHAR(20),
                company VARCHAR(40),
                last_update DATE,
                PRIMARY KEY (code)
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_price (
                code VARCHAR(20),
                date DATE,
                open BIGINT(20),
                high BIGINT(20),
                low BIGINT(20),
                close BIGINT(20),
                differ FLOAT(8, 2),
                volume BIGINT(20),
                PRIMARY KEY (code, date)
            );
            """)
        self.connection.commit()
        self.code_name_match = {}
        self.update_company_info()

    def __del__(self):
        self.connection.close()

    # Return currently listed stocks
    # noinspection PyMethodMayBeStatic
    def read_stock_code(self):
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        stock_codes = pd.read_html(url, header=0)[0]
        stock_codes = stock_codes[['종목코드', '회사명']]
        stock_codes = stock_codes.rename(columns={'종목코드': 'code', '회사명': 'company'})
        stock_codes.code = stock_codes.code.map('{:06d}'.format)
        stock_codes = stock_codes.sort_values(by='code')
        return stock_codes

    # Reflect currently listed stocks on DB
    def update_company_info(self):
        sql = "SELECT * FROM company_info"
        info_df = pd.read_sql(sql, self.connection)
        for row in info_df.itertuples():
            self.code_name_match[row.code] = row.company

        with self.connection.cursor() as cursor:
            cursor.execute("""SELECT MAX(last_update) FROM company_info""")
            last_update = cursor.fetchone()
            today = datetime.today().strftime('%Y-%m-%d')
            
            # If DB is empty or last update date is not today:
            if last_update[0] is None or last_update[0].strftime('%Y-%m-%d') < today:
                stock_codes = self.read_stock_code()
                for row in stock_codes.itertuples():
                    sql = f"REPLACE INTO company_info (code, company, last_update) VALUES " \
                          f"('{row.code}', '{row.company}', '{today}')"
                    cursor.execute(sql)
                    self.code_name_match[row.code] = row.company
        print('company_info DB Update Completed')

    # Crawling price data up to {count} days from now
    def read_days(self, count):
        with self.connection.cursor() as cursor:
            options = webdriver.ChromeOptions()
            options.add_argument('headless')
            # Options for speed up
            prefs = {'profile.default_content_setting_values': {
                'cookies': 2, 'images': 2, 'plugins': 2, 'popups': 2, 'geolocation': 2, 'notifications': 2,
                'auto_select_certificate': 2, 'fullscreen': 2, 'mouselock': 2, 'mixed_script': 2,
                'media_stream': 2, 'media_stream_mic': 2, 'media_stream_camera': 2, 'protocol_handlers': 2,
                'ppapi_broker': 2, 'automatic_downloads': 2, 'midi_sysex': 2, 'push_messaging': 2,
                'ssl_cert_decisions': 2, 'metro_switch_to_desktop': 2, 'protected_media_identifier': 2,
                'app_banner': 2, 'site_engagement': 2, 'durable_storage': 2}}
            options.add_experimental_option('prefs', prefs)
            driver = webdriver.Chrome(executable_path='chromedriver', options=options)

            today = datetime.today()
            y = today.year
            m = today.month
            d = today.day

            for number, stockcode in enumerate(tqdm(self.code_name_match.keys())):
                url = f'https://fchart.stock.naver.com/siseJson.nhn?symbol={stockcode}&requestType=2' \
                      f'&count={count}&startTime={y}{m:02d}{d:02d}&timeframe=day'
                driver.get(url)
                r = driver.page_source
                html = BeautifulSoup(r, 'lxml')
                split_html = str(html).split('\n\t\t\n')

                columns = ['code', 'date', 'open', 'high', 'low', 'close', 'differ', 'volume']
                last_close = 0
                days_value_list = []

                for daily_value in split_html[1:-1]:
                    daily_value = daily_value.replace('"', '').replace(',', '').strip('[]')
                    daily_value = daily_value.split(' ')[:-1]

                    temp_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                    temp_df = pd.DataFrame([daily_value], columns=temp_columns)
                    temp_df[['open', 'high', 'low', 'close', 'volume']] = \
                        temp_df[['open', 'high', 'low', 'close', 'volume']].astype('int')

                    if last_close != 0:
                        differ = (temp_df.close.values[0] / last_close - 1) * 100
                    else:
                        differ = 0

                    differ_df = pd.DataFrame([differ], columns=['differ'])
                    code_df = pd.DataFrame([stockcode], columns=['code'])
                    daily_value_df = pd.concat([temp_df, code_df, differ_df], axis=1)
                    daily_value_df = daily_value_df[columns]
                    days_value_list.append(daily_value_df)

                    last_close = int(daily_value_df.close.values[0])

                days_value_df = pd.concat(days_value_list)
                days_value_df.columns = columns
                days_value_df = days_value_df.dropna()

                for daily in days_value_df.itertuples():
                    sql = f"REPLACE INTO daily_price VALUES ('{daily.code}', '{daily.date}', " \
                          f"{daily.open}, {daily.high}, {daily.low}, {daily.close}, " \
                          f"{daily.differ}, {daily.volume})"
                    cursor.execute(sql)
                self.connection.commit()

            print('daily_price DB Update Completed')

    # Crawling price data from last update date to today
    def read_recent(self):
        with self.connection.cursor() as cursor:
            today = datetime.today()
            yesterday = today - timedelta(days=1)
            cursor.execute("""SELECT MAX(date) FROM daily_price""")
            last_date = datetime.strptime(str(cursor.fetchone()[0]), '%Y-%m-%d')
            recent = last_date.day == today.day \
                or (last_date.day == yesterday.day and int(today.strftime('%H')) < 9)

            if recent:
                print('The most recent update date is today.')
            else:
                options = webdriver.ChromeOptions()
                options.add_argument('headless')
                prefs = {'profile.default_content_setting_values': {
                    'cookies': 2, 'images': 2, 'plugins': 2, 'popups': 2, 'geolocation': 2, 'notifications': 2,
                    'auto_select_certificate': 2, 'fullscreen': 2, 'mouselock': 2, 'mixed_script': 2,
                    'media_stream': 2, 'media_stream_mic': 2, 'media_stream_camera': 2, 'protocol_handlers': 2,
                    'ppapi_broker': 2, 'automatic_downloads': 2, 'midi_sysex': 2, 'push_messaging': 2,
                    'ssl_cert_decisions': 2, 'metro_switch_to_desktop': 2, 'protected_media_identifier': 2,
                    'app_banner': 2, 'site_engagement': 2, 'durable_storage': 2}}
                options.add_experimental_option('prefs', prefs)
                driver = webdriver.Chrome(executable_path='chromedriver', options=options)

                no_update_term = (today - last_date).days

                # Consider weekend
                count = int(no_update_term * 5 / 7) + 2

                y = today.year
                m = today.month
                d = today.day

                for number, stockcode in enumerate(tqdm(self.code_name_match.keys())):
                    url = f'https://fchart.stock.naver.com/siseJson.nhn?symbol={stockcode}&requestType=2' \
                          f'&count={count}&startTime={y}{m:02d}{d:02d}&timeframe=day'
                    driver.get(url)
                    r = driver.page_source
                    html = BeautifulSoup(r, 'lxml')
                    split_html = str(html).split('\n\t\t\n')

                    columns = ['code', 'date', 'open', 'high', 'low', 'close', 'differ', 'volume']
                    last_close = 0
                    days_value_list = []

                    for daily_value in split_html[1:-1]:
                        daily_value = daily_value.replace('"', '').replace(',', '').strip('[]')
                        daily_value = daily_value.split(' ')[:-1]

                        temp_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                        temp_df = pd.DataFrame([daily_value], columns=temp_columns)
                        temp_df[['open', 'high', 'low', 'close', 'volume']] = \
                            temp_df[['open', 'high', 'low', 'close', 'volume']].astype('int')

                        if last_close != 0:
                            differ = (temp_df.close.values[0] / last_close - 1) * 100
                        else:
                            differ = 0

                        differ_df = pd.DataFrame([differ], columns=['differ'])
                        code_df = pd.DataFrame([stockcode], columns=['code'])
                        daily_value_df = pd.concat([temp_df, code_df, differ_df], axis=1)
                        daily_value_df = daily_value_df[columns]
                        days_value_list.append(daily_value_df)

                        last_close = daily_value_df.close.values[0]
                        last_close = int(last_close)

                    try:
                        days_value_df = pd.concat(days_value_list)
                    except ValueError:
                        # The stock is going to be listed today
                        # In this case, this stock's page is empty
                        pass
                    else:
                        days_value_df.columns = columns
                        days_value_df = days_value_df.dropna()

                        for daily in days_value_df.itertuples():
                            # Some intervals overlap existing data -> REPLACE instead of INSERT
                            sql = f"REPLACE INTO daily_price VALUES ('{daily.code}', '{daily.date}', " \
                                  f"{daily.open}, {daily.high}, {daily.low}, {daily.close}, " \
                                  f"{daily.differ}, {daily.volume})"
                            cursor.execute(sql)
                        self.connection.commit()

                print('daily_price DB Update Completed')


class PriceCheck:

    def __init__(self, db_pw):
        self.connection = pymysql.connect(
            host='localhost', user='root', db='trading_db', password=db_pw, charset='utf8')
        self.code_name_match = {}
        self.get_company_info()

    def __del__(self):
        self.connection.close()

    # Reflect currently listed stocks on DB
    def get_company_info(self):
        info_df = pd.read_sql("SELECT * FROM company_info", self.connection)
        for row in info_df.itertuples():
            self.code_name_match[row.code] = row.company

    # Return price data of input
    def get_price(self, code=None, name=None, start_date=None, end_date=None):
        # start_date default: one year ago, end_date default: today
        if start_date is None:
            one_year_ago = datetime.today() - timedelta(days=365)
            start_date = one_year_ago.strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.today().strftime('%Y-%m-%d')
        
        # User will input either code or name
        # If input name, match code / else ok
        if code is None:
            for stockcode, stockname in self.code_name_match.items():
                if stockname == name:
                    code = stockcode

        sql = f"SELECT * FROM daily_price " \
              f"WHERE code = '{code}' and date >= '{start_date}' and date <= '{end_date}'"
        price_df = pd.read_sql(sql, self.connection)
        price_df.index = price_df.date

        price_df['code'] = code
        price_df['name'] = name
        price_df['start_date'] = start_date
        price_df['end_date'] = end_date

        return price_df


if __name__ == '__main__':
    pw = '12357'

    # pu = PriceUpdate(pw)
    # pu.read_recent()

    pc = PriceCheck(pw)
    price_df = pc.get_price(name='SK하이닉스', start_date='2021-01-01', end_date='2021-02-22')
    candlestick_chart(price_df)