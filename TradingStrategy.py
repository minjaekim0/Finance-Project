import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import gridspec, rc, rcParams
import seaborn as sns
from scipy.optimize import minimize
from datetime import datetime, timedelta
import pymysql
from PriceDB import PriceCheck
from ChartTool import x_axis_setting, price_bar


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
        indc['ma'] = price.close.rolling(window=20, min_periods=1).mean()  # 20-day moving average
        indc['stdev'] = price.close.rolling(window=20, min_periods=1).std()  # 20-day std
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
        
        indc['mfi'] = 100 - 100 / (1 + indc.pmf.rolling(window=10, min_periods=1).sum()
            / indc.nmf.rolling(window=10, min_periods=1).sum())
        
        # Calculate II(Intraday Intensity), II%
        indc['ii'] = (2 * price.close - price.high - price.low) \
            / (price.high - price.low) * price.volume
        indc['iip'] = indc.ii.rolling(window=21, min_periods=1).sum() \
            / price.volume.rolling(window=21, min_periods=1).sum() * 100

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
    rc('font', family='NanumGothic')
    rcParams['axes.unicode_minus'] = False

    price = pc.get_price(code, name, start_date, end_date)
    indc = pd.DataFrame()  # indicator dataframe

    # macd
    indc['ema60'] = price.close.ewm(span=60).mean()  # exponential moving average, 12 weeks
    indc['ema130'] = price.close.ewm(span=130).mean()  # exponential moving average, 26 weeks
    indc['macd'] = indc.ema60 - indc.ema130  # moving average convergence divergence
    indc['signal'] = indc.macd.ewm(span=45).mean()
    indc['macd_hist'] = indc.macd - indc.signal

    # stochastic
    highest = price.high.rolling(window=14, min_periods=1).max()
    lowest = price.low.rolling(window=14, min_periods=1).min()
    indc['pk'] = (price.close - lowest) / (highest - lowest) * 100  # %K
    indc['pd'] = indc.pk.rolling(window=3, min_periods=1).mean()
    
    # Plotting
    plt.figure(figsize=(14, 7))
    plt.suptitle(f"Triple Screen Trading: {name}({code})", position=(0.5, 0.93), fontsize=15)

    # First Screen
    first_screen = plt.subplot(311)
    first_screen.grid(True)
    ax = plt.subplot(first_screen)
    price_bar(ax, price, up='r', down='b', show_labels=False)
    plt.plot(range(len(indc)), indc.ema130, c='darkcyan', label='EMA130')
    plt.legend()

    # Buy / Sell
    for i in range(len(price)):
        if indc.ema130.iloc[i] < indc.ema130.iloc[i-1] and \
            indc.pd.iloc[i-1] >= 20 and indc.pd.iloc[i] < 20:
            plt.plot(i, price.close.iloc[i], c='maroon', marker='^')
        elif indc.ema130.iloc[i] > indc.ema130.iloc[i-1] and \
            indc.pd.iloc[i-1] <= 80 and indc.pd.iloc[i] > 80:
            plt.plot(i, price.close.iloc[i], c='navy', marker='v')

    # Second Screen
    second_screen = plt.subplot(312)
    plt.plot(range(len(indc)), indc.macd, c='coral', label='MACD')
    plt.plot(range(len(indc)), indc.signal, c='steelblue', label='MACD Signal')
    plt.bar(range(len(indc)), indc.macd_hist, color='indigo', label='MACD Hist')
    x_axis_setting(price.date, True, False)
    plt.legend()

    # Third Screen
    third_screen = plt.subplot(313)
    plt.plot(range(len(indc)), indc.pk, c='olive', label='%K')
    plt.plot(range(len(indc)), indc.pd, c='k', label='%D')
    plt.axhline(y=20, color='0.5', linestyle='--', linewidth=1)
    plt.axhline(y=80, color='0.5', linestyle='--', linewidth=1)
    x_axis_setting(price.date, True, True)
    plt.legend()

    plt.show()


# Modern Portfolio Theory
class MPT:
    def __init__(self, db_pw, codes=None, names=None, start_date=None, end_date=None):
        np.random.seed(0)
        pc = PriceCheck(db_pw)
        company_info = pc.code_name_match
        if names == None:
            names = [company_info[code] for code in codes]

        self.names = names

        close_df = pd.DataFrame()
        for stock_name in names:
            close_df[stock_name] = pc.get_price(name=stock_name, start_date=start_date, end_date=end_date).close
        self.close_df = close_df

        # Assume annual trading days are 250 days
        daily_return = close_df.pct_change()
        annual_return = daily_return.mean(axis=0) * 250
        annual_cov = daily_return.cov() * 250
        self.annual_return = annual_return
        self.annual_cov = annual_cov

        # Portfolios made randomly
        portfolios_list = []

        for index in range(10000):
            weights = np.random.random(len(self.names))
            weights = weights / sum(weights)
            return_ = np.dot(weights, annual_return)
            risk_ = np.sqrt(np.dot(weights.T, np.dot(annual_cov, weights)))
            # Assume risk free interest rate = 0
            Sharpe = return_ / risk_
            temp_df = pd.DataFrame([[return_, risk_, weights, Sharpe]],
                                columns=['return_', 'risk_', 'weights', 'Sharpe'])
            portfolios_list.append(temp_df)

        portfolios = pd.concat(portfolios_list, ignore_index=True)
        self.portfolios = portfolios


    def efficient_frontier(self):
        annual_return = self.annual_return
        annual_cov = self.annual_cov
        portfolios = self.portfolios

        return_range = np.linspace(min(portfolios.return_), max(portfolios.return_), 100)
        efficient_list = []

        def neg_sharpe(weights):
            weights_return_ = np.dot(weights, annual_return)
            weights_risk_ = np.sqrt(np.dot(weights.T, np.dot(annual_cov, weights)))
            return - weights_return_ / weights_risk_

        def sum_is_one(weights):
            return sum(weights) - 1

        number = len(portfolios.loc[0].weights)
        init_weights = np.array([1 / number]) * number
        bounds = [[0, 1]] * number

        # 각 return 값들에 대해 minimize risk
        for opt_return_ in return_range:
            def return_constraint(weights):
                return np.dot(weights, annual_return) - opt_return_
            constraints = [{'type': 'eq', 'fun': sum_is_one},
                        {'type': 'eq', 'fun': return_constraint}]
            opt = minimize(neg_sharpe, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
            opt_weights = opt.x
            opt_risk_ = np.sqrt(np.dot(opt_weights.T, np.dot(annual_cov, opt_weights)))
            temp_df = pd.DataFrame([[opt_return_, opt_risk_, opt_weights, -opt.fun]],
                                columns=['return_', 'risk_', 'weights', 'Sharpe'])
            efficient_list.append(temp_df)
        return pd.concat(efficient_list, ignore_index=True)
    
    def efficient_frontier_plot(self):
        portfolios = self.portfolios
        efficient_frontier = self.efficient_frontier()

        rc('font', family='NanumGothic')
        rcParams['axes.unicode_minus'] = False
        
        plt.figure()
        plt.title(self.names)

        plt.scatter(portfolios.risk_, portfolios.return_, c=portfolios.Sharpe,
                    cmap=sns.color_palette('flare', as_cmap=True), s=5)
        plt.plot(efficient_frontier.risk_, efficient_frontier.return_, c='k', linewidth=3)

        lowest_risk_index = efficient_frontier.index[
            efficient_frontier.risk_ == min(efficient_frontier.risk_)][0]
        lowest_risk_ = efficient_frontier.loc[lowest_risk_index].risk_
        return_at_lowest_risk_ = efficient_frontier.loc[lowest_risk_index].return_

        plt.scatter(lowest_risk_, return_at_lowest_risk_, c='r', s=50, zorder=10)

        for i, weight in enumerate(efficient_frontier.weights):
            if i % 10 == lowest_risk_index % 10 and i >= lowest_risk_index:
                plt.annotate([int(100 * r) for r in weight], \
                    (efficient_frontier.risk_[i], efficient_frontier.return_[i]),
                    xytext=(lowest_risk_ - 0.01 * len(names), efficient_frontier.return_[i] - 0.002))
        
        plt.axis([lowest_risk_ - 0.05, None, None, None])
        plt.xlabel('Risk')
        plt.ylabel('Return')
        plt.show()




if __name__ == '__main__':
    pw = '12357'

    # bb = BB(db_pw=pw, name='삼성전자', start_date='2019-01-01', end_date='2020-12-31')
    # bb.trend()
    
    # triple_screen(db_pw=pw, name='포스코', start_date='2018-01-01', end_date='2021-02-20')
    
    codes = ['000660', '005380', '035420', '035720']
    mpt = MPT(db_pw=pw, codes=codes, start_date='2017-01-01', end_date='2020-12-31')
    mpt.efficient_frontier_plot()