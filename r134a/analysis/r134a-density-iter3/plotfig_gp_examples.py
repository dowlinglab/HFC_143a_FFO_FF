import sys
import gpflow
import numpy as np
from scipy import stats
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from fffit.utils import (
    shuffle_and_split,
    values_real_to_scaled,
    values_scaled_to_real,
    variances_scaled_to_real,
)

from fffit.plot import (
    plot_model_performance,
    plot_slices_temperature,
    plot_slices_params,
    plot_model_vs_test,
)

from fffit.models import run_gpflow_scipy

sys.path.append("../")

from utils.r134a import R134aConstants
from utils.id_new_samples import prepare_df_density

R134a = R134aConstants()

pdf = PdfPages('fig_gp_examples.pdf')

############################# QUANTITIES TO EDIT #############################
##############################################################################

iternum = 3
gp_shuffle_seed = 8278573

##############################################################################
##############################################################################

csv_path = "../csv/"
in_csv_names = ["r134a-density-iter" + str(i) + "-results.csv" for i in range(1, iternum+1)]
#out_csv_name = "r134a-density-iter" + str(iternum + 1) + "-params.csv"

# Read files

df_csvs = [pd.read_csv(csv_path + in_csv_name, index_col=0) for in_csv_name in in_csv_names]
df_csv = pd.concat(df_csvs)
df_all, df_liq, df_vap = prepare_df_density(df_csv, R134a,liquid_density_threshold=500)
df_all = df_liq #Set df_all to df_liq to only plot liquid GP parity plots

### Fit GP Model to liquid density
param_names = list(R134a.param_names) + ["temperature"]
property_name = "md_density"
x_train, y_train, x_test, y_test = shuffle_and_split(
    df_all, param_names, property_name, shuffle_seed=gp_shuffle_seed, fraction_train=0.8
)

# Fit model
models = {}
models["RBF"] = run_gpflow_scipy(
    x_train,
    y_train,
    gpflow.kernels.RBF(lengthscales=np.ones(R134a.n_params + 1)),
)
models["Matern32"] = run_gpflow_scipy(
    x_train,
    y_train,
    gpflow.kernels.Matern32(lengthscales=np.ones(R134a.n_params + 1)),
)

models["Matern52"] = run_gpflow_scipy(
    x_train,
    y_train,
    gpflow.kernels.Matern52(lengthscales=np.ones(R134a.n_params + 1)),
)

# Plot model performance on train and test points
pdf.savefig(plot_model_performance(models, x_train, y_train, R134a.liq_density_bounds))
pdf.savefig(plot_model_performance(models, x_test, y_test, R134a.liq_density_bounds))

# Plot temperature slices
figs = plot_slices_temperature(
    models,
    R134a.n_params,
    R134a.temperature_bounds,
    R134a.liq_density_bounds,
    property_name="Liquid Density [kg/m^3]",
)

try:
    for fig in figs:
        pdf.savefig(fig)
except:
    pdf.savefig(figs)
del figs

# Plot parameter slices
for param_name in R134a.param_names:
    figs = plot_slices_params(
        models,
        param_name,
        R134a.param_names,
        300,
        R134a.temperature_bounds,
        R134a.liq_density_bounds,
        property_name="Liquid Density [kg/m^3]",
    )
    try:
        for fig in figs:
            pdf.savefig(fig)
    except:
        pdf.savefig(figs)
    del figs

# Loop over test params
for test_params in x_test[:,:R134a.n_params]:
    train_points = []
    test_points = []
    # Locate rows where parameter set == test parameter set
    matches = np.unique(np.where((df_all[list(R134a.param_names)] == test_params).all(axis=1))[0])
    # Loop over all matches -- these will be different temperatures
    for match in matches:
        # If the match (including T) is in the test set, then append to test points
        if np.where((df_all.values[match,:R134a.n_params+1] == x_test[:,:R134a.n_params+1]).all(axis=1))[0].shape[0] == 1:
            test_points.append([df_all["temperature"].iloc[match],df_all[property_name].iloc[match]])
        # Else append to train points
        else:
            train_points.append([df_all["temperature"].iloc[match],df_all[property_name].iloc[match]])

    pdf.savefig(
        plot_model_vs_test(
            models,
            test_params,
            np.asarray(train_points),
            np.asarray(test_points),
            R134a.temperature_bounds,
            R134a.liq_density_bounds,
            property_name="Liquid Density [kg/m^3]"
        )
    )
pdf.close()

