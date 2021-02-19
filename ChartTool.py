import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import gridspec, rc, rcParams
from datetime import datetime, timedelta


# If datetime format is used in x axis, x axis contains weekends.
# Therefore, new x axis setting tool is needed.
class x_axis_setting:

    def __init__(self, dates, setting=True, show_labels=True):
        
        xticks = []
        xlabels = []
        
        n = len(dates) // 10
        
        if n == 0:
            for index, date in enumerate(dates):
                xticks.append(index)
                xlabels.append(date.strftime('%Y-%m-%d'))
        else:
            for index, date in enumerate(dates):
                if index % n == (len(dates)-1) % n:
                    xticks.append(index)
                    if n <= 10:
                        xlabels.append(date.strftime('%Y-%m-%d'))
                    elif n <= 200:
                        xlabels.append(date.strftime('%Y-%m'))
                    else:
                        xlabels.append(date.strftime('%Y'))
        
        if setting:
            plt.gca().set_xticks(xticks)

            if show_labels:
                plt.gca().set_xticklabels(xlabels, rotation=45, minor=False)
            else:
                plt.gca().set_xticklabels([], rotation=45, minor=False)

        self.xticks = xticks
        self.xlabels = xlabels


# Just add price bars(candlestick) at existing chart.
def price_bar(ax, price_df, up=None, down=None, show_labels=False):
    if up == None:
        up = 'r'
    if down == None:
        down = 'b'

    x_axis_setting(price_df.date, True, show_labels)

    for index, daily in enumerate(price_df.itertuples()):
        width = 0.8
        line_width = 0.12
        if daily.close - daily.open != 0:
            height = abs(daily.close - daily.open)
        # Open and close price should appear on chart even if they are the same
        else:
            height = daily.close / 1000
        line_height = (daily.high - daily.low)

        if daily.close >= daily.open:
            ax.add_patch(patches.Rectangle(
                (index - 0.5 *  width, daily.open),
                width, 
                height,
                facecolor=up,
                fill=True
            ))
            ax.add_patch(patches.Rectangle(
                (index - 0.5 * line_width, daily.low),
                line_width,
                line_height,
                facecolor=up,
                fill=True
            ))
        else:
            ax.add_patch(patches.Rectangle(
                (index - 0.5 * width, daily.close),
                width,
                height,
                facecolor=down,
                fill=True
            ))
            ax.add_patch(patches.Rectangle(
                (index - 0.5 * line_width, daily.low),
                line_width,
                line_height,
                facecolor=down,
                fill=True
            ))

    min_price = min(price_df.low)
    max_price = max(price_df.high)
    gap = max_price - min_price
    plt.axis([None, None, min_price - gap * 0.1, max_price + gap * 0.1])

    
# Just add volume bars(candlestick) at existing chart.
# volume increase -> red / decrease -> blue
def volume_bar(ax, price_df, up=None, down=None, show_labels=True):
    if up == None:
        up = 'r'
    if down == None:
        down = 'b'
    
    x_axis_setting(price_df.date, True, show_labels)

    last_volume = 0
    for index, daily in enumerate(price_df.itertuples()):
        width = 0.8
        height = daily.volume

        if daily.volume >= last_volume:
            ax.add_patch(patches.Rectangle(
                (index - 0.5 * width, 0),
                width,
                height,
                facecolor=up,
                fill=True
            ))
        else:
            ax.add_patch(patches.Rectangle(
                (index - 0.5 * width, 0),
                width,
                height,
                facecolor=down,
                fill=True
            ))
        last_volume = daily.volume

    max_volume = max(price_df.volume)
    plt.axis([None, None, 0, max_volume * 1.2])


# Full candlestick chart
def candlestick_chart(price_df, up=None, down=None):
    code = price_df.code[0]
    name = price_df.name[0]
    start_date = price_df.start_date[0]
    end_date = price_df.end_date[0]
    
    rc('font', family='NanumGothic')
    rcParams['axes.unicode_minus'] = False

    plt.figure(figsize=(12, 6), dpi=100)
    plt.suptitle(f"{name}({code}) Candlestick Chart ({start_date} ~ {end_date})",
                fontsize=15, position=(0.5, 0.93))
    gs = gridspec.GridSpec(nrows=3, ncols=1, height_ratios=[5, 2, 0.3])

    price_plot = plt.subplot(gs[0])
    price_bar(price_plot, price_df, up, down, False)
    plt.grid(color='gray', linestyle='-')
    plt.ylabel('ohlc candles')
    plt.axis([-0.5, len(price_df)-0.5, None, None])

    volume_plot = plt.subplot(gs[1])
    volume_bar(volume_plot, price_df, up, down, True)
    plt.grid(color='gray', linestyle='-')
    plt.ylabel('volume')
    plt.axis([-0.5, len(price_df)-0.5, None, None])

    plt.subplots_adjust(hspace=0.1)
    plt.show()