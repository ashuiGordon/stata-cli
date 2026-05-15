# stata-cli skill

Stata reference library built into stata-cli. Covers syntax, data management,
econometrics, causal inference, graphics, Mata programming, and 20+ community
packages. Use `stata-cli skill <topic>` to read a specific reference.

## Critical Gotchas

### Missing Values Sort to +Infinity
Stata's `.` (and `.a`-`.z`) are **greater than all numbers**.
```stata
* WRONG — includes observations where income is missing!
gen high_income = (income > 50000)

* RIGHT
gen high_income = (income > 50000) if !missing(income)
```

### `=` vs `==`
`=` is assignment; `==` is comparison.
```stata
* WRONG — syntax error
gen employed = 1 if status = 1

* RIGHT
gen employed = 1 if status == 1
```

### Local Macro Syntax
Locals use `` `name' `` (backtick + single-quote). Globals use `$name`.
```stata
local controls "age education income"
regress wage `controls'        // correct
regress wage `controls         // WRONG — missing closing quote
```

### `by` Requires Prior Sort (Use `bysort`)
```stata
bysort id: gen first = (_n == 1)    // RIGHT — bysort sorts automatically
```

### Factor Variable Notation
Use `i.` for categorical, `c.` for continuous.
```stata
* WRONG — treats race as continuous
regress wage race education

* RIGHT — creates dummies
regress wage i.race education
```

### `merge` Always Check `_merge`
```stata
merge 1:1 id using other.dta
tab _merge
drop _merge
```

### Stored Results: `r()` vs `e()` vs `s()`
- `r()` — r-class (summarize, tabulate)
- `e()` — e-class (regress, logit)
- `s()` — s-class (parsing)

A new estimation command **overwrites** previous `e()` results. Use `estimates store`.

## Common Patterns

### Regression Table Workflow
```stata
eststo clear
eststo: regress y x1 x2, vce(robust)
eststo: regress y x1 x2 x3, vce(robust)
esttab using "results.tex", replace se star(* 0.10 ** 0.05 *** 0.01) label booktabs
```

### Panel Data Setup
```stata
xtset panelid timevar
reghdfe y x1 x2, absorb(panelid timevar) vce(cluster panelid)
```

### Difference-in-Differences
```stata
* Classic 2x2 DiD
gen post = (year >= treatment_year)
gen treat_post = treated * post
regress y treated post treat_post, vce(cluster id)

* Modern staggered DiD (Callaway & Sant'Anna)
csdid y x1 x2, ivar(id) time(year) gvar(first_treat) agg(event)
```

### Data Cleaning Pipeline
```stata
import delimited "raw_data.csv", clear varnames(1)
rename *, lower
destring income, replace force
replace income = . if income < 0
label variable income "Annual household income (USD)"
compress
save "clean_data.dta", replace
```

## Topic Routing Table

Use `stata-cli skill <topic>` to read a specific reference.
Use `stata-cli skill --list` to see all topics with descriptions.

### Data Operations
| Topic | Key Commands |
|-------|-------------|
| `basics` | use, save, describe, browse, sysuse |
| `data-import-export` | import delimited/excel, export, ODBC |
| `data-management` | generate, replace, merge, reshape, collapse, egen |
| `variables-operators` | Variable types, missing values, if/in qualifiers |
| `string-functions` | substr(), regexm(), split, Unicode |
| `date-time-functions` | date(), clock(), %td/%tc formats |
| `mathematical-functions` | round(), log(), cond(), distributions |

### Statistics & Econometrics
| Topic | Key Commands |
|-------|-------------|
| `descriptive-statistics` | summarize, tabulate, correlate, tabstat |
| `linear-regression` | regress, vce(robust), margins, predict |
| `panel-data` | xtset, xtreg fe/re, Hausman test |
| `time-series` | tsset, ARIMA, VAR, unit root tests |
| `limited-dependent` | logit, probit, tobit, poisson, mlogit |
| `survey-data` | svyset, svy:, subpop(), complex design |
| `bootstrap-simulation` | bootstrap, simulate, Monte Carlo |
| `missing-data` | mi impute, mi estimate, FIML |
| `maximum-likelihood` | ml model, custom likelihood |
| `gmm-estimation` | gmm, moment conditions, J-test |

### Causal Inference
| Topic | Key Commands |
|-------|-------------|
| `treatment-effects` | teffects ra/ipw/aipw, ATE/ATT |
| `difference-in-differences` | DiD, event study, staggered adoption |
| `regression-discontinuity` | Sharp/fuzzy RD, bandwidth selection |
| `matching-methods` | PSM, nearest neighbor, kernel matching |
| `sample-selection` | heckman, exclusion restrictions |

### Advanced Methods
| Topic | Key Commands |
|-------|-------------|
| `survival-analysis` | stset, stcox, streg, Kaplan-Meier |
| `sem-factor-analysis` | sem, gsem, CFA, path analysis |
| `nonparametric-methods` | kdensity, qreg, npregress |
| `spatial-analysis` | spmatrix, spregress, Moran's I |
| `machine-learning` | lasso, elasticnet, cross-validation |

### Graphics
| Topic | Key Commands |
|-------|-------------|
| `graphics` | twoway, scatter, histogram, graph export |

### Programming
| Topic | Key Commands |
|-------|-------------|
| `programming-basics` | local, global, foreach, program define |
| `advanced-programming` | syntax, mata, tempfile/tempvar |
| `mata-introduction` | Mata basics, when to use Mata |
| `mata-programming` | Mata functions, structures, pointers |
| `mata-matrix-operations` | Matrix decompositions, st_matrix() |
| `mata-data-access` | st_data(), st_view(), st_store() |

### Output & Workflow
| Topic | Key Commands |
|-------|-------------|
| `tables-reporting` | putexcel, putdocx, LaTeX, collect |
| `workflow-best-practices` | Project structure, version control |
| `external-tools` | Python via python:, R, shell commands |

### Community Packages
| Topic | What It Does |
|-------|-------------|
| `reghdfe` | High-dimensional fixed effects OLS |
| `estout` | Publication-quality regression tables (esttab) |
| `outreg2` | Alternative table exporter (Word/Excel/TeX) |
| `asdoc` | One-command Word document creation |
| `coefplot` | Coefficient plots from stored estimates |
| `did` | Modern DiD estimators (csdid, did_multiplegt) |
| `event-study` | eventstudyinteract, eventdd |
| `rdrobust` | Robust RD estimation + optimal bandwidth |
| `psmatch2` | Propensity score matching |
| `synth` | Synthetic control method |
| `ivreg2` | Enhanced IV/2SLS with diagnostics |
| `xtabond2` | Dynamic panel GMM (Arellano-Bond) |
| `binsreg` | Binned scatter plots with CI |
| `data-manipulation` | gtools (fast collapse/egen), rangestat |
| `diagnostics` | bacondecomp, xttest3, heteroskedasticity |
| `graph-schemes` | grstyle, schemepack, plotplain |
| `nprobust` | Nonparametric kernel estimation |
| `winsor` | Winsorizing and trimming (winsor2) |
| `tabout` | Cross-tabulations to file |
| `package-management` | ssc install, net install, ado update |
