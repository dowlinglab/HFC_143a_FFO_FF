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
from utils.r134a import R134aConstants
from matplotlib import ticker

R134a = R134aConstants()
matplotlib.rc("font", family="sans-serif")
matplotlib.rc("font", serif="Arial")

NM_TO_ANGSTROM = 10
K_B = 0.008314 # J/MOL K
KJMOL_TO_K = 1.0 / K_B


def main():
    # ID the top ten by lowest average MAPE
    df = pd.read_csv("../csv/r134a-pareto-iter2.csv", index_col=0)
    dff = pd.read_csv("../csv/r134a-final-iter2.csv", index_col=0)

    seaborn.set_palette('bright', n_colors=len(df))
    data = df[list(R134a.param_names)].values
    result_bounds = np.array([[0, 25], [0, 50], [0, 50], [0, 35]])
    results = values_real_to_scaled(df[["mape_liq_density", "mape_vap_density", "mape_Pvap", "mape_Hvap"]].values, result_bounds)
    data_f = dff[list(R134a.param_names)].values
    results_f = values_real_to_scaled(dff[["mape_liq_density", "mape_vap_density", "mape_Pvap", "mape_Hvap"]].values, result_bounds)
    param_bounds = R134a.param_bounds
    print(param_bounds)
    param_bounds[:5] = param_bounds[:5] * NM_TO_ANGSTROM
    param_bounds[5:] = param_bounds[5:] * KJMOL_TO_K

    data = np.hstack((data, results))
    data_f = np.hstack((data_f, results_f))
    bounds = np.vstack((param_bounds, result_bounds))
    
    col_names = [
        r"$\sigma_{C1}$",
        r"$\sigma_{C2}$",
        r"$\sigma_{F1}$",
        r"$\sigma_{F2}$",
        r"$\sigma_{H1}$",
        r"$\epsilon_{C1}/k_B$",
        r"$\epsilon_{C2}/k_B$",
        r"$\epsilon_{F1}/k_B$",
        r"$\epsilon_{F2}/k_B$",
        r"$\epsilon_{H1}/k_B$",
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

    # Add 10.1021/jp806213w
    '''df_gaff=pd.read_csv("../../gaff/results.csv")
    mape_gaff=[]
    for i in range(df_gaff["temperature"].shape[0]):
        ape=[]
        ape.append(np.abs(df_gaff["liq_density"][i]-R134a.expt_liq_density[int(df_gaff["temperature"][i])])/R134a.expt_liq_density[int(df_gaff["temperature"][i])])
    mape_gaff.append(np.mean(ape))
    for i in range(df_gaff["temperature"].shape[0]):
        ape=[]
        ape.append(np.abs(df_gaff["vap_density"][i]-R134a.expt_vap_density[int(df_gaff["temperature"][i])])/R134a.expt_vap_density[int(df_gaff["temperature"][i])])
    mape_gaff.append(np.mean(ape))
    for i in range(df_gaff["temperature"].shape[0]):
        ape=[]
        ape.append(np.abs(df_gaff["Pvap"][i]-R134a.expt_Pvap[int(df_gaff["temperature"][i])])/R134a.expt_Pvap[int(df_gaff["temperature"][i])])
    mape_gaff.append(np.mean(ape))
    for i in range(df_gaff["temperature"].shape[0]):
        ape=[]
        ape.append(np.abs(df_gaff["Hvap"][i]-R134a.expt_Hvap[int(df_gaff["temperature"][i])]*R134a.molecular_weight/1000)/(R134a.expt_Hvap[int(df_gaff["temperature"][i])]*R134a.molecular_weight/1000)) #convert j/g to kj/mol for experimental values in R134a constants
    mape_gaff.append(np.mean(ape))

    print(mape_gaff)'''
    ax.plot(x_vals[-1], 2.2/bounds[-1][1], markersize=12, color="#0989d9", marker="^", alpha=0.5, clip_on=False, zorder=200,label="Peguin et al.")
    ax.plot(x_vals[-2], 3.1/bounds[-2][1], markersize=12, color="#0989d9", marker="^", alpha=0.5, clip_on=False, zorder=200)
    ax.plot(x_vals[-3], 4.4/bounds[-3][1], markersize=12, color="#0989d9", marker="^", alpha=0.5, clip_on=False, zorder=200)
    ax.plot(x_vals[-4], 0.7/bounds[-4][1], markersize=12, color="#0989d9", marker="^", alpha=0.5, clip_on=False, zorder=200)

    # Remove space between subplots
    plt.subplots_adjust(wspace=0, bottom=0.3)
    #plt.tight_layout()
    #fig.subplots_adjust(left=0, right=50, bottom=0, top=25)
    plt.legend(fontsize=16)  
    fig.savefig("pdfs/fig_r134a-parallel.png",dpi=360)


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

