import matplotlib.pyplot as plt

class x_axis_setting:
    def __init__(self, x_data, show_labels=True):
        xticks = []
        xlabels = []
            
        n = len(x_data) // 10
        
        for index, date in enumerate(x_data):
            if index % n == (len(x_data)-1) % n:
                xticks.append(index)
                if n <= 10:
                    xlabels.append(date.strftime('%Y-%m-%d'))
                elif n <= 200:
                    xlabels.append(date.strftime('%Y-%m'))
                else:
                    xlabels.append(date.strftime('%Y'))
        
        plt.gca().set_xticks(xticks)
        if show_labels:
            plt.gca().set_xticklabels(xlabels, rotation=45, minor=False)
        else:
            plt.gca().set_xticklabels([], rotation=45, minor=False)

        self.xticks = xticks
        self.xlabels = xlabels
    
    def xticks(self):
        return self.xticks
        
    def xlabels(self):
        return self.xlabels