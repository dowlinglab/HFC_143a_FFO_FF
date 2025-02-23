import sys
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatch
import seaborn

sys.path.append("../")

from fffit.utils import values_scaled_to_real
from fffit.utils import values_real_to_scaled
from utils.r143a import R143aConstants
from matplotlib import ticker

R143a = R143aConstants()

matplotlib.rc("font", family="sans-serif")
matplotlib.rc("font", serif="Arial")

NM_TO_ANGSTROM = 10
K_B = 0.008314 # J/MOL K
KJMOL_TO_K = 1.0 / K_B


def main():
    # ID the top ten by lowest average MAPE
    df = pd.read_csv("../csv/r143a-pareto.csv", index_col=0)
    dff = pd.read_csv("../csv/r143a-final-4.csv", index_col=0)

    seaborn.set_palette('bright', n_colors=len(df))
    #No need to plot top ten (this should be a multi-objective optimization)
    #top10 = df.loc[df.filter(regex="mape*").mean(axis=1).sort_values()[:10].index] #only sorted by one column
    #print(top10)
    #data = top10[list(R143a.param_names)].values
    data = df[list(R143a.param_names)].values
    result_bounds = np.array([[0, 10], [0, 20], [0, 20], [0, 10]])
    results = values_real_to_scaled(top10[["mape_liq_density", "mape_vap_density", "mape_Pvap", "mape_Hvap"]].values, result_bounds)
    data_f = dff[list(R143a.param_names)].values
    results_f = values_real_to_scaled(dff[["mape_liq_density", "mape_vap_density", "mape_Pvap", "mape_Hvap"]].values, result_bounds)
    param_bounds = R143a.param_bounds
    param_bounds[:4] = param_bounds[:4] * NM_TO_ANGSTROM # need to change 4 to (the number of sigma or epsilon)
    param_bounds[4:] = param_bounds[4:] * KJMOL_TO_K

    data = np.hstack((data, results))
    data_f = np.hstack((data_f, results_f))
    bounds = np.vstack((param_bounds, result_bounds))

    col_names = [
        r"$\sigma_{C1}$",
        r"$\sigma_{C2}$",
        r"$\sigma_{F1}$",
        r"$\sigma_{H1}$",
        r"$\epsilon_{C1}$",
        r"$\epsilon_{C2}$",
        r"$\epsilon_{F1}$",
        r"$\epsilon_{H1}$",
        "MAPE\n" + r"$\rho^l_{\mathrm{sat}}$",
        "MAPE\n" + r"$\rho^v_{\mathrm{sat}}$",
        "MAPE\n" + r"$P_{\mathrm{vap}}$",
        "MAPE\n" + r"$\Delta H_{\mathrm{vap}}$",
    ]
    n_axis = len(col_names)
    assert data.shape[1] == n_axis
    x_vals = [i for i in range(n_axis)]
    
    # Create (N-1) subplots along x axis
    fig, axes = plt.subplots(1, n_axis-1, sharey=False, figsize=(20,5))
    
    # Plot each row
    for i, ax in enumerate(axes):
        for line in data:
            ax.plot(x_vals, line, alpha=0.45)
        ax.set_xlim([x_vals[i], x_vals[i+1]])
        for line in data_f:
            ax.plot(x_vals, line, alpha=1.0, linewidth=3)

    for dim, ax in enumerate(axes):
        ax.xaxis.set_major_locator(ticker.FixedLocator([dim]))
        set_ticks_for_axis(ax, bounds[dim], nticks=6)
        if dim < 10:
            ax.set_xticklabels([col_names[dim]], fontsize=24)
        else:
            ax.set_xticklabels([col_names[dim]], fontsize=20)
        ax.set_ylim(-0.05,1.05)
        # Add white background behind labels
        for label in ax.get_yticklabels():
            label.set_bbox(
                dict(
                    facecolor='white',
                    edgecolor='none',
                    alpha=0.45,
                    boxstyle=mpatch.BoxStyle("round4")
                )
            )
        ax.spines['top'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_linewidth(2.0)

    ax = axes[-1]
    ax.xaxis.set_major_locator(ticker.FixedLocator([n_axis-2, n_axis-1]))
    ax.set_xticklabels([col_names[-2], col_names[-1]], fontsize=20)

    ax = plt.twinx(axes[-1])
    ax.set_ylim(-0.05, 1.05)
    set_ticks_for_axis(ax, bounds[-1], nticks=6)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['right'].set_linewidth(2.0)

    # Add GAFF
    #ax.plot(x_vals[-1], 22.37/bounds[-1][1], markersize=12, color="gray", marker="s", clip_on=False, zorder=200)
    #ax.plot(x_vals[-2], 46.05/bounds[-2][1], markersize=12, color="gray", marker="s", clip_on=False, zorder=200)
    #ax.plot(x_vals[-3], 50.52/bounds[-3][1], markersize=12, color="gray", marker="s", clip_on=False, zorder=200)
    #ax.plot(x_vals[-4], 2.92/bounds[-4][1], markersize=12, color="gray", marker="s", clip_on=False, zorder=200)


    # Remove space between subplots
    plt.subplots_adjust(wspace=0, bottom=0.2)
    
    fig.savefig("pdfs/fig_r143a-parallel-top10.pdf")


def set_ticks_for_axis(ax, param_bounds, nticks):
    """Set the tick positions and labels on y axis for each plot

    Tick positions based on normalised data
    Tick labels are based on original data
    """
    min_val, max_val = param_bounds
    step = (max_val - min_val) / float(nticks-1)
    tick_labels = [round(min_val + step * i, 2) for i in range(nticks)]
    ticks = np.linspace(0, 1.0, nticks)
    ax.yaxis.set_ticks(ticks)
    ax.set_yticklabels(tick_labels, fontsize=16)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(2))
    ax.tick_params("y", direction="inout", which="both", length=7)
    ax.tick_params("y", which="major", length=14)
    ax.tick_params("x", pad=15) 

if __name__ == "__main__":
    main()

