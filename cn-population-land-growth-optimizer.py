import streamlit as st
import itertools
import pandas as pd

# =============================================================================
# Official Cyber Nations–Based Values and Formulas
#
# Note: Cyber Nations contains hundreds of variables. This script incorporates
# a subset focused on population and land growth:
#   - Government type: affects population happiness (via an absolute bonus)
#     and land area bonus.
#   - DEFCON: as per CN, the DEFCON levels affect population happiness:
#         DEFCON 5 → +2, 4 → +1, 3 → 0, 2 → –1, 1 → –2.
#   - Technology: affects happiness in a tiered manner.
#   - Infrastructure: each infra level adds citizens.
#   - Tax rate: penalizes growth.
#   - War mode: reduces overall growth.
#
# For full details, please refer to:
# https://www.cybernations.net/about_topics.asp
# =============================================================================

# ---------------- Government Settings ----------------
# For government type we use two keys:
# - "happiness_adj": the absolute adjustment (in happiness units) applied to the base happiness.
# - "land": the multiplier for land growth (e.g. +8% land area means 1.08).
GOVERNMENTS = {
    "Anarchy": {"happiness_adj": -1, "land": 1.0},              # Negative environment effect
    "Capitalist": {"happiness_adj": 5, "land": 0.95},            # +5 happiness; -5% land
    "Communist": {"happiness_adj": 5, "land": 1.08},             # +5 happiness; +8% land
    "Democracy": {"happiness_adj": 1, "land": 1.08},             # +1 happiness; +8% land
    "Dictatorship": {"happiness_adj": 8, "land": 0.95},          # +8 happiness; -5% land
    "Federal": {"happiness_adj": 8, "land": 0.95},               # +8 happiness; -5% land
    "Monarchy": {"happiness_adj": 1, "land": 1.05},              # +1 happiness; +5% land
    "Republic": {"happiness_adj": 5, "land": 0.95},              # +5 happiness; -5% land
    "Revolutionary": {"happiness_adj": 1, "land": 0.95},         # +1 happiness; -5% land
    "Totalitarian State": {"happiness_adj": 1, "land": 1.05},    # +1 happiness; +5% land
    "Transitional": {"happiness_adj": 5, "land": 1.08}           # +5 happiness; +8% land
}

# ---------------- DEFCON Settings ----------------
# As per the CN website, DEFCON levels affect population happiness:
DEFCON_HAPPINESS = {5: 2, 4: 1, 3: 0, 2: -1, 1: -2}

# ---------------- Other Key Variables ----------------
# War mode (True if at war; reduces growth) and Tax Rates (in percent 1% to 28%)
WAR_MODES = [True, False]
TAX_RATES = list(range(1, 29))

# ---------------- Technology Happiness Bonus ----------------
def tech_happiness_bonus(tech):
    """
    Returns the technology happiness bonus based on the CN scale:
      - tech = 0 → -1 happiness
      - 0 < tech <= 0.5 → 0 bonus
      - 0.5 < tech <= 1 → +1 bonus
      - 1 < tech <= 3 → +2 bonus
      - 3 < tech <= 6 → +3 bonus
      - 6 < tech <= 10 → +4 bonus
      - 10 < tech <= 15 → +5 bonus
      - tech > 15 → bonus = 5 + (tech * 0.02) (capped at level 200)
    Note: In a complete simulation tech is purchased in whole numbers.
    """
    if tech <= 0:
        return -1
    elif tech <= 0.5:
        return 0
    elif tech <= 1:
        return 1
    elif tech <= 3:
        return 2
    elif tech <= 6:
        return 3
    elif tech <= 10:
        return 4
    elif tech <= 15:
        return 5
    else:
        bonus = 5 + (tech * 0.02)
        # cap bonus if tech exceeds 200 levels
        max_bonus = 5 + (200 * 0.02)
        return min(bonus, max_bonus)

# =============================================================================
# Population and Land Growth Formulas
# =============================================================================

def calculate_population(government, defcon, war_mode, tax_rate, infra, tech, base_pop=1000, happiness_factor=100):
    """
    Calculate the nation's effective population.
    
    Components:
      1. Base Population: Derived from a starting value plus contributions
         from infrastructure and technology.
           - Each infrastructure level adds roughly 100 citizens.
           - Each technology level adds roughly 10 citizens.
      2. Happiness Adjustments: Sum of:
           - Government happiness adjustment (absolute).
           - DEFCON bonus/penalty (as per DEFCON_HAPPINESS).
           - Technology happiness bonus (per tech_happiness_bonus).
         These are multiplied by a happiness_factor to convert units to citizen count.
      3. War & Tax Effects:
           - War mode imposes a multiplier (0.9 if at war).
           - Tax rate imposes a penalty (modeled here as a linear factor).
    
    Formula:
      effective_population = (base_pop + infra*100 + tech*10 + (total_hap_adj * happiness_factor))
                             * war_multiplier * tax_multiplier
    """
    # Base population from initial value, infrastructure, and technology.
    base_population = base_pop + (infra * 100) + (tech * 10)
    
    # Get absolute adjustments from government, DEFCON, and technology.
    gov_hap = GOVERNMENTS[government]["happiness_adj"]
    defcon_hap = DEFCON_HAPPINESS[defcon]
    tech_hap = tech_happiness_bonus(tech)
    total_hap_adj = gov_hap + defcon_hap + tech_hap

    # Add the happiness contribution.
    adjusted_population = base_population + (total_hap_adj * happiness_factor)
    
    # Apply penalties:
    war_multiplier = 0.9 if war_mode else 1.0
    tax_multiplier = 1 - (tax_rate / 200)  # adjustable scaling

    population = adjusted_population * war_multiplier * tax_multiplier
    return population

def calculate_land_growth(government, infra, base_land):
    """
    Calculate effective land growth.
    
    Components:
      1. Natural Growth: Land increases naturally at ~0.5 miles per day scaled to current land.
      2. Infrastructure Bonus: Every ~1000 infra points add a 1% bonus.
      3. Government Land Multiplier: As defined in the GOVERNMENTS dict.
    
    Formula:
      effective_land_growth = (base_land * natural_growth_factor)
                              * (1 + infra/100000)
                              * (government land multiplier)
    """
    natural_growth = 0.5 * (base_land / 1000)  # scaling factor based on base land
    infra_bonus = 1 + (infra / 100000)         # every 1000 infra ~1% bonus
    gov_land_bonus = GOVERNMENTS[government]["land"]
    
    land_growth = (base_land * natural_growth) * infra_bonus * gov_land_bonus
    return land_growth

def fitness_function(pop, land, weight_pop=1.0, weight_land=1.0):
    """
    Combine population and land growth into a single fitness score.
    This is a simple weighted sum:
         fitness = (weight_pop * population) + (weight_land * land)
    """
    return weight_pop * pop + weight_land * land

# =============================================================================
# Optimization Routine
# =============================================================================

def optimize_settings(infra, tech, base_land, weight_pop, weight_land, happiness_factor):
    """
    Searches over combinations of government type, DEFCON level, war mode, and tax rate.
    Returns the configuration that maximizes our fitness function.
    """
    best_score = -1
    best_config = None
    results = []
    
    # Iterate over every combination using itertools.product
    for gov, d, w, t in itertools.product(GOVERNMENTS.keys(), DEFCON_HAPPINESS.keys(), WAR_MODES, TAX_RATES):
        pop = calculate_population(gov, d, w, t, infra, tech, happiness_factor=happiness_factor)
        land = calculate_land_growth(gov, infra, base_land)
        score = fitness_function(pop, land, weight_pop, weight_land)
        results.append({
            "Government": gov,
            "DEFCON": d,
            "War_Mode": w,
            "Tax_Rate": t,
            "Population": round(pop, 2),
            "Land": round(land, 2),
            "Fitness": round(score, 2)
        })
        if score > best_score:
            best_score = score
            best_config = {
                "Government": gov,
                "DEFCON": d,
                "War_Mode": w,
                "Tax_Rate": t,
                "Population": round(pop, 2),
                "Land": round(land, 2),
                "Fitness": round(score, 2)
            }
    return best_config, pd.DataFrame(results)

# =============================================================================
# Streamlit User Interface
# =============================================================================

st.title("Cyber Nations Optimization Tool")
st.write("This simulation uses formulas derived from the official Cyber Nations website to optimize settings for maximum population and land growth.")

st.sidebar.header("Base Parameters")
infra = st.sidebar.number_input("Infrastructure Level", min_value=0, value=3000, step=100)
tech = st.sidebar.number_input("Technology Level", min_value=0, value=1500, step=50)
base_land = st.sidebar.number_input("Current Land Area", min_value=0, value=1000, step=50)

st.sidebar.header("Optimization Weights and Factors")
weight_pop = st.sidebar.slider("Weight for Population", 0.0, 2.0, 1.0, 0.1)
weight_land = st.sidebar.slider("Weight for Land", 0.0, 2.0, 1.0, 0.1)
happiness_factor = st.sidebar.number_input("Happiness Factor", min_value=1, value=100, step=10,
                                           help="Each unit of happiness adjustment (gov + DEFCON + tech) is multiplied by this factor.")

if st.button("Optimize Settings"):
    with st.spinner("Optimizing, please wait..."):
        best_config, results_df = optimize_settings(infra, tech, base_land, weight_pop, weight_land, happiness_factor)
    
    st.subheader("Best Configuration Found")
    st.write(best_config)
    
    st.subheader("Sample of Evaluated Configurations")
    st.dataframe(results_df.sort_values(by="Fitness", ascending=False).reset_index(drop=True).head(20))
    
    # Option to download full results as CSV.
    csv = results_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download full results as CSV",
        data=csv,
        file_name='cyber_nations_optimization_results.csv',
        mime='text/csv',
    )
