from pandas import read_excel

from cschedule.plotting import plot_calendar

results_path = "../results/results.xlsx"

if __name__ == "__main__":
    results_df = read_excel(results_path)
    plot_calendar(results_df)
