"""stata-cli skill — built-in Stata reference library."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SKILLS_DIR = Path(__file__).parent / "skills"

TOPIC_CATALOG: List[Tuple[str, str, str]] = [
    # (topic_name, category, description)
    # Data Operations
    ("basics", "Data Operations", "Getting started, use, save, describe, browse, sysuse"),
    ("data-import-export", "Data Operations", "import delimited/excel, export, ODBC, web data"),
    ("data-management", "Data Operations", "generate, replace, merge, reshape, collapse, egen, encode/decode"),
    ("variables-operators", "Data Operations", "Variable types, missing values, operators, if/in qualifiers"),
    ("string-functions", "Data Operations", "substr(), regexm(), split, strtrim(), Unicode"),
    ("date-time-functions", "Data Operations", "date(), clock(), %td/%tc formats, mdy(), business calendars"),
    ("mathematical-functions", "Data Operations", "round(), log(), exp(), cond(), distributions, random numbers"),
    # Statistics & Econometrics
    ("descriptive-statistics", "Statistics & Econometrics", "summarize, tabulate, correlate, tabstat, codebook"),
    ("linear-regression", "Statistics & Econometrics", "regress, vce(robust), vce(cluster), margins, predict, ivregress"),
    ("panel-data", "Statistics & Econometrics", "xtset, xtreg fe/re, Hausman test, dynamic panels"),
    ("time-series", "Statistics & Econometrics", "tsset, ARIMA, VAR, dfuller, pperron, irf, forecasting"),
    ("limited-dependent-variables", "Statistics & Econometrics", "logit, probit, tobit, poisson, nbreg, mlogit, ologit"),
    ("survey-data-analysis", "Statistics & Econometrics", "svyset, svy:, subpop(), complex survey design"),
    ("bootstrap-simulation", "Statistics & Econometrics", "bootstrap, simulate, permute, Monte Carlo"),
    ("missing-data-handling", "Statistics & Econometrics", "mi impute, mi estimate, FIML, misstable"),
    ("maximum-likelihood", "Statistics & Econometrics", "ml model, custom likelihood functions, ml init"),
    ("gmm-estimation", "Statistics & Econometrics", "gmm, moment conditions, estat overid, J-test"),
    # Causal Inference
    ("treatment-effects", "Causal Inference", "teffects ra/ipw/ipwra/aipw, ATE/ATT/ATET"),
    ("difference-in-differences", "Causal Inference", "DiD, parallel trends, event studies, staggered adoption"),
    ("regression-discontinuity", "Causal Inference", "Sharp/fuzzy RD, bandwidth selection, rdplot"),
    ("matching-methods", "Causal Inference", "PSM, nearest neighbor, kernel matching, teffects nnmatch"),
    ("sample-selection", "Causal Inference", "heckman, heckprobit, exclusion restrictions"),
    # Advanced Methods
    ("survival-analysis", "Advanced Methods", "stset, stcox, streg, Kaplan-Meier, parametric models"),
    ("sem-factor-analysis", "Advanced Methods", "sem, gsem, CFA, path analysis, alpha, reliability"),
    ("nonparametric-methods", "Advanced Methods", "kdensity, rank tests, qreg, npregress"),
    ("spatial-analysis", "Advanced Methods", "spmatrix, spregress, spatial weights, Moran's I"),
    ("machine-learning", "Advanced Methods", "lasso, elasticnet, cvlasso, cross-validation"),
    # Graphics
    ("graphics", "Graphics", "twoway, scatter, line, bar, histogram, graph combine, graph export"),
    # Programming
    ("programming-basics", "Programming", "local, global, foreach, forvalues, program define, syntax"),
    ("advanced-programming", "Programming", "syntax, mata, classes, tempfile/tempvar"),
    ("mata-introduction", "Programming", "Mata basics, when to use Mata vs ado, data types"),
    ("mata-programming", "Programming", "Mata functions, flow control, structures, pointers"),
    ("mata-matrix-operations", "Programming", "Matrix creation, decompositions, solvers, st_matrix()"),
    ("mata-data-access", "Programming", "st_data(), st_view(), st_store(), performance tips"),
    # Output & Workflow
    ("tables-reporting", "Output & Workflow", "putexcel, putdocx, putpdf, LaTeX, collect"),
    ("workflow-best-practices", "Output & Workflow", "Project structure, master do-files, version control"),
    ("external-tools-integration", "Output & Workflow", "Python via python:, R via rsource, shell, Git"),
    # Community Packages
    ("reghdfe", "Community Packages", "High-dimensional fixed effects OLS"),
    ("estout", "Community Packages", "Publication-quality regression tables (esttab/estout)"),
    ("outreg2", "Community Packages", "Alternative regression table exporter (Word/Excel/TeX)"),
    ("asdoc", "Community Packages", "One-command Word document creation for any Stata output"),
    ("tabout", "Community Packages", "Cross-tabulations and summary tables to file"),
    ("coefplot", "Community Packages", "Coefficient plots from stored estimates"),
    ("graph-schemes", "Community Packages", "grstyle, schemepack, plotplain — better graph themes"),
    ("did", "Community Packages", "Modern DiD: csdid, did_multiplegt, did_imputation"),
    ("event-study", "Community Packages", "eventstudyinteract, eventdd — event study estimators"),
    ("rdrobust", "Community Packages", "Robust RD estimation with optimal bandwidth"),
    ("psmatch2", "Community Packages", "Propensity score matching (nearest neighbor, kernel)"),
    ("synth", "Community Packages", "Synthetic control method (synth, synth_runner)"),
    ("ivreg2", "Community Packages", "Enhanced IV/2SLS with additional diagnostics"),
    ("xtabond2", "Community Packages", "Dynamic panel GMM (Arellano-Bond/Blundell-Bond)"),
    ("binsreg", "Community Packages", "Binned scatter plots with CI"),
    ("nprobust", "Community Packages", "Nonparametric kernel estimation and inference"),
    ("diagnostics", "Community Packages", "bacondecomp, xttest3, collinearity, heteroskedasticity"),
    ("winsor", "Community Packages", "Winsorizing and trimming: winsor2, winsor"),
    ("data-manipulation", "Community Packages", "gtools (fast collapse/egen), rangestat, egenmore"),
    ("package-management", "Community Packages", "ssc install, net install, ado update"),
]

# Build lookup: topic name -> (category, description)
_TOPIC_MAP: Dict[str, Tuple[str, str]] = {t[0]: (t[1], t[2]) for t in TOPIC_CATALOG}

# Short aliases for convenience
_ALIASES: Dict[str, str] = {
    "basics": "basics-getting-started",
    "regression": "linear-regression",
    "panel": "panel-data",
    "did": "difference-in-differences",
    "rd": "regression-discontinuity",
    "matching": "matching-methods",
    "ts": "time-series",
    "logit": "limited-dependent-variables",
    "probit": "limited-dependent-variables",
    "tobit": "limited-dependent-variables",
    "survival": "survival-analysis",
    "sem": "sem-factor-analysis",
    "ml": "maximum-likelihood",
    "gmm": "gmm-estimation",
    "survey": "survey-data-analysis",
    "bootstrap": "bootstrap-simulation",
    "mi": "missing-data-handling",
    "mata": "mata-introduction",
    "strings": "string-functions",
    "dates": "date-time-functions",
    "math": "mathematical-functions",
    "tables": "tables-reporting",
    "workflow": "workflow-best-practices",
    "external": "external-tools-integration",
    "nonparametric": "nonparametric-methods",
    "spatial": "spatial-analysis",
    "lasso": "machine-learning",
    "missing": "missing-data-handling",
    "heckman": "sample-selection",
    "selection": "sample-selection",
    "iv": "ivreg2",
    "gtools": "data-manipulation",
}


def _resolve_topic(name: str) -> Optional[str]:
    """Resolve a topic name (with alias support) to its file stem."""
    name = name.lower().strip()
    if name in _ALIASES:
        name = _ALIASES[name]
    # Try references/ then packages/
    for subdir in ("references", "packages"):
        path = SKILLS_DIR / subdir / f"{name}.md"
        if path.exists():
            return str(path)
    # Try partial match
    for subdir in ("references", "packages"):
        d = SKILLS_DIR / subdir
        if d.is_dir():
            for f in d.iterdir():
                if f.suffix == ".md" and name in f.stem:
                    return str(f)
    return None


def get_overview() -> str:
    """Return the skill overview content."""
    overview_path = SKILLS_DIR / "overview.md"
    if overview_path.exists():
        return overview_path.read_text(encoding="utf-8")
    return "Skill overview not found."


def get_topic(name: str) -> Optional[str]:
    """Return content of a specific topic, or None if not found."""
    path = _resolve_topic(name)
    if path:
        return Path(path).read_text(encoding="utf-8")
    return None


def list_topics() -> str:
    """Return a formatted topic listing grouped by category."""
    lines = []
    current_cat = ""
    for topic_name, category, description in TOPIC_CATALOG:
        if category != current_cat:
            if current_cat:
                lines.append("")
            lines.append(category)
            current_cat = category
        lines.append(f"  {topic_name:<30s} {description}")
    return "\n".join(lines)


def get_all_topic_names() -> List[str]:
    """Return list of all valid topic names."""
    return [t[0] for t in TOPIC_CATALOG]
