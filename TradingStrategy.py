import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import gridspec, rc, rcParams
import seaborn as sns
from datetime import datetime, timedelta
import pymysql
from PriceDB import PriceCheck


class BB:

    def __init__(self, db_pw, code=None, name=None, start_date=None, end_date=None):   
        pc = PriceCheck(db_pw)
        if code is None:
            for stockcode, stockname in pc.code_name_match.items():
                if stockname == name:
                    code = stockcode
        if name == None:
            name = pc.code_name_match[code]
        self.code = code
        self.name = name

        price_df = pc.get_price(code, name, start_date, end_date)
        indc_df = pd.DataFrame()  # indicator dataframe
        
        # Calcluate Bollinger Band
        indc_df['ma'] = price_df.close.rolling(window=20).mean()  # 20-day moving average
        indc_df['stdev'] = price_df.close.rolling(window=20).std()  # 20-day std
        indc_df['upperbb'] = indc_df.ma + 2 * indc_df.stdev
        indc_df['lowerbb'] = indc_df.ma - 2 * indc_df.stdev

        # %B indicator
        indc_df['pb'] = (price_df.close - indc_df.lowerbb) / (indc_df.upperbb - indc_df.lowerbb)

        # Calculate MFI(Money Flow Index)
        indc_df['tp'] = (price_df.low + price_df.close + price_df.high) / 3  # typical price
        indc_df['pmf'] = indc_df.tp * price_df.volume  # positive money flow
        indc_df['nmf'] = indc_df.tp * price_df.volume  # negative money flow

        for index in range(1, len(indc_df)):
            if indc_df.tp.iloc[index] > indc_df.tp.iloc[index-1]:
                indc_df.nmf.iloc[index] = 0
            else:
                indc_df.pmf.iloc[index] = 0
        
        indc_df['mfi'] = 100 - 100 / (1 + indc_df.pmf.rolling(window=10).sum()
            / indc_df.nmf.rolling(window=10).sum())
        
        # Calculate II(Intraday Intensity), II%
        indc_df['ii'] = (2 * price_df.close - price_df.high - price_df.low) \
            / (price_df.high - price_df.low) * price_df.volume
        indc_df['iip'] = indc_df.ii.rolling(window=21).sum() \
            / price_df.volume.rolling(window=21).sum() * 100

        self.indc_df = indc_df.dropna()
        self.price_df = price_df.iloc[-len(self.indc_df):]
        
        plt.style.use('seaborn-darkgrid')
        try:
            rc('font', family='NanumGothic')
            rcParams['axes.unicode_minus'] = False
        except FileNotFoundError:
            print("You should install 'NanumGothic' font.")

    # Trend Trading Strategy
    def trend(self):
        price_df = self.price_df
        indc_df = self.indc_df

        plt.figure(figsize=(12, 6))
        plt.suptitle(f"Trend Trading: Chart of {self.name}({self.code}) with Bollinger Band, 20 days, 2 std",
                     position=(0.5, 0.93), fontsize=15)

        # Upper chart: chart with BB
        plt.subplot(211)
        plt.plot(price_df.index, price_df.close, c='k', linestyle='-', label='Close')
        plt.plot(indc_df.index, indc_df.ma, c='0.4', linestyle='-', label='MA20')
        plt.plot(indc_df.index, indc_df.upperbb, c='salmon', linestyle='--', label='UpperBB')
        plt.plot(indc_df.index, indc_df.lowerbb, c='teal', linestyle='--', label='LowerBB')
        plt.fill_between(indc_df.index, indc_df.upperbb, indc_df.lowerbb, color='0.8')
        
        for index in indc_df.index:
            if indc_df.pb.loc[index] > 0.8 and indc_df.mfi.loc[index] > 80:
                # buy
                plt.plot(index, price_df.close.loc[index], 'r^')
            elif indc_df.pb.loc[index] < 0.2 and indc_df.mfi.loc[index] < 20:
                # sell
                plt.plot(index, price_df.close.loc[index], 'bv')

        # Lower chart: %B, MFI
        lower_chart = plt.subplot(212)
        ax1 = plt.subplot(lower_chart)
        pb_plot = ax1.plot(indc_df.index, indc_df.pb, c='darkcyan', linestyle='-', linewidth=1, label='%B')
        ax1.set_ylim(-0.4, 1.4)
        plt.ylabel('%B')
        plt.axhline(y=0.8, color='0.5', linestyle='--', linewidth=1)
        plt.axhline(y=0.2, color='0.5', linestyle='--', linewidth=1)

        ax2 = ax1.twinx()
        mfi_plot = ax2.plot(indc_df.index, indc_df.mfi, c='chocolate', linestyle='-', linewidth=1, label='MFI')
        ax2.set_ylim(-40, 140)
        plt.ylabel('MFI', rotation=270)

        plots = pb_plot + mfi_plot
        labels = [plot.get_label() for plot in plots]
        lower_chart.legend(plots, labels)

        plt.show()

    # Reversal Trading Strategy
    def reversal(self):
        price_df = self.price_df
        indc_df = self.indc_df

        plt.figure(figsize=(12, 8))
        plt.suptitle(f"Reversal Trading: Chart of {self.name}({self.code}) with Bollinger Band, 20 days, 2 std",
                     position=(0.5, 0.93), fontsize=15)

        # Upper chart: chart with BB
        plt.subplot(311)
        plt.plot(price_df.index, price_df.close, c='k', linestyle='-', label='Close')
        plt.plot(indc_df.index, indc_df.ma, c='0.4', linestyle='-', label='MA20')
        plt.plot(indc_df.index, indc_df.upperbb, c='salmon', linestyle='--', label='UpperBB')
        plt.plot(indc_df.index, indc_df.lowerbb, c='teal', linestyle='--', label='LowerBB')
        plt.fill_between(indc_df.index, indc_df.upperbb, indc_df.lowerbb, color='0.8')
        
        for index in indc_df.index:
            if indc_df.pb.loc[index] < 0.05 and indc_df.iip.loc[index] > 0:
                # buy
                plt.plot(index, price_df.close.loc[index], 'r^')
            elif indc_df.pb.loc[index] > 0.95 and indc_df.iip.loc[index] < 0:
                # sell
                plt.plot(index, price_df.close.loc[index], 'bv')

        # Middle chart: %B
        plt.subplot(312)
        plt.plot(indc_df.index, indc_df.pb, c='darkcyan', linestyle='-', linewidth=1, label='%B')
        plt.axis([None, None, -0.4, 1.4])
        plt.ylabel('%B')
        plt.axhline(y=0.95, color='0.5', linestyle='--', linewidth=1)
        plt.axhline(y=0.05, color='0.5', linestyle='--', linewidth=1)
        plt.legend()

        # Lower chart: II%
        plt.subplot(313)
        plt.plot(indc_df.index, indc_df.iip, c='chocolate', linestyle='-', linewidth=1, label='II%')
        plt.axis([None, None, -50, 50])
        plt.ylabel('II%')
        plt.axhline(y=0, color='0.5', linestyle='--', linewidth=1)
        plt.legend()

        plt.show()


if __name__ == '__main__':
    pw = '12357'
    bb = BB(db_pw=pw, name='삼성전자', start_date='2019-01-01', end_date='2020-12-31')
    bb.reversal()
