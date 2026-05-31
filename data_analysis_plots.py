"""
Inputs:  carbon_intensity_seasonal.csv  (processed ENTSO-E data)
         Four raw ENTSO-E CSV files (one per season, 15-min resolution)
Output:  data_analysis_plots.pdf / .png

"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats

# Reproducibility

# Load processed data 
hourly = pd.read_csv('carbon_intensity_seasonal.csv', parse_dates=['hour'])

# Parameters 
mean_iat   = 12096          # mean inter-arrival time (s) = 7*24*3600/50
crane_min  = 90             # min crane cycle time (s) = 3600/40 moves/hr
crane_max  = 144            # max crane cycle time (s) = 3600/25 moves/hr
n_samples  = 1000           # KS test sample size
alpha      = 0.05           # significance level

# Figure layout
fig = plt.figure(figsize=(12, 9))
gs  = gridspec.GridSpec(2, 3, hspace=0.42, wspace=0.35)

season_colors = {
    'Winter': '#3498DB',
    'Spring': '#27AE60',
    'Summer': '#F39C12',
    'Autumn': '#E67E22',
}
season_order = ['Winter', 'Spring', 'Summer', 'Autumn']

#  Plot 1: Exponential PDF (vessel inter-arrival)
ax1 = fig.add_subplot(gs[0, 0])
x   = np.linspace(0, 60000, 500)
pdf = stats.expon.pdf(x, scale=mean_iat)
ax1.plot(x / 60, pdf * 60, color='#2980B9', linewidth=2)
ax1.set_xlabel('Inter-arrival time (min)', fontsize=9)
ax1.set_ylabel('Density', fontsize=9)
ax1.set_title('Vessel arrivals\nExp(λ = 50/week)', fontsize=9, fontweight='bold')
ax1.text(0.97, 0.95, f'Mean = {mean_iat/60:.0f} min',
         transform=ax1.transAxes, ha='right', va='top', fontsize=8)
ax1.grid(True, alpha=0.25)

# Plot 2: Uniform PDF (crane cycle time) 
ax2 = fig.add_subplot(gs[0, 1])
x2  = np.linspace(70, 160, 300)
pdf2 = stats.uniform.pdf(x2, loc=crane_min, scale=crane_max - crane_min)
ax2.plot(x2, pdf2, color='#27AE60', linewidth=2)
ax2.fill_between(x2, pdf2, alpha=0.2, color='#27AE60')
ax2.set_xlabel('Crane cycle time (s)', fontsize=9)
ax2.set_ylabel('Density', fontsize=9)
ax2.set_title('Crane cycle time\nUniform(90, 144 s)', fontsize=9, fontweight='bold')
ax2.text(0.97, 0.95, 'Mean = 117 s',
         transform=ax2.transAxes, ha='right', va='top', fontsize=8)
ax2.grid(True, alpha=0.25)

# Plot 3: Carbon intensity histogram 
ax3 = fig.add_subplot(gs[0, 2])
mu  = hourly['carbon_intensity'].mean()
sig = hourly['carbon_intensity'].std()
ax3.hist(hourly['carbon_intensity'], bins=30,
         color='#E74C3C', alpha=0.7, edgecolor='white',
         linewidth=0.5, density=True)
x3  = np.linspace(200, 700, 300)
ax3.plot(x3, stats.norm.pdf(x3, mu, sig),
         'k--', linewidth=1.5, label='Normal fit')
ax3.set_xlabel('Carbon intensity (gCO₂/kWh)', fontsize=9)
ax3.set_ylabel('Density', fontsize=9)
ax3.set_title('Grid carbon intensity\ndistribution (2024)', fontsize=9, fontweight='bold')
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.25)

# Plot 4: ECDF check for vessel arrivals 
ax4 = fig.add_subplot(gs[1, 0])
samples_exp = np.random.exponential(mean_iat, n_samples)
sorted_s    = np.sort(samples_exp)
ecdf        = np.arange(1, n_samples + 1) / n_samples
theo        = stats.expon.cdf(sorted_s, scale=mean_iat)
ks_stat, ks_p = stats.kstest(samples_exp, 'expon', args=(0, mean_iat))
ax4.plot(sorted_s / 60, ecdf,  color='#2980B9', linewidth=1.5, label='Empirical CDF')
ax4.plot(sorted_s / 60, theo,  'k--',           linewidth=1.5, label='Theoretical CDF')
ax4.set_xlabel('Inter-arrival time (min)', fontsize=9)
ax4.set_ylabel('Cumulative probability', fontsize=9)
ax4.set_title(f'ECDF check — vessel arrivals\n(KS stat={ks_stat:.3f}, p={ks_p:.3f})',
              fontsize=9, fontweight='bold')
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.25)

# Plot 5: Mean diurnal carbon intensity 
ax5 = fig.add_subplot(gs[1, 1])
diurnal = hourly.groupby('hour_of_day')['carbon_intensity'].mean()
ax5.plot(diurnal.index, diurnal.values,
         color='#E74C3C', linewidth=2.5, marker='o', markersize=4)
ax5.fill_between(diurnal.index, diurnal.values, diurnal.min(),
                 alpha=0.12, color='#E74C3C')
ax5.axhline(diurnal.mean(), color='gray', linestyle='--', linewidth=1,
            label=f'Mean: {diurnal.mean():.0f} gCO₂/kWh')
peak_h = diurnal.idxmax()
low_h  = diurnal.idxmin()
ax5.annotate(f'Peak: {diurnal[peak_h]:.0f}\n(hour {peak_h})',
             xy=(peak_h, diurnal[peak_h]),
             xytext=(peak_h - 5, diurnal[peak_h] - 35),
             arrowprops=dict(arrowstyle='->', color='gray'), fontsize=7)
ax5.annotate(f'Low: {diurnal[low_h]:.0f}\n(hour {low_h})',
             xy=(low_h, diurnal[low_h]),
             xytext=(low_h + 1, diurnal[low_h] + 25),
             arrowprops=dict(arrowstyle='->', color='gray'), fontsize=7)
ax5.set_xlabel('Hour of day', fontsize=9)
ax5.set_ylabel('Mean gCO₂/kWh', fontsize=9)
ax5.set_title('Mean diurnal carbon\nintensity profile', fontsize=9, fontweight='bold')
ax5.set_xticks(range(0, 24, 4))
ax5.legend(fontsize=8)
ax5.grid(True, alpha=0.25)

# Plot 6: Seasonal box plots 
ax6 = fig.add_subplot(gs[1, 2])
data_by_season = [
    hourly[hourly['season'] == s]['carbon_intensity'].values
    for s in season_order
]
bp = ax6.boxplot(data_by_season, tick_labels=season_order,
                 patch_artist=True,
                 medianprops=dict(color='black', linewidth=2))
for patch, s in zip(bp['boxes'], season_order):
    patch.set_facecolor(season_colors[s])
    patch.set_alpha(0.75)
ax6.set_ylabel('Carbon intensity (gCO₂/kWh)', fontsize=9)
ax6.set_title('Carbon intensity\nby season', fontsize=9, fontweight='bold')
ax6.tick_params(axis='x', labelsize=8)
ax6.grid(True, alpha=0.25, axis='y')

# Save 
plt.savefig('data_analysis_plots.pdf', bbox_inches='tight', dpi=150)
plt.savefig('data_analysis_plots.png', bbox_inches='tight', dpi=150)
print("Saved: data_analysis_plots.pdf and data_analysis_plots.png")

# Print KS test results 
samples_unif = np.random.uniform(crane_min, crane_max, n_samples)
ks_u, ks_pu  = stats.kstest(samples_unif, 'uniform',
                              args=(crane_min, crane_max - crane_min))
print(f"\nKS test — Exponential (vessel IAT):  stat={ks_stat:.3f}, p={ks_p:.3f}")
print(f"KS test — Uniform     (crane cycle): stat={ks_u:.3f}, p={ks_pu:.3f}")