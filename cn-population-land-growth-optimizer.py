import streamlit as st
import itertools
import pandas as pd

# =============================================================================
# Government Effects from Official Chart
#
# The following dictionary was inferred from the chart:
#
#   - "happiness": A check indicates +1 bonus; absence means 0.
#   - "land": A check indicates +5% bonus (multiplier 1.05); otherwise 1.00.
#   - "soldier_eff": A check indicates +8% bonus (multiplier 1.08); otherwise 1.00.
#   - "infra_cost": A check indicates a 5% reduction (multiplier 0.95); otherwise 1.00.
#   - "imp_upkeep": A check indicates 5% lower upkeep (multiplier 0.95); otherwise 1.00.
#   - "mil_upkeep": A check indicates 2% lower military upkeep (multiplier 0.98); otherwise 1.00.
#   - "spy_attack": A check indicates +10% bonus (multiplier 1.10); otherwise 1.00.
#
# For this optimization we will use only "happiness" and "land" for adjustments.
# =============================================================================

GOVERNMENTS = {
    "Anarchy": {
        "happiness": 0,
        "land": 1.00,
        "soldier_eff": 1.00,
        "infra_cost": 1.00,
        "imp_upkeep": 1.00,
        "mil_upkeep": 1.00,
        "spy_attack": 1.00
    },
    "Capitalist": {
        "happiness": 0,
        "land": 1.05,
        "soldier_eff": 1.00,
        "infra_cost": 0.95,
        "imp_upkeep": 0.95,
        "mil_upkeep": 1.00,
        "spy_attack": 1.00
    },
    "Communist": {
        "happiness": 0,
        "land": 1.05,
        "soldier_eff": 1.08,
        "infra_cost": 1.00,
        "imp_upkeep": 1.00,
        "mil_upkeep": 0.98,
        "spy_attack": 1.10
    },
    "Democracy": {
        "happiness": 1,
        "land": 1.00,
        "soldier_eff": 1.08,
        "infra_cost": 1.00,
        "imp_upkeep": 1.00,
        "mil_upkeep": 1.00,
        "spy_attack": 1.00
    },
    "Dictatorship": {
        "happiness": 0,
        "land": 1.00,
        "soldier_eff": 1.08,
        "infra_cost": 0.95,
        "imp_upkeep": 1.00,
        "mil_upkeep": 0.98,
        "spy_attack": 1.00
    },
    "Federal Government": {
        "happiness": 0,
        "land": 1.00,
        "soldier_eff": 1.08,
        "infra_cost": 0.95,
        "imp_upkeep": 0.95,
        "mil_upkeep": 1.00,
        "spy_attack": 1.00
    },
    "Monarchy": {
        "happiness": 1,
        "land": 1.05,
        "soldier_eff": 1.00,
        "infra_cost": 0.95,
        "imp_upkeep": 1.00,
        "mil_upkeep": 1.00,
        "spy_attack": 1.00
    },
    "Republic": {
        "happiness": 0,
        "land": 1.05,
        "soldier_eff": 1.00,
        "infra_cost": 0.95,
        "imp_upkeep": 1.00,
        "mil_upkeep": 1.00,
        "spy_attack": 1.10
    },
    "Revolutionary Government": {
        "happiness": 1,
        "land": 1.00,
        "soldier_eff": 1.00,
        "infra_cost": 0.95,
        "imp_upkeep": 0.95,
        "mil_upkeep": 1.00,
        "spy_attack": 1.00
    },
    "Totalitarian State": {
        "happiness": 1,
        "land": 1.05,
        "soldier_eff": 1.00,
        "infra_cost": 1.00,
        "imp_upkeep": 1.00,
        "mil_upkeep": 0.98,
        "spy_attack": 1.00
    },
    "Transitional": {
        "happiness": 0,
        "land": 1.05,
        "soldier_eff": 1.08,
        "infra_cost": 1.00,
        "imp_upkeep": 0.95,
        "mil_upkeep": 1.00,
        "spy_attack": 1.10
    }
}

# =============================================================================
# DEFCON Settings
#
# DEFCON levels affect population happiness:
# DEFCON 5: +2, DEFCON 4: +1, DEFCON 3: 0, DEFCON 2: -1, DEFCON 1: -2.
# =============================================================================
DEFCON_HAPPINESS = {5: 2, 4: 1, 3: 0, 2: -1, 1: -2}

# =============================================================================
# Other Key Variables
#
# War mode is a boolean array indicating whether the nation is at war.
# Tax rate is fixed at 30%, since most players consider taxes lower than 28% intolerable
# and 30% is the standard setting.
# =============================================================================
WAR_MODES = [True, False]
FIXED_TAX_RATE = 30  # Fixed at 30%

# =============================================================================
# Technology Happiness Bonus
# =============================================================================
def tech_happiness_bonus(tech):
    """
    Returns technology happiness bonus based on Cyber Nations scale:
      - tech = 0 → -1
      - 0 < tech <= 0.5 → 0
      - 0.5 < tech <= 1 → +1
      - 1 < tech <= 3 → +2
      - 3 < tech <= 6 → +3
      - 6 < tech <= 10 → +4
      - 10 < tech <= 15 → +5
      - tech > 15 → bonus = 5 + (tech * 0.02) (capped for tech > 200)
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
        max_bonus = 5 + (200 * 0.02)
        return min(bonus, max_bonus)

# =============================================================================
# Population and Land Growth Formulas
#
# For population: We start with a base population influenced by infrastructure and technology.
# Then we add a happiness bonus computed as:
#   total_hap_adj = (government happiness + DEFCON bonus + technology bonus)
# multiplied by a user–tunable factor.
#
# For land growth: We use a natural growth factor based on current land, an infrastructure bonus,
# and the government’s land multiplier.
# =============================================================================

def calculate_population(government, defcon, war_mode, infra, tech, base_pop=1000, happiness_factor=100):
    base_population = base_pop + (infra * 100) + (tech * 10)
    gov_hap = GOVERNMENTS[government]["happiness"]
    defcon_hap = DEFCON_HAPPINESS[defcon]
    tech_hap = tech_happiness_bonus(tech)
    total_hap_adj = gov_hap + defcon_hap + tech_hap
    adjusted_population = base_population + (total_hap_adj * happiness_factor)
    war_multiplier = 0.9 if war_mode else 1.0
    tax_multiplier = 1 - (FIXED_TAX_RATE / 200)
    population = adjusted_population * war_multiplier * tax_multiplier
    return population

def calculate_land_growth(government, infra, base_land):
    natural_growth = 0.5 * (base_land / 1000)
    infra_bonus = 1 + (infra / 100000)
    gov_land_bonus = GOVERNMENTS[government]["land"]
    land_growth = (base_land * natural_growth) * infra_bonus * gov_land_bonus
    return land_growth

def fitness_function(pop, land, weight_pop=1.0, weight_land=1.0):
    return weight_pop * pop + weight_land * land

# =============================================================================
# Optimization Routine
# =============================================================================

def optimize_settings(infra, tech, base_land, weight_pop, weight_land, happiness_factor):
    best_score = -1
    best_config = None
    results = []
    # Since the tax rate is fixed at 30%, we no longer iterate over it.
    for gov, d, w in itertools.product(GOVERNMENTS.keys(), DEFCON_HAPPINESS.keys(), WAR_MODES):
        pop = calculate_population(gov, d, w, infra, tech, happiness_factor=happiness_factor)
        land = calculate_land_growth(gov, infra, base_land)
        score = fitness_function(pop, land, weight_pop, weight_land)
        results.append({
            "Government": gov,
            "DEFCON": d,
            "War_Mode": w,
            "Tax_Rate": FIXED_TAX_RATE,
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
                "Tax_Rate": FIXED_TAX_RATE,
                "Population": round(pop, 2),
                "Land": round(land, 2),
                "Fitness": round(score, 2)
            }
    return best_config, pd.DataFrame(results)

# =============================================================================
# Streamlit User Interface
# =============================================================================

st.title("Cyber Nations | Population + Land Growth Optimization Tool")
st.write("This simulation uses formulas derived from the official Cyber Nations website to optimize settings for maximum population and land growth. Note: The tax rate is fixed at 30% as this is the standard setting tolerated by most players.")

st.sidebar.header("Base Parameters")
infra = st.sidebar.number_input("Infrastructure Level", min_value=0, value=3000, step=100)
tech = st.sidebar.number_input("Technology Level", min_value=0, value=1500, step=50)
base_land = st.sidebar.number_input("Current Land Area", min_value=0, value=1000, step=50)

st.sidebar.header("Optimization Weights and Factors")
weight_pop = st.sidebar.slider("Weight for Population", 0.0, 2.0, 1.0, 0.1)
weight_land = st.sidebar.slider("Weight for Land", 0.0, 2.0, 1.0, 0.1)
happiness_factor = st.sidebar.number_input(
    "Happiness Factor", 
    min_value=1, 
    value=100, 
    step=10,
    help="Scales the total happiness adjustment (from government, DEFCON, and technology). For example, if the total adjustment is 2, a factor of 100 adds 200 to the population. This is needed because the raw adjustments are small integers; the factor amplifies their effect, making happiness a more significant driver of population growth in the model."
)

if st.sidebar.button("Optimize"):
    with st.spinner("Optimizing, please wait..."):
        best_config, results_df = optimize_settings(infra, tech, base_land, weight_pop, weight_land, happiness_factor)
    st.subheader("Best Configuration Found")
    st.write(best_config)
    st.subheader("Evaluated Configurations (Sorted by Highest Fitness)")
    sorted_results = results_df.sort_values(by="Fitness", ascending=False).reset_index(drop=True)
    st.dataframe(sorted_results.head(20))
    csv = sorted_results.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Results",
        data=csv,
        file_name='cyber_nations_population_land_optimization_results.csv',
        mime='text/csv',
    )
