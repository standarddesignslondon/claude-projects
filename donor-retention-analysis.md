# Donor Retention & Cross-Sell Analysis
### SQL Design Guide for Power BI

---

## Overview

This document covers the SQL design for analysing donor retention and cross-sell behaviour across fundraising appeals. The goal is to understand:

- How many donors are retained period-on-period within an appeal category
- How many lapse (stop giving)
- How many cross-sell into a new appeal category (either within the same team or across teams)
- Whether a donor is **cold** (first time giving to a category) or **warm** (has given before)

---

## Donor Status Taxonomy

Each donor × category × period combination gets one of four statuses:

| Status | Definition |
|---|---|
| **New Acquisition** | First time giving to this category AND first time giving to the organisation |
| **Cross-sell** | First time giving to this category, but an existing donor to the organisation |
| **Retained** | Has given to this category before AND gave in the immediately preceding period |
| **Reactivated** | Has given to this category before, skipped at least one period, now back |
| **Lapsed** | Gave in the previous period, absent in the current period |

**Cold vs Warm** (event-level warmth):
- **Cold** = `New Acquisition` or `Cross-sell` — first time to this category
- **Warm** = `Retained` or `Reactivated` — has given to this category before

---

## Schema

```sql
CREATE TABLE transactions (
    transaction_id   INT            PRIMARY KEY,
    person_id        INT            NOT NULL,
    amount           DECIMAL(10,2)  NOT NULL,
    transaction_date DATE           NOT NULL,
    appeal_id        INT            NOT NULL
);

CREATE TABLE appeals (
    appeal_id        INT            PRIMARY KEY,
    appeal_name      VARCHAR(200),
    appeal_category  VARCHAR(100)   NOT NULL,  -- the "what" dimension
    appeal_team      VARCHAR(100)   NOT NULL,  -- the "who" dimension
    period_sort      INT            NOT NULL,  -- numeric ordering (1, 2, 3…)
    period_label     VARCHAR(50)               -- e.g. "2023", "Spring 2024"
);
```

### Key design decisions

- **`appeal_category`** is the primary analysis dimension — cold/warm status and cross-sell are measured relative to category.
- **`appeal_team`** is an attribute for slicing. One team can own multiple categories.
- **`period_sort`** (integer) drives the "previous period" join. You define what a period means (annual, per campaign run, etc.) by assigning values. Period 2 always follows period 1 for the same category.
- **`period_label`** is the human-readable version shown in Power BI.

---

## Core Analysis SQL

Build as a series of CTEs. Each layer adds a classification on top of the previous.

```sql
-- ================================================================
-- LAYER 1: Anchor points
-- ================================================================
WITH first_category_donation AS (
    -- Determines cold/warm relative to appeal_category
    SELECT
        t.person_id,
        a.appeal_category,
        MIN(t.transaction_date) AS first_category_date
    FROM transactions t
    JOIN appeals a ON t.appeal_id = a.appeal_id
    GROUP BY t.person_id, a.appeal_category
),

first_org_donation AS (
    -- Determines whether someone is a new or existing donor to the organisation
    SELECT
        person_id,
        MIN(transaction_date) AS first_org_date
    FROM transactions
    GROUP BY person_id
),

-- ================================================================
-- LAYER 2: Aggregate to donor × category × period grain
-- ================================================================
donor_category_period AS (
    SELECT
        t.person_id,
        a.appeal_category,
        a.appeal_team,           -- carried as attribute for Power BI slicing
        a.period_sort,
        a.period_label,
        SUM(t.amount)            AS total_amount,
        COUNT(t.transaction_id)  AS gift_count,
        MIN(t.transaction_date)  AS first_gift_date
    FROM transactions t
    JOIN appeals a ON t.appeal_id = a.appeal_id
    GROUP BY t.person_id, a.appeal_category, a.appeal_team, a.period_sort, a.period_label
),

-- ================================================================
-- LAYER 3: Classify each row
-- ================================================================
classified AS (
    SELECT
        dep.person_id,
        dep.appeal_category,
        dep.appeal_team,
        dep.period_sort,
        dep.period_label,
        dep.total_amount,
        dep.gift_count,
        dep.first_gift_date,

        -- Cold/warm TO THIS CATEGORY
        CASE
            WHEN dep.first_gift_date = fcd.first_category_date
            THEN 'Cold'   -- first time ever giving to this category
            ELSE 'Warm'   -- has given before (may have lapsed in between)
        END AS category_warmth,

        -- New/existing TO THE ORGANISATION
        CASE
            WHEN dep.first_gift_date = fod.first_org_date
            THEN 'New Donor'
            ELSE 'Existing Donor'
        END AS org_status,

        -- Retained from the IMMEDIATELY preceding period?
        -- (warm but skipped a period = reactivated, not retained)
        CASE WHEN prev.person_id IS NOT NULL THEN 1 ELSE 0 END
            AS retained_from_prev,

        prev.total_amount AS prev_period_amount

    FROM donor_category_period dep
    JOIN  first_category_donation fcd ON dep.person_id       = fcd.person_id
                                      AND dep.appeal_category = fcd.appeal_category
    JOIN  first_org_donation      fod ON dep.person_id       = fod.person_id
    LEFT JOIN donor_category_period prev
           ON dep.person_id       = prev.person_id
          AND dep.appeal_category = prev.appeal_category
          AND dep.period_sort     = prev.period_sort + 1   -- immediately prior period only
),

-- ================================================================
-- LAYER 4: Single status label per row
-- ================================================================
donor_status AS (
    SELECT
        *,
        CASE
            WHEN category_warmth = 'Cold' AND org_status = 'New Donor'      THEN 'New Acquisition'
            WHEN category_warmth = 'Cold' AND org_status = 'Existing Donor' THEN 'Cross-sell'
            WHEN category_warmth = 'Warm' AND retained_from_prev = 1        THEN 'Retained'
            WHEN category_warmth = 'Warm' AND retained_from_prev = 0        THEN 'Reactivated'
        END AS donor_status
    FROM classified
)
```

---

## Output Tables for Power BI

### Table 1 — Detail
*Grain: one row per donor × appeal category × period*

Use this as your most flexible table. Power BI can aggregate it any way needed.

```sql
SELECT
    ds.person_id,
    ds.appeal_category,
    ds.appeal_team,
    ds.period_sort,
    ds.period_label,
    ds.total_amount,
    ds.gift_count,
    ds.category_warmth,    -- Cold / Warm
    ds.org_status,         -- New Donor / Existing Donor
    ds.donor_status,       -- New Acquisition / Cross-sell / Retained / Reactivated
    ds.retained_from_prev,
    ds.prev_period_amount
FROM donor_status ds;
```

---

### Table 2 — Retention Summary
*Grain: one row per appeal category × period*

Pre-aggregated for headline charts and KPI cards.

```sql
SELECT
    ds.appeal_category,
    ds.appeal_team,
    ds.period_label,
    ds.period_sort,

    COUNT(DISTINCT CASE WHEN ds.donor_status = 'New Acquisition' THEN ds.person_id END) AS new_acquisitions,
    COUNT(DISTINCT CASE WHEN ds.donor_status = 'Cross-sell'      THEN ds.person_id END) AS cross_sells,
    COUNT(DISTINCT CASE WHEN ds.donor_status = 'Retained'        THEN ds.person_id END) AS retained,
    COUNT(DISTINCT CASE WHEN ds.donor_status = 'Reactivated'     THEN ds.person_id END) AS reactivated,
    COUNT(DISTINCT ds.person_id)                                                          AS total_active,

    COUNT(DISTINCT lapsed.person_id) AS lapsed,

    -- Retention rate: of last period's donors, what % came back this period?
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN ds.donor_status = 'Retained' THEN ds.person_id END)
              / NULLIF(
                    COUNT(DISTINCT lapsed.person_id)
                  + COUNT(DISTINCT CASE WHEN ds.donor_status = 'Retained' THEN ds.person_id END)
                , 0)
    , 1) AS retention_rate_pct,

    SUM(CASE WHEN ds.donor_status IN ('New Acquisition','Cross-sell') THEN ds.total_amount ELSE 0 END) AS revenue_new,
    SUM(CASE WHEN ds.donor_status IN ('Retained','Reactivated')       THEN ds.total_amount ELSE 0 END) AS revenue_returning,
    SUM(ds.total_amount)                                                                                AS revenue_total

FROM donor_status ds
LEFT JOIN (
    -- Lapsed: gave in period P, absent in period P+1
    SELECT
        prev_dep.person_id,
        prev_dep.appeal_category,
        prev_dep.period_sort + 1 AS absent_in_period_sort
    FROM donor_category_period prev_dep
    WHERE NOT EXISTS (
        SELECT 1 FROM donor_category_period curr_dep
        WHERE curr_dep.person_id       = prev_dep.person_id
          AND curr_dep.appeal_category = prev_dep.appeal_category
          AND curr_dep.period_sort     = prev_dep.period_sort + 1
    )
) lapsed
    ON ds.person_id       = lapsed.person_id
   AND ds.appeal_category = lapsed.appeal_category
   AND ds.period_sort     = lapsed.absent_in_period_sort

GROUP BY ds.appeal_category, ds.appeal_team, ds.period_label, ds.period_sort;
```

---

### Table 3 — Donor Flow
*Grain: from-category × from-period → to-category × to-period*

Used for Sankey diagrams and flow/waterfall visualisations. Shows where donors go between consecutive periods.

```sql
SELECT
    from_dep.appeal_category          AS from_category,
    from_dep.appeal_team              AS from_team,
    from_dep.period_label             AS from_period,
    from_dep.period_sort              AS from_period_sort,

    COALESCE(to_dep.appeal_category, 'Lapsed') AS to_category,
    COALESCE(to_dep.appeal_team,     'Lapsed') AS to_team,
    to_dep.period_label                        AS to_period,

    COUNT(DISTINCT from_dep.person_id) AS donor_count,
    SUM(to_dep.total_amount)           AS to_period_revenue

FROM donor_category_period from_dep
LEFT JOIN donor_category_period to_dep
       ON from_dep.person_id   = to_dep.person_id
      AND to_dep.period_sort   = from_dep.period_sort + 1  -- any category in the next period

GROUP BY
    from_dep.appeal_category, from_dep.appeal_team,
    from_dep.period_label,    from_dep.period_sort,
    to_dep.appeal_category,   to_dep.appeal_team,
    to_dep.period_label;
```

> **Note:** A donor who gives to both Category A and Category B in the next period will appear in two rows in this table — one for each destination. This is correct for a flow/Sankey visual. Be careful not to double-count them in summary totals.

---

## Power BI Visualisations

| Chart type | Source table | What it shows |
|---|---|---|
| **Stacked bar** by period | Retention Summary | New Acquisition / Cross-sell / Retained / Reactivated / Lapsed stacked — volume and composition over time |
| **Line chart** | Retention Summary | `retention_rate_pct` over time per category — headline KPI |
| **Waterfall** | Retention Summary | Start with last period's donors, add new + reactivated, subtract lapsed = this period's total |
| **Sankey** (custom visual) | Donor Flow | Flow between categories across periods — visualises cross-sell routes |
| **Cohort matrix** (matrix visual) | Detail | Rows = first period, columns = periods since first gift, values = % still active — classic retention heatmap |
| **KPI cards** | Retention Summary | Total active, retention rate, revenue by status |

---

## Power BI Slicing by Team vs Category

Because `appeal_team` is an attribute on every row in all three tables, you get both analysis levels without extra SQL:

| Power BI setup | What you see |
|---|---|
| No team filter | All categories across all teams |
| Filter by `appeal_team` | Retention/cross-sell within one team's categories only |
| Swap `appeal_category` for `appeal_team` in visual | Roll up to team-level view |

**Cross-team vs within-team cross-sell** — add this as a calculated column in Power BI on the Flow table:

```
Cross Team = IF([from_team] <> [to_team], "Across Teams", "Within Team")
```

This lets you split the cross-sell metric to show whether donors are moving between teams or just between categories within the same team.

---

*Document compiled from design session — February 2026*
