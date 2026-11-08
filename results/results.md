# Results

## 2x2 difference-in-differences (group means)

| treated           |    Pre |   Post |   Change (Post - Pre) |
|:------------------|-------:|-------:|----------------------:|
| Comparison states | 0.4449 | 0.4589 |                0.0139 |
| California        | 0.2713 | 0.2628 |               -0.0085 |

**DiD = -0.0225** (-2.25 percentage points)

## Two-way fixed effects (state + quarter FE, SEs clustered by state)

| | Estimate | Std. error | 95% CI |
|---|---|---|---|
| California x Post | -0.0225 | 0.0067 | [-0.0356, -0.0093] |

Relative to California's pre-policy mean of 0.271, that is a **-8.3% change**.

## Event study (reference quarter: Q2 2011)

| Quarter   |    coef |   ci_low |   ci_high |
|:----------|--------:|---------:|----------:|
| Q4 2010   | -0.0029 |  -0.0139 |    0.008  |
| Q1 2011   |  0.0063 |   0.0014 |    0.0112 |
| Q2 2011   |  0      |   0      |    0      |
| Q3 2011   | -0.0216 |  -0.0324 |   -0.0107 |
| Q4 2011   | -0.0203 |  -0.0299 |   -0.0107 |
| Q1 2012   | -0.0222 |  -0.0437 |   -0.0006 |

Joint test that both pre-period coefficients equal 0: F = 3.41, p = 0.048

## Randomization inference

California's estimate ranks **5 of 27** in absolute size among all placebo assignments.
Permutation p-value = 0.185  (the smallest possible value with 27 states is 0.037).

## Placebo in time (fake policy in Q1 2011, pre-period data only)

Estimate = 0.0061, 95% CI [-0.0062, 0.0183]
