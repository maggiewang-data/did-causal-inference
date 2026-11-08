"""
Difference-in-Differences: Did California's switch to "active choice" organ
donor registration change its donor registration rate?

Policy: In July 2011 (Q3 2011), California began requiring drivers'-license
applicants to actively answer whether they wanted to register as organ donors.
Comparison group: 26 other U.S. states that made no such change.

Data: Kessler & Roth (2014), distributed in the `causaldata` package
(27 states x 6 quarters, Q4 2010 - Q1 2012).

Run:  python src/did_analysis.py
Outputs: figures/*.png, results/results.md
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from causaldata import organ_donations

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
RES = ROOT / "results"
FIG.mkdir(exist_ok=True)
RES.mkdir(exist_ok=True)

TREATED_STATE = "California"
FIRST_POST_QUARTER = 4  # Quarter_Num 4 = Q3 2011, the first quarter under the new policy
REFERENCE_QUARTER = 3   # Q2 2011, the last pre-policy quarter (event-study baseline)

QUARTER_LABELS = {1: "Q4 2010", 2: "Q1 2011", 3: "Q2 2011",
                  4: "Q3 2011", 5: "Q4 2011", 6: "Q1 2012"}


def load_data() -> pd.DataFrame:
    df = organ_donations.load_pandas().data.copy()
    df["treated"] = (df["State"] == TREATED_STATE).astype(int)
    df["post"] = (df["Quarter_Num"] >= FIRST_POST_QUARTER).astype(int)
    df["treated_post"] = df["treated"] * df["post"]
    return df


# --------------------------------------------------------------------------- #
# 1. Raw trends
# --------------------------------------------------------------------------- #
def plot_trends(df: pd.DataFrame) -> None:
    ca = df[df.treated == 1].groupby("Quarter_Num").Rate.mean()
    ctrl = df[df.treated == 0].groupby("Quarter_Num").Rate.mean()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(ca.index, ca.values, marker="o", lw=2, label="California (treated)")
    ax.plot(ctrl.index, ctrl.values, marker="o", lw=2, label="26 comparison states (mean)")
    ax.axvline(FIRST_POST_QUARTER - 0.5, color="grey", ls="--", lw=1)
    ax.text(FIRST_POST_QUARTER - 0.45, 0.40, "Active choice\nbegins", fontsize=9, color="grey")
    ax.set_xticks(list(QUARTER_LABELS))
    ax.set_xticklabels(QUARTER_LABELS.values())
    ax.set_ylabel("Organ donor registration rate")
    ax.set_title("Registration rates before and after California's policy change")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "01_raw_trends.png", dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 2. Classic 2x2 DiD, computed by hand from group means
# --------------------------------------------------------------------------- #
def two_by_two(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    means = (df.groupby(["treated", "post"]).Rate.mean()
               .unstack("post")
               .rename(index={0: "Comparison states", 1: "California"},
                       columns={0: "Pre", 1: "Post"}))
    means["Change (Post - Pre)"] = means["Post"] - means["Pre"]
    did = (means.loc["California", "Change (Post - Pre)"]
           - means.loc["Comparison states", "Change (Post - Pre)"])
    return means, did


# --------------------------------------------------------------------------- #
# 3. Two-way fixed effects regression
# --------------------------------------------------------------------------- #
def twfe(df: pd.DataFrame):
    model = smf.ols("Rate ~ treated_post + C(State) + C(Quarter_Num)", data=df)
    return model.fit(cov_type="cluster", cov_kwds={"groups": df["State"]})


# --------------------------------------------------------------------------- #
# 4. Event study (dynamic DiD) to check pre-trends
# --------------------------------------------------------------------------- #
def event_study(df: pd.DataFrame):
    d = df.copy()
    terms = []
    for q in sorted(d.Quarter_Num.unique()):
        if q == REFERENCE_QUARTER:
            continue
        col = f"ca_q{q}"
        d[col] = ((d.treated == 1) & (d.Quarter_Num == q)).astype(int)
        terms.append(col)
    formula = "Rate ~ " + " + ".join(terms) + " + C(State) + C(Quarter_Num)"
    fit = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["State"]})

    rows = []
    for q in sorted(d.Quarter_Num.unique()):
        if q == REFERENCE_QUARTER:
            rows.append((q, 0.0, 0.0, 0.0))
        else:
            c = f"ca_q{q}"
            lo, hi = fit.conf_int().loc[c]
            rows.append((q, fit.params[c], lo, hi))
    es = pd.DataFrame(rows, columns=["Quarter_Num", "coef", "ci_low", "ci_high"])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(FIRST_POST_QUARTER - 0.5, color="grey", ls="--", lw=1)
    ax.errorbar(es.Quarter_Num, es.coef,
                yerr=[es.coef - es.ci_low, es.ci_high - es.coef],
                fmt="o", capsize=4, lw=1.5)
    ax.set_xticks(list(QUARTER_LABELS))
    ax.set_xticklabels(QUARTER_LABELS.values())
    ax.set_ylabel("Effect on registration rate\n(relative to Q2 2011)")
    ax.set_title("Event study: California vs. comparison states, by quarter")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "02_event_study.png", dpi=150)
    plt.close(fig)

    leads = [f"ca_q{q}" for q in range(1, REFERENCE_QUARTER)]
    pretrend_test = fit.f_test(" = ".join(leads) + " = 0" if len(leads) > 1 else f"{leads[0]} = 0")
    return es, pretrend_test


# --------------------------------------------------------------------------- #
# 5. Randomization (permutation) inference
#    With only ONE treated state, cluster-robust standard errors are
#    unreliable. Instead, pretend each state was the treated one and ask:
#    how unusual is California's estimate in that distribution?
# --------------------------------------------------------------------------- #
def did_for_state(df: pd.DataFrame, state: str) -> float:
    d = df.copy()
    d["tp"] = ((d.State == state) & (d.post == 1)).astype(int)
    return smf.ols("Rate ~ tp + C(State) + C(Quarter_Num)", data=d).fit().params["tp"]


def randomization_inference(df: pd.DataFrame, actual: float) -> tuple[pd.Series, float]:
    placebo = pd.Series({s: did_for_state(df, s) for s in df.State.unique()})
    p_value = (np.abs(placebo) >= abs(actual) - 1e-12).mean()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    others = placebo.drop(TREATED_STATE)
    ax.hist(others, bins=15, alpha=0.8, label="Placebo estimates (26 other states)")
    ax.axvline(actual, color="crimson", lw=2, label=f"California: {actual:.4f}")
    ax.set_xlabel("DiD estimate if this state had been 'treated'")
    ax.set_ylabel("Number of states")
    ax.set_title("Randomization inference")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "03_randomization_inference.png", dpi=150)
    plt.close(fig)
    return placebo, p_value


# --------------------------------------------------------------------------- #
# 6. Placebo-in-time test: fake a policy at Q1 2011 using pre-period data only
# --------------------------------------------------------------------------- #
def placebo_in_time(df: pd.DataFrame):
    pre = df[df.Quarter_Num < FIRST_POST_QUARTER].copy()
    pre["fake_tp"] = ((pre.treated == 1) & (pre.Quarter_Num >= 2)).astype(int)
    return smf.ols("Rate ~ fake_tp + C(State) + C(Quarter_Num)", data=pre).fit(
        cov_type="cluster", cov_kwds={"groups": pre["State"]})


def main() -> None:
    df = load_data()
    plot_trends(df)

    means, did_manual = two_by_two(df)
    fit = twfe(df)
    est = fit.params["treated_post"]
    es, pretrend = event_study(df)
    placebo, ri_p = randomization_inference(df, est)
    rank = int((placebo.abs() >= abs(est) - 1e-12).sum())
    pit = placebo_in_time(df)

    baseline = means.loc["California", "Pre"]
    md = f"""# Results

## 2x2 difference-in-differences (group means)

{means.round(4).to_markdown()}

**DiD = {did_manual:.4f}** ({did_manual*100:.2f} percentage points)

## Two-way fixed effects (state + quarter FE, SEs clustered by state)

| | Estimate | Std. error | 95% CI |
|---|---|---|---|
| California x Post | {est:.4f} | {fit.bse['treated_post']:.4f} | [{fit.conf_int().loc['treated_post', 0]:.4f}, {fit.conf_int().loc['treated_post', 1]:.4f}] |

Relative to California's pre-policy mean of {baseline:.3f}, that is a **{est/baseline*100:.1f}% change**.

## Event study (reference quarter: Q2 2011)

{es.assign(Quarter=es.Quarter_Num.map(QUARTER_LABELS))[['Quarter', 'coef', 'ci_low', 'ci_high']].round(4).to_markdown(index=False)}

Joint test that both pre-period coefficients equal 0: F = {float(np.squeeze(pretrend.fvalue)):.2f}, p = {float(pretrend.pvalue):.3f}

## Randomization inference

California's estimate ranks **{rank} of {len(placebo)}** in absolute size among all placebo assignments.
Permutation p-value = {ri_p:.3f}  (the smallest possible value with 27 states is {1/len(placebo):.3f}).

## Placebo in time (fake policy in Q1 2011, pre-period data only)

Estimate = {pit.params['fake_tp']:.4f}, 95% CI [{pit.conf_int().loc['fake_tp', 0]:.4f}, {pit.conf_int().loc['fake_tp', 1]:.4f}]
"""
    (RES / "results.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
