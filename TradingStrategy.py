import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import gridspec, rc, rcParams
import seaborn as sns
from datetime import datetime, timedelta
import pymysql
from PriceDB import PriceCheck


# Bollinger Band
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

        price = pc.get_price(code, name, start_date, end_date)
        indc = pd.DataFrame()  # indicator dataframe
        
        # Calcluate Bollinger Band
        indc['ma'] = price.close.rolling(window=20).mean()  # 20-day moving average
        indc['stdev'] = price.close.rolling(window=20).std()  # 20-day std
        indc['upperbb'] = indc.ma + 2 * indc.stdev
        indc['lowerbb'] = indc.ma - 2 * indc.stdev

        # %B indicator
        indc['pb'] = (price.close - indc.lowerbb) / (indc.upperbb - indc.lowerbb)

        # Calculate MFI(Money Flow Index)
        indc['tp'] = (price.low + price.close + price.high) / 3  # typical price
        indc['pmf'] = indc.tp * price.volume  # positive money flow
        indc['nmf'] = indc.tp * price.volume  # negative money flow

        for index in range(1, len(indc)):
            if indc.tp.iloc[index] > indc.tp.iloc[index-1]:
                indc.nmf.iloc[index] = 0
            else:
                indc.pmf.iloc[index] = 0
        
        indc['mfi'] = 100 - 100 / (1 + indc.pmf.rolling(window=10).sum()
            / indc.nmf.rolling(window=10).sum())
        
        # Calculate II(Intraday Intensity), II%
        indc['ii'] = (2 * price.close - price.high - price.low) \
            / (price.high - price.low) * price.volume
        indc['iip'] = indc.ii.rolling(window=21).sum() \
            / price.volume.rolling(window=21).sum() * 100

        self.indc = indc.dropna()
        self.price = price.iloc[-len(self.indc):]
        
        plt.style.use('seaborn-darkgrid')
        try:
            rc('font', family='NanumGothic')
            rcParams['axes.unicode_minus'] = False
        except FileNotFoundError:
            print("You should install 'NanumGothic' font.")

    # Trend Trading Strategy
    def trend(self):
        price = self.price
        indc = self.indc

        plt.figure(figsize=(12, 6))
        plt.suptitle(f"Trend Trading: Chart of {self.name}({self.code}) with Bollinger Band, 20 days, 2 std",
                     position=(0.5, 0.93), fontsize=15)

        # Upper chart: chart with BB
        plt.subplot(211)
        plt.plot(price.index, price.close, c='k', linestyle='-', label='Close')
        plt.plot(indc.index, indc.ma, c='0.4', linestyle='-', label='MA20')
        plt.plot(indc.index, indc.upperbb, c='salmon', linestyle='--', label='UpperBB')
        plt.plot(indc.index, indc.lowerbb, c='teal', linestyle='--', label='LowerBB')
        plt.fill_between(indc.index, indc.upperbb, indc.lowerbb, color='0.8')
        
        for index in indc.index:
            if indc.pb.loc[index] > 0.8 and indc.mfi.loc[index] > 80:
                # buy
                plt.plot(index, price.close.loc[index], 'r^')
            elif indc.pb.loc[index] < 0.2 and indc.mfi.loc[index] < 20:
                # sell
                plt.plot(index, price.close.loc[index], 'bv')

        # Lower chart: %B, MFI
        lower_chart = plt.subplot(212)
        ax1 = plt.subplot(lower_chart)
        pb_plot = ax1.plot(indc.index, indc.pb, c='darkcyan', linestyle='-', linewidth=1, label='%B')
        ax1.set_ylim(-0.4, 1.4)
        plt.ylabel('%B')
        plt.axhline(y=0.8, color='0.5', linestyle='--', linewidth=1)
        plt.axhline(y=0.2, color='0.5', linestyle='--', linewidth=1)

        ax2 = ax1.twinx()
        mfi_plot = ax2.plot(indc.index, indc.mfi, c='chocolate', linestyle='-', linewidth=1, label='MFI')
        ax2.set_ylim(-40, 140)
        plt.ylabel('MFI', rotation=270)

        plots = pb_plot + mfi_plot
        labels = [plot.get_label() for plot in plots]
        lower_chart.legend(plots, labels)

        plt.show()

    # Reversal Trading Strategy
    def reversal(self):
        price = self.price
        indc = self.indc

        plt.figure(figsize=(12, 8))
        plt.suptitle(f"Reversal Trading: Chart of {self.name}({self.code}) with Bollinger Band, 20 days, 2 std",
                     position=(0.5, 0.93), fontsize=15)

        # Upper chart: chart with BB
        plt.subplot(311)
        plt.plot(price.index, price.close, c='k', linestyle='-', label='Close')
        plt.plot(indc.index, indc.ma, c='0.4', linestyle='-', label='MA20')
        plt.plot(indc.index, indc.upperbb, c='salmon', linestyle='--', label='UpperBB')
        plt.plot(indc.index, indc.lowerbb, c='teal', linestyle='--', label='LowerBB')
        plt.fill_between(indc.index, indc.upperbb, indc.lowerbb, color='0.8')
        
        for index in indc.index:
            if indc.pb.loc[index] < 0.05 and indc.iip.loc[index] > 0:
                # buy
                plt.plot(index, price.close.loc[index], 'r^')
            elif indc.pb.loc[index] > 0.95 and indc.iip.loc[index] < 0:
                # sell
                plt.plot(index, price.close.loc[index], 'bv')

        # Middle chart: %B
        plt.subplot(312)
        plt.plot(indc.index, indc.pb, c='darkcyan', linestyle='-', linewidth=1, label='%B')
        plt.axis([None, None, -0.4, 1.4])
        plt.ylabel('%B')
        plt.axhline(y=0.95, color='0.5', linestyle='--', linewidth=1)
        plt.axhline(y=0.05, color='0.5', linestyle='--', linewidth=1)
        plt.legend()

        # Lower chart: II%
        plt.subplot(313)
        plt.plot(indc.index, indc.iip, c='chocolate', linestyle='-', linewidth=1, label='II%')
        plt.axis([None, None, -50, 50])
        plt.ylabel('II%')
        plt.axhline(y=0, color='0.5', linestyle='--', linewidth=1)
        plt.legend()

        plt.show()


# Triple Screen Trading
def triple_screen(db_pw, code=None, name=None, start_date=None, end_date=None):
    pc = PriceCheck(db_pw)
    if code is None:
        for stockcode, stockname in pc.code_name_match.items():
            if stockname == name:
                code = stockcode
    if name == None:
        name = pc.code_name_match[code]

    plt.style.use('seaborn-darkgrid')
    try:
        rc('font', family='NanumGothic')
        rcParams['axes.unicode_minus'] = False
    except FileNotFoundError:
        print("You should install 'NanumGothic' font.")

    price = pc.get_price(code, name, start_date, end_date)
    indc = pd.DataFrame()  # indicator dataframe

    indc['ema60'] = price.close.ewm(span=60).mean()  # exponential moving average, 12 weeks
    indc['ema130'] = price.close.ewm(span=130).mean()  # exponential moving average, 26 weeks
    indc['macd'] = indc.ema60 - indc.ema130  # moving average convergence divergence
    indc['signal'] = indc.macd.ewm(span=45).mean()
    indc['macd_hist'] = indc.macd - indc.signal

    plt.figure(figsize=(12, 8))
    plt.suptitle(f"Triple Screen Trading: {name}({code})", position=(0.5, 0.93), fontsize=15)

    # Reflect input to x-axis
    xticks = [0]
    xlabels = [price.iloc[0].date]

    last_row = price.iloc[0]
    for index, row in enumerate(price.itertuples()):
        if index == len(price) - 1:
            break
        if row.date.month != last_row.date.month:
            xticks.append(index)
            xlabels.append(f'{row.date.year}-{row.date.month:02d}')
        last_row = row

    xticks.append(len(price))
    xlabels.append(price.iloc[-1].date)

    if xticks[1] - xticks[0] < 5:
        xlabels[1] = ''
    if xticks[-1] - xticks[-2] < 5:
        xlabels[-2] = ''

    # First Screen
    first_screen = plt.subplot(311)
    first_screen.set_xticks(xticks)
    first_screen.set_xticklabels([])
    
    ax = plt.subplot(first_screen)
    for index, daily in enumerate(price.itertuples()):
        width = 1
        line_width = 0.2
        if daily.close - daily.open != 0:
            height = abs(daily.close - daily.open)
        # Open and close price should appear on chart even if they are the same
        else:
            height = 10 ** (len(str(daily.close)) - 4)
        line_height = (daily.high - daily.low)

        if daily.close >= daily.open:
            ax.add_patch(patches.Rectangle(
                (index + 0.5 * (1 - width), daily.open),
                width,
                height,
                facecolor='maroon',
                fill=True
            ))
            ax.add_patch(patches.Rectangle(
                (index + 0.5 * (1 - line_width), daily.low),
                line_width,
                line_height,
                facecolor='maroon',
                fill=True
            ))
        else:
            ax.add_patch(patches.Rectangle(
                (index + 0.5 * (1 - width), daily.close),
                width,
                height,
                facecolor='navy',
                fill=True
            ))
            ax.add_patch(patches.Rectangle(
                (index + 0.5 * (1 - line_width), daily.low),
                line_width,
                line_height,
                facecolor='navy',
                fill=True
            ))

    plt.plot(range(len(indc)), indc.ema130, c='darkcyan', linestyle='--', label='EMA130')
    plt.legend()

    min_price = min(price.low)
    max_price = max(price.high)
    gap = max_price - min_price
    plt.axis([None, None, min_price - gap * 0.1, max_price + gap * 0.1])

    # Second Screen
    second_screen = plt.subplot(312)
    
    # Third Screen
    third_screen = plt.subplot(313)
    

    plt.show()


if __name__ == '__main__':
    pw = '12357'
    # bb = BB(db_pw=pw, name='삼성전자', start_date='2019-01-01', end_date='2020-12-31')
    # bb.reversal()
    triple_screen(db_pw=pw, name='삼성전자', start_date='2019-01-01', end_date='2020-12-31')
