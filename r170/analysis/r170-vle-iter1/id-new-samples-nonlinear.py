import sys
import gpflow
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn
import scipy.optimize as optimize

from fffit.utils import (
    shuffle_and_split,
    values_scaled_to_real,
)


from fffit.models import run_gpflow_scipy
from fffit.pareto import find_pareto_set, is_pareto_efficient

sys.path.append("../")

from utils.r170 import R170Constants
from utils.id_new_samples import (
    prepare_df_density,
    prepare_df_vle,
    rank_samples,
)

R170 = R170Constants()

############################# QUANTITIES TO EDIT #############################
##############################################################################

iternum = 1
gp_shuffle_seed = 584745
##############################################################################
##############################################################################

md_gp_shuffle_seed = 1
liquid_density_threshold = 320  # kg/m^3


# Read VLE files
csv_path = "/scratch365/nwang2/ff_development/HFC_143a_FFO_FF/r170/analysis/csv/"
in_csv_names = [
    "r170-vle-iter" + str(i) + "-results.csv" for i in range(1, iternum + 1)
]
out_csv_name = "r170-vle-iter" + str(iternum + 1) + "-params.csv"
df_csvs = [
    pd.read_csv(csv_path + in_csv_name, index_col=0)
    for in_csv_name in in_csv_names
]
df_csv = pd.concat(df_csvs)
df_vle = prepare_df_vle(df_csv, R170)

# Read liquid density files
max_density_iter = 4
in_csv_names = [
    "r170-density-iter" + str(i) + "-results.csv"
    for i in range(1, max_density_iter + 1)
]
df_csvs = [
    pd.read_csv(csv_path + in_csv_name, index_col=0)
    for in_csv_name in in_csv_names
]
df_csv = pd.concat(df_csvs)
df_all, df_liquid, df_vapor = prepare_df_density(
    df_csv, R170, liquid_density_threshold
)

### Fit GP models to VLE data
# Create training/test set
param_names = list(R170.param_names) + ["temperature"]
property_names = ["sim_liq_density", "sim_vap_density", "sim_Pvap", "sim_Hvap"]

vle_models = {}
for property_name in property_names:
    # Get train/test
    x_train, y_train, x_test, y_test = shuffle_and_split(
        df_vle, param_names, property_name, shuffle_seed=gp_shuffle_seed
    )

    # Fit model
    vle_models[property_name] = run_gpflow_scipy(
        x_train,
        y_train,
        gpflow.kernels.RBF(lengthscales=np.ones(R170.n_params + 1)),
    )

# For vapor density replace with Matern52 kernel
property_name = "sim_vap_density"
# Get train/test
x_train, y_train, x_test, y_test = shuffle_and_split(
    df_vle, param_names, property_name, shuffle_seed=gp_shuffle_seed
)
# Fit model
vle_models[property_name] = run_gpflow_scipy(
    x_train,
    y_train,
    gpflow.kernels.Matern52(lengthscales=np.ones(R170.n_params + 1)),
)

### Fit GP models to liquid density data
# Get train/test
property_name = "md_density"
x_train, y_train, x_test, y_test = shuffle_and_split(
    df_liquid, param_names, property_name, shuffle_seed=md_gp_shuffle_seed
)

# Fit model
md_model = run_gpflow_scipy(
    x_train,
    y_train,
    gpflow.kernels.RBF(lengthscales=np.ones(R170.n_params + 1)),
)


# Get difference between GROMACS/Cassandra density
df_test_points = df_vle[
    list(R170.param_names) + ["temperature", "sim_liq_density"]
]
xx = df_test_points[list(R170.param_names) + ["temperature"]].values
means, vars_ = md_model.predict_f(xx)
diff = values_scaled_to_real(
    df_test_points["sim_liq_density"].values.reshape(-1, 1),
    R170.liq_density_bounds,
) - values_scaled_to_real(means, R170.liq_density_bounds)
print(
    f"The average density difference between Cassandra and GROMACS is {np.mean(diff)} kg/m^3"
)
print(
    f"The minimum density difference between Cassandra and GROMACS is {np.min(diff)} kg/m^3"
)
print(
    f"The maximum density difference between Cassandra and GROMACS is {np.max(diff)} kg/m^3"
)


### Step 3: Find new parameters for simulations
max_mse = 625  # kg^2/m^6
latin_hypercube = np.loadtxt("LHS_500000_x_4.csv", delimiter=",")
ranked_samples = rank_samples( # compare and downselect with MD density results first
    latin_hypercube, md_model, R170, "sim_liq_density", property_offset=13.5
)
print("Ranking samples complete!")
viable_samples = ranked_samples[ranked_samples["mse"] < max_mse].drop(
    columns="mse"
)
viable_samples = viable_samples.values
print(
    "There are:",
    viable_samples.shape[0],
    "viable parameter sets which are within 25 kg/m$^2$ of GROMACS liquid densities",
)

# Calculate other properties
vle_predicted_mses = {}
for property_name, model in vle_models.items():
    vle_predicted_mses[property_name] = rank_samples(
        viable_samples, model, R170, property_name
    )
print("Completed calculating other properties!")

# Merge into single DF
vle_mses = vle_predicted_mses["sim_liq_density"].merge(
    vle_predicted_mses["sim_vap_density"], on=R170.param_names
)
vle_mses = vle_mses.rename(
    {"mse_x": "mse_liq_density", "mse_y": "mse_vap_density"}, axis="columns"
)
vle_mses = vle_mses.merge(vle_predicted_mses["sim_Pvap"], on=R170.param_names)
vle_mses = vle_mses.merge(vle_predicted_mses["sim_Hvap"], on=R170.param_names)
vle_mses = vle_mses.rename(
    {"mse_x": "mse_Pvap", "mse_y": "mse_Hvap"}, axis="columns"
)

# Find pareto efficient points
result, pareto_points, dominated_points = find_pareto_set(
    vle_mses.drop(columns=list(R170.param_names)).values, is_pareto_efficient
)
vle_mses = vle_mses.join(pd.DataFrame(result, columns=["is_pareto"]))

vle_mses.to_csv(csv_path + "vle_mses.csv")

# Plot pareto points vs. MSEs
g = seaborn.pairplot(
    vle_mses,
    vars=["mse_liq_density", "mse_vap_density", "mse_Pvap", "mse_Hvap"],
    hue="is_pareto",
)
g.savefig("figs/R170-pareto-mses-nonlinear.pdf")

# Plot pareto points vs. params
g = seaborn.pairplot(vle_mses, vars=list(R170.param_names), hue="is_pareto")
g.set(xlim=(-0.1, 1.1), ylim=(-0.1, 1.1))
g.savefig("figs/R170-pareto-params-nonlinear.pdf")

