import pandas as pd
import numpy as np

from AGV_sim import run_simulation, INPUT_PARAMETERS


OBSERVATION_HOURS = INPUT_PARAMETERS["ObservationPeriod"] / 3600

scenario_names = {
    0: "Baseline charging",
    1: "Opportunity charging",
    2: "Carbon-aware charging"
}

results = []

# Use 10 replications first. Increase later if needed.
N_REPLICATIONS = 10

#For each scenario N_REPLICATIONS are done
for scenario in [0, 1, 2]:
    for seed in range(N_REPLICATIONS):

        test_input = INPUT_PARAMETERS.copy()
        test_input["Scenario"] = scenario

        print(f"Running scenario {scenario}, seed {seed}")

        counters, delivery_df, charging_df = run_simulation(
            input_parameters=test_input,
            seed=seed
        )

        containers = counters["CompletedContainers"]
        total_co2_kg = counters["TotalCO2"] / 1000

        if containers > 0:
            throughput = containers / OBSERVATION_HOURS
            co2_per_teu = total_co2_kg / containers
        else:
            throughput = 0
            co2_per_teu = np.nan

        results.append({
            "Scenario": scenario,
            "ScenarioName": scenario_names[scenario],
            "Seed": seed,
            "CompletedContainers": containers,
            "Throughput_TEU_per_h": throughput,
            "TotalCO2_kg": total_co2_kg,
            "CO2_per_TEU_kg": co2_per_teu
        })


results_df = pd.DataFrame(results)

summary_df = (
    results_df
    .groupby(["Scenario", "ScenarioName"])
    .agg(
        CompletedContainers_mean=("CompletedContainers", "mean"),
        CompletedContainers_std=("CompletedContainers", "std"),
        Throughput_mean=("Throughput_TEU_per_h", "mean"),
        Throughput_std=("Throughput_TEU_per_h", "std"),
        CO2_per_TEU_mean=("CO2_per_TEU_kg", "mean"),
        CO2_per_TEU_std=("CO2_per_TEU_kg", "std"),
        TotalCO2_mean=("TotalCO2_kg", "mean"),
        TotalCO2_std=("TotalCO2_kg", "std")
    )
    .reset_index()
)

# 95% confidence intervals
summary_df["Throughput_CI95"] = 1.96 * summary_df["Throughput_std"] / np.sqrt(N_REPLICATIONS)
summary_df["CO2_per_TEU_CI95"] = 1.96 * summary_df["CO2_per_TEU_std"] / np.sqrt(N_REPLICATIONS)

print("\n=== RAW RESULTS ===")
print(results_df)

print("\n=== SUMMARY RESULTS ===")
print(summary_df)

results_df.to_csv("scenario_results_raw.csv", index=False)
summary_df.to_csv("scenario_results_summary.csv", index=False)

print("\nSaved:")
print("scenario_results_raw.csv")
print("scenario_results_summary.csv")