# User Matches Analytics - Metrics Documentation

---

# STREAMLIT DASHBOARD REQUIREMENTS

## Design Principles

1. **Zero Loading Time** - All data pre-fetched in JSON, instant rendering
2. **Dark/Light Mode** - Full support for both themes with proper contrast
3. **Sticky Header** - Filters always visible at top while scrolling
4. **Tab-based Navigation** - Each metric in its own tab for clean UX

---

## STICKY HEADER (Always visible at top)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│  📅 SELECT DATES:                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │ [✓] Dec 28  [✓] Dec 27  [ ] Dec 26  [ ] Dec 25  ... [Select All] [Clear All]      │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  👤 GENDER:  [● Both]  [○ Male Only]  [○ Female Only]                                   │
│                                                                                         │
│  🏷️ TIER:    [● All]   [○ Tier 1]    [○ Tier 2]    [○ Tier 3]                           │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  🔄 REFRESH DATA    │    Last Refreshed: Dec 28, 2025 11:45 AM IST              │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## REFRESH BUTTON BEHAVIOR

When clicked, show **FULL SCREEN LOADING** with step-by-step progress:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           🔄 REFRESHING DATA...                                         │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │ ████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  45%           │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ✅ Step 1/4: Deleting old cached JSON files...                                         │
│  ✅ Step 2/4: Fetching user_matches (Batch 45/136 - 4500 rows)...                       │
│  🔄 Step 3/4: Fetching user_metadata (Batch 12/50 - 1200 rows)...                       │
│  ⏳ Step 4/4: Processing & generating analytics...                                      │
│                                                                                         │
│  Elapsed: 45s | ETA: ~55s                                                               │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Refresh Steps (in order):

| Step | Action | Details |
|------|--------|---------|
| 1 | Delete old JSONs | Clear `personal-scripts/metrics/data/` folder |
| 2 | Fetch `user_matches` | 100 rows/batch, 0.2s gap, show progress |
| 3 | Fetch `user_metadata` | 100 rows/batch, 0.2s gap, show progress |
| 4 | Process & Save | Generate all metrics JSON, save to `data/` |

**After refresh complete:** Auto-load new data, show dashboard with updated timestamp.

---

## METRIC TABS (8 tabs, click to view)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│  [ 1. Funnel ] [ 2. Hours ] [ 3. Time ] [ 4. Rank ] [ 5. Tier ] [ 6. Dates ] [ 7. KM ]  |
|   [ 8. Ghost ]                                                                          |
│                                                                                         │
│  ═══════════════════════════════════════════════════════════════════════════════════    │
│                                                                                         │
│                         << SELECTED TAB CONTENT HERE >>                                 │
│                                                                                         │
│                      Full width, scrollable, beautiful charts                           │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Tab Names:
1. **Funnel** - Core Funnel (METRIC 1)
2. **Hours** - Activity Hour Distribution (METRIC 2)
3. **Time** - Time to Decision (METRIC 3)
4. **Rank** - Rank Performance (METRIC 4)
5. **Tier** - Tier Analysis (METRIC 5)
6. **Dates** - Date-wise Engagement (METRIC 6)
7. **KM** - Know More Distribution (METRIC 7)
8. **Ghost** - Ghost & Pass-Only Users (METRIC 8)

---

## DARK/LIGHT MODE SUPPORT

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| Background | `#FFFFFF` | `#0E1117` |
| Text | `#31333F` | `#FAFAFA` |
| Card Background | `#F0F2F6` | `#262730` |
| Primary Accent | `#FF4B4B` | `#FF4B4B` |
| Success | `#21C354` | `#21C354` |
| Warning | `#FACA2B` | `#FACA2B` |
| Chart Grid | `#E0E0E0` | `#3D3D3D` |
| Tab Active | `#FF4B4B` | `#FF4B4B` |
| Tab Inactive | `#808495` | `#808495` |

**Streamlit auto-detects system preference, but add toggle option.**

---

## DATA FOLDER STRUCTURE

```
personal-scripts/metrics/
├── data/                          ← JSON files (refreshed by button)
│   ├── user_matches.json          ← Raw fetched data
│   ├── user_metadata.json         ← Raw fetched data
│   ├── analytics_processed.json   ← All computed metrics
│   └── last_refresh.txt           ← Timestamp of last refresh
├── utils/                         ← Old folder (can be deprecated)
├── docs/
│   └── analytics-metrics.md       ← This documentation
├── fetch-user-matches.js          ← Standalone fetch script
├── fetch-user-metadata.js         ← Standalone fetch script
├── generate-analytics.js          ← Process & compute all metrics
└── dashboard.py                   ← Streamlit dashboard
```

---

## KEY PERFORMANCE REQUIREMENTS

| Requirement | Target |
|-------------|--------|
| Initial Load | < 1 second (JSON already cached) |
| Filter Change | < 100ms (in-memory filtering) |
| Tab Switch | < 50ms (instant, data ready) |
| Refresh Full Data | ~2-3 min (network dependent) |

---

## Filter Logic:
- **Dates**: Filter `user_matches` rows by `created_at IN (selected_dates)`
- **Gender**: Join with `user_metadata`, filter by `gender = 'male'/'female'` on `current_user_id`
- **Tier**: Join with `user_metadata`, filter by `professional_tier = 1/2/3` on `current_user_id`

**All filters apply instantly to all 8 tabs.**

---

## METRIC 1: Core Funnel (User-Level)

### Definition

**All counts are UNIQUE `current_user_id` counts, NOT row counts.**

```
Unique Users with Matches (unique current_user_ids in selected dates)
    ↓
Unique Users who Viewed (users with at least 1 is_viewed = true)
    ↓
Unique Users who Engaged (users with at least 1 know_more_count > 0)
    ↓
Unique Users who Decided (users with at least 1 is_liked IS NOT NULL)
    ├── Users who Liked at least 1
    ├── Users who Disliked at least 1
    └── Users who Passed at least 1
```

**Note:** One user can be in multiple categories (liked 1, disliked another). So Liked + Disliked + Passed won't equal Decided.

### Percentages

Two types shown for each step:

| Type | Formula | Example |
|------|---------|---------|
| **Absolute %** | (Current Step / Users with Matches) × 100 | "65% of all users viewed at least 1 match" |
| **Relative %** | (Current Step / Previous Step) × 100 | "45% of users who viewed also engaged" |

### Display Format

```
                         ALL              MALE             FEMALE
                         Count  Abs%  Rel%   Count Abs% Rel%   Count Abs% Rel%
Users with Matches:       500   100%   -      280  100%  -      220  100%  -
Users who Viewed:         325    65%  65%     168   60% 60%     157   71% 71%
Users who Engaged:        146    29%  45%      73   26% 43%      73   33% 46%
Users who Decided:        120    24%  82%      58   21% 79%      62   28% 85%
  - Liked at least 1:      89    18%  74%      42   15% 72%      47   21% 76%
  - Disliked at least 1:   67    13%  56%      35   13% 60%      32   15% 52%
  - Passed at least 1:     45     9%  38%      22    8% 38%      23   10% 37%
Users No Action Yet:      205    41%   -      110   39%  -       95   43%  -
```

### Fields Used
- `current_user_id` (for unique user counting)
- `is_viewed` (boolean)
- `know_more_count` (integer)
- `is_liked` (enum: 'liked', 'disliked', 'passed', null)

### Status: ✅ VERIFIED

---

## METRIC 2: Activity Hour Distribution

### Definition

Three separate hour distributions, all showing **unique user counts** per hour (0-23).
**Sorted by count (highest first), not by hour.**

#### 2a. View Hour Distribution
- Extract hour from `viewed_at`
- Count unique `current_user_id` per hour

#### 2b. Like Hour Distribution
- Extract hour from `liked_at` WHERE `is_liked = 'liked'`
- Count unique `current_user_id` per hour

#### 2c. Dislike/Pass Hour Distribution
- Extract hour from `liked_at` WHERE `is_liked IN ('disliked', 'passed')`
- Count unique `current_user_id` per hour

### Display Format

```
VIEW HOURS (When users open and view matches)
──────────────────────────────────────────────────────────────────
Hour 21 (9 PM):   ████████████████████ 234 users (15.2%)
Hour 20 (8 PM):   ██████████████████   212 users (13.8%)
Hour 22 (10 PM):  ███████████████      189 users (12.3%)
Hour 19 (7 PM):   ████████████         156 users (10.1%)
...
Hour 4 (4 AM):    █                     12 users (0.8%)

📊 Summary: Peak at 9 PM | Top 3 hrs (8-10 PM): 41.3% | Dead hrs: 2-6 AM

──────────────────────────────────────────────────────────────────
LIKE HOURS (When users like someone)
──────────────────────────────────────────────────────────────────
Hour 22 (10 PM):  ████████████████████  89 users (18.5%)
Hour 21 (9 PM):   █████████████████     78 users (16.2%)
...

📊 Summary: Peak at 10 PM | Top 3 hrs: 48.2% | Dead hrs: 3-7 AM

──────────────────────────────────────────────────────────────────
DISLIKE/PASS HOURS (When users reject)
──────────────────────────────────────────────────────────────────
Hour 21 (9 PM):   ████████████████████ 112 users (17.8%)
Hour 20 (8 PM):   ██████████████████    98 users (15.6%)
...

📊 Summary: Peak at 9 PM | Top 3 hrs: 45.6% | Dead hrs: 2-6 AM
```

### Summary Stats (for each distribution):
- **Peak Hour**: Hour with highest user count
- **Top 3 Hours**: Combined percentage of these hours
- **Dead Hours**: Hours with < 1% activity

### Fields Used
- `viewed_at` (timestamp, already IST +05:30)
- `liked_at` (timestamp)
- `is_liked` (enum: 'liked', 'disliked', 'passed')
- `current_user_id` (for unique counting)

### Status: ✅ VERIFIED

---

## METRIC 3: Time to Decision (Buckets)

### Definition

Calculate time difference: `liked_at - viewed_at` for all rows where user took an action.

Separate distributions for LIKES vs DISLIKES/PASSES.

### Buckets

| Bucket | Range | Meaning |
|--------|-------|---------|
| Instant | < 1 min | Snap decision |
| Quick | 1-5 min | Fast decision |
| Thinking | 5-30 min | Took time to consider |
| Later | 30 min - 2 hr | Came back later |
| Much Later | 2-6 hr | Different session likely |
| Next Session | 6-24 hr | Next day/session |
| Days Later | 24 hr+ | Much later return |

### Display Format

```
TIME TO DECISION (How long after viewing did user decide?)
══════════════════════════════════════════════════════════════════

LIKES:
──────────────────────────────────────────────────────────────────
Instant (<1 min):    ████████████████████  89 users (35.2%)
Quick (1-5 min):     ██████████████        67 users (26.5%)
Thinking (5-30 min): ████████              45 users (17.8%)
Later (30min-2hr):   ████                  23 users (9.1%)
Much Later (2-6hr):  ██                    15 users (5.9%)
Next Session (6-24h):█                      8 users (3.2%)
Days Later (24h+):   █                      6 users (2.4%)

📊 Avg time to like: 12.3 min | Median: 3.2 min

══════════════════════════════════════════════════════════════════

DISLIKES/PASSES:
──────────────────────────────────────────────────────────────────
Instant (<1 min):    ████████████████████ 145 users (52.3%)
Quick (1-5 min):     ██████████            78 users (28.1%)
Thinking (5-30 min): ████                  34 users (12.3%)
Later (30min-2hr):   ██                    12 users (4.3%)
Much Later (2-6hr):  █                      5 users (1.8%)
Next Session (6-24h):                       2 users (0.7%)
Days Later (24h+):                          1 users (0.4%)

📊 Avg time to dislike: 4.5 min | Median: 0.8 min
```

### Insight
- If LIKES take longer than DISLIKES → Users think more before liking (good sign)
- If DISLIKES are instant → Quick rejections based on first impression

### Fields Used
- `viewed_at` (timestamp)
- `liked_at` (timestamp)
- `is_liked` (to separate likes vs dislikes/passes)
- `current_user_id` (unique counting)

### Status: ✅ VERIFIED

---

## METRIC 4: Rank Performance Table

### Definition

Group all matches by `rank` (1-9), calculate metrics for each rank.

**All counts are unique `current_user_id` counts per rank.**

### Columns

| Column | Calculation |
|--------|-------------|
| Rank | 1, 2, 3... 9 |
| Total Users | Unique `current_user_id` with this rank |
| Viewed | Users who viewed at least 1 match at this rank |
| View% | Viewed / Total × 100 |
| KM Avg | Average `know_more_count` for this rank |
| Liked | Users who liked at least 1 at this rank |
| Like% | Liked / Viewed × 100 |
| Disliked | Users who disliked at least 1 at this rank |
| Dislike% | Disliked / Viewed × 100 |
| Passed | Users who passed at least 1 at this rank |
| Pass% | Passed / Viewed × 100 |

### Display Format

```
RANK PERFORMANCE (Click column header to sort)
═══════════════════════════════════════════════════════════════════════════════════════════
Rank │ Total │ Viewed │ View% │ KM Avg │ Liked │ Like% │ Disliked │ Dis% │ Passed │ Pass%
─────┼───────┼────────┼───────┼────────┼───────┼───────┼──────────┼──────┼────────┼───────
  1  │  500  │  425   │ 85.0% │  2.3   │  180  │ 42.4% │    120   │28.2% │   65   │ 15.3%
  2  │  500  │  390   │ 78.0% │  1.9   │  156  │ 40.0% │    134   │34.4% │   58   │ 14.9%
  3  │  500  │  360   │ 72.0% │  1.6   │  130  │ 36.1% │    145   │40.3% │   52   │ 14.4%
  4  │  500  │  335   │ 67.0% │  1.4   │  115  │ 34.3% │    150   │44.8% │   48   │ 14.3%
  5  │  500  │  310   │ 62.0% │  1.2   │   98  │ 31.6% │    148   │47.7% │   45   │ 14.5%
  6  │  500  │  285   │ 57.0% │  1.0   │   82  │ 28.8% │    142   │49.8% │   42   │ 14.7%
  7  │  500  │  265   │ 53.0% │  0.9   │   70  │ 26.4% │    138   │52.1% │   40   │ 15.1%
  8  │  500  │  245   │ 49.0% │  0.8   │   62  │ 25.3% │    130   │53.1% │   38   │ 15.5%
  9  │  500  │  225   │ 45.0% │  0.8   │   58  │ 25.8% │    112   │49.8% │   35   │ 15.6%
═══════════════════════════════════════════════════════════════════════════════════════════

📊 Insight: Rank 1 has 85% view rate vs Rank 9 at 45% | Like rate drops from 42% to 26%
```

### Sortable
Click any column header to sort ascending/descending.

### Fields Used
- `rank` (integer 1-9)
- `current_user_id` (for unique counting)
- `is_viewed` (boolean)
- `know_more_count` (integer)
- `is_liked` (enum)

### Status: ✅ VERIFIED

---

## METRIC 5: Tier Analysis

### Terminology

| Term | Field | Meaning |
|------|-------|---------|
| **Viewer** | `current_user_id` | User who is viewing matches (opened app) |
| **Candidate** | `matched_user_id` | Profile being shown to the viewer |
| **Viewer Tier** | `user_metadata.professional_tier` of `current_user_id` | Tier of the person viewing |
| **Candidate Tier** | `user_metadata.professional_tier` of `matched_user_id` | Tier of the profile shown |

---

### 5a. Viewer Tier Performance

"How do users of each tier BEHAVE when viewing matches?"

```
VIEWER TIER PERFORMANCE (How each tier behaves as viewers)
═══════════════════════════════════════════════════════════════════════════════════════════
Viewer │ Total │ Viewed │ View% │ KM Avg │ Liked │ Like% │ Disliked │ Dis% │ Passed │ Pass%
Tier   │       │        │       │        │       │       │          │      │        │
───────┼───────┼────────┼───────┼────────┼───────┼───────┼──────────┼──────┼────────┼───────
  1    │  150  │  135   │ 90.0% │  2.8   │   68  │ 50.4% │     45   │33.3% │   15   │ 11.1%
  2    │  200  │  160   │ 80.0% │  2.1   │   72  │ 45.0% │     58   │36.3% │   22   │ 13.8%
  3    │  150  │  105   │ 70.0% │  1.5   │   42  │ 40.0% │     45   │42.9% │   12   │ 11.4%
═══════════════════════════════════════════════════════════════════════════════════════════

📊 Insight: Tier 1 viewers are most engaged (90% view, 50% like rate)
```

---

### 5b. Candidate Tier Performance

"How do profiles of each tier PERFORM when shown to others?"

```
CANDIDATE TIER PERFORMANCE (How each tier performs as profiles)
═══════════════════════════════════════════════════════════════════════════════════════════
Candidate│ Times │ Times  │ View% │ KM Avg │ Times │ Like% │ Times    │ Dis% │ Times  │ Pass%
Tier     │ Shown │ Viewed │       │        │ Liked │       │ Disliked │      │ Passed │
─────────┼───────┼────────┼───────┼────────┼───────┼───────┼──────────┼──────┼────────┼───────
   1     │  180  │  162   │ 90.0% │  2.9   │   85  │ 52.5% │     50   │30.9% │   18   │ 11.1%
   2     │  220  │  176   │ 80.0% │  2.0   │   79  │ 44.9% │     65   │36.9% │   25   │ 14.2%
   3     │  100  │   70   │ 70.0% │  1.4   │   28  │ 40.0% │     30   │42.9% │   10   │ 14.3%
═══════════════════════════════════════════════════════════════════════════════════════════

📊 Insight: Tier 1 profiles get liked 52.5% of time vs Tier 3 at 40%
```

---

### 5c. Tier Cross Matrix (3×3)

"How does Viewer Tier × Candidate Tier affect behavior?"

```
TIER CROSS-PERFORMANCE MATRIX
══════════════════════════════════════════════════════════════════════════════════════

                        CANDIDATE TIER (Profile being shown)
                        ┌─────────────────┬─────────────────┬─────────────────┐
                        │     Tier 1      │     Tier 2      │     Tier 3      │
════════════════════════════════════════════════════════════════════════════════════
VIEWER     │  Tier 1    │  V: 92% L: 55%  │  V: 85% L: 42%  │  V: 78% L: 28%  │
TIER       │            │  KM: 3.2  n=60  │  KM: 2.1  n=55  │  KM: 1.4  n=35  │
(Person    ├────────────┼─────────────────┼─────────────────┼─────────────────┤
viewing)   │  Tier 2    │  V: 88% L: 48%  │  V: 80% L: 38%  │  V: 70% L: 25%  │
           │            │  KM: 2.8  n=70  │  KM: 1.9  n=80  │  KM: 1.2  n=50  │
           ├────────────┼─────────────────┼─────────────────┼─────────────────┤
           │  Tier 3    │  V: 82% L: 42%  │  V: 72% L: 32%  │  V: 65% L: 22%  │
           │            │  KM: 2.2  n=50  │  KM: 1.5  n=85  │  KM: 0.9  n=15  │
════════════════════════════════════════════════════════════════════════════════════

V = View%  |  L = Like%  |  KM = Know More Avg  |  n = Match count
```

**Key Insights:**
- Diagonal (same tier): How do same-tier matches perform?
- Off-diagonal: Cross-tier attraction patterns
- "Tier 1 viewers like Tier 1 candidates 55%, but Tier 3 candidates only 28%"

---

### 5d. Expandable Rank Breakdown (Click to expand any cell)

Clicking on any cell in 3×3 matrix shows rank distribution:

```
▼ TIER 1 VIEWER → TIER 2 CANDIDATE (Click to collapse)
──────────────────────────────────────────────────────────────────
Rank │ Count │ Viewed │ View% │ KM Avg │ Liked │ Like% │ Dis% │ Pass%
─────┼───────┼────────┼───────┼────────┼───────┼───────┼──────┼──────
  1  │   8   │   8    │  100% │  3.2   │   5   │ 62.5% │ 25.0%│ 12.5%
  2  │   7   │   6    │ 85.7% │  2.5   │   3   │ 50.0% │ 33.3%│ 16.7%
  3  │   6   │   5    │ 83.3% │  2.1   │   2   │ 40.0% │ 40.0%│ 20.0%
  4  │   8   │   6    │ 75.0% │  1.8   │   2   │ 33.3% │ 50.0%│ 16.7%
  5  │   7   │   5    │ 71.4% │  1.5   │   2   │ 40.0% │ 40.0%│ 20.0%
  6  │   6   │   4    │ 66.7% │  1.2   │   1   │ 25.0% │ 50.0%│ 25.0%
  7  │   5   │   3    │ 60.0% │  1.0   │   1   │ 33.3% │ 33.3%│ 33.3%
  8  │   4   │   2    │ 50.0% │  0.8   │   1   │ 50.0% │ 50.0%│  0.0%
  9  │   4   │   2    │ 50.0% │  0.5   │   0   │  0.0% │ 50.0%│ 50.0%
──────────────────────────────────────────────────────────────────
📊 Rank 1-3 have 51% like rate vs Rank 7-9 at 28%
```

---

### Fields Used
- `current_user_id` → join `user_metadata` for Viewer Tier
- `matched_user_id` → join `user_metadata` for Candidate Tier
- `rank`, `is_viewed`, `know_more_count`, `is_liked`

### Data Requirement
Need to fetch `user_metadata` with `user_id`, `gender`, `professional_tier` for BOTH current and matched users.

### Status: ✅ VERIFIED

---

## METRIC 6: Date-wise User Engagement

### Definition

Track unique user engagement across selected dates. **Auto-adjusts based on number of dates selected.**

---

### 6a. Engagement Timeline Graph

X-axis: Selected dates (`created_at`)
Y-axis: Unique user counts

Three lines:
- Users with matches (got matches on that date)
- Users who viewed (viewed at least 1 on that date)
- Users who liked (liked at least 1 on that date)

```
DATE-WISE ENGAGEMENT TREND
═══════════════════════════════════════════════════════════════════════════════

       500 │                                    ●
           │                              ●           ●
       400 │        ●       ●       ●                       ●
           │  ●                                                   ●
       300 │
           │
       200 │  ○       ○       ○       ○       ○       ○       ○       ○
           │
       100 │  △       △       △       △       △       △       △       △
           │
         0 └────────────────────────────────────────────────────────────────
             Dec 17  Dec 19  Dec 21  Dec 23  Dec 25  Dec 26  Dec 27  Dec 28

● = Users with matches   ○ = Users who viewed   △ = Users who liked
```

---

### 6b. User Retention Across Selected Dates

"How many users engaged on multiple dates?"

**Dynamic buckets based on N selected dates:**

```
USER RETENTION PATTERN (for selected dates: Dec 26, 27, 28)
══════════════════════════════════════════════════════════════════════════════

Engaged on 1 date only:    ████████████████████ 234 users (46.8%)
Engaged on 2 dates:        ██████████████       156 users (31.2%)
Engaged on all 3 dates:    ████████              89 users (17.8%)
No engagement:             ██                    21 users (4.2%)

──────────────────────────────────────────────────────────────────────────────
SPECIAL SEGMENTS:
──────────────────────────────────────────────────────────────────────────────
Loyal Users (all dates):        89 users  - Engaged every selected date
Churned (first date only):      67 users  - Engaged first date, not after
Late Adopters (not first):      45 users  - Skipped first date, engaged later
One-time (any single date):    234 users  - Only engaged on 1 date total
══════════════════════════════════════════════════════════════════════════════

If 5 dates selected → buckets become: 1 date, 2 dates, 3 dates, 4 dates, all 5 dates
```

---

### 6c. Date × Date Overlap Matrix

"Which dates share users?"

**N×N matrix where N = number of selected dates:**

```
USER OVERLAP MATRIX (Users who engaged on both dates)
══════════════════════════════════════════════════════════════════════════════

              │  Dec 26  │  Dec 27  │  Dec 28  │
──────────────┼──────────┼──────────┼──────────┤
   Dec 26     │   320    │   156    │   134    │
   Dec 27     │   156    │   380    │   189    │
   Dec 28     │   134    │   189    │   410    │
══════════════════════════════════════════════════════════════════════════════

Diagonal = Total unique users who engaged on that date
Off-diagonal = Users who engaged on BOTH dates (intersection)
```

**If 5 dates selected → 5×5 matrix**

---

### Dynamic Behavior

| Dates Selected | Graph Points | Retention Buckets | Matrix Size |
|----------------|--------------|-------------------|-------------|
| 2 dates | 2 | 1, 2, none | 2×2 |
| 3 dates | 3 | 1, 2, 3, none | 3×3 |
| 5 dates | 5 | 1, 2, 3, 4, 5, none | 5×5 |
| 10 dates | 10 | 1, 2, 3...10, none | 10×10 |

---

### Fields Used
- `created_at` (date) - For date grouping
- `current_user_id` - For unique user counting
- `is_viewed` - For view engagement
- `is_liked` - For like engagement

### Status: ✅ VERIFIED

---

## METRIC 7: Know More Count Distribution

### Definition

Group users by how many times they clicked "Know More" before making a decision.

**All counts are unique `current_user_id` counts.**

### Display Format

```
KNOW MORE ENGAGEMENT (Do more clicks = better conversion?)
══════════════════════════════════════════════════════════════════════════════════════════

KM Clicks │ Unique Users │ % of Users │ → Liked │ → Disliked │ → Passed │ → No Decision
──────────┼──────────────┼────────────┼─────────┼────────────┼──────────┼───────────────
    0     │     234      │   31.2%    │   45    │     89     │    34    │      66
    1     │     189      │   25.2%    │   67    │     72     │    28    │      22
    2     │     156      │   20.8%    │   78    │     45     │    18    │      15
   3+     │     171      │   22.8%    │   98    │     42     │    12    │      19
══════════════════════════════════════════════════════════════════════════════════════════

📊 Insight: Users with 3+ KM clicks have 57% like rate vs 19% for 0 clicks
```

### Calculation Logic

1. For each unique `current_user_id`, sum all `know_more_count` across their matches
2. Bucket into 0, 1, 2, 3+
3. For each bucket, count how many users ended up in each decision category

### Fields Used
- `current_user_id` (for unique counting)
- `know_more_count` (integer)
- `is_liked` (enum: 'liked', 'disliked', 'passed', null)

### Status: ✅ VERIFIED

---

## METRIC 8: Ghost & Pass-Only Users

### Definition

Identify users with specific behavior patterns:
- **Ghost Users**: Viewed matches but never took any action (like/dislike/pass)
- **Pass-Only Users**: Took actions but never liked anyone (only disliked/passed)

---

### 8a. Ghost Users (Viewed but never decided)

```
GHOST USERS (Viewed but never liked/disliked/passed anyone)
══════════════════════════════════════════════════════════════════════════════════════════

Total Ghost Users:    156 users (12.4% of all viewers)

Breakdown by view count:
──────────────────────────────────────────────────────────────────────────────────────────
Viewed 1-2 matches:    ████████████████████  67 users (43.0%)
Viewed 3-5 matches:    ██████████████        45 users (28.8%)
Viewed 6-8 matches:    ████████              28 users (17.9%)
Viewed ALL 9 matches:  ████                  16 users (10.3%)  ← Most engaged ghosts
──────────────────────────────────────────────────────────────────────────────────────────

Average Know More clicks by ghosts: 1.2
```

**Ghost = Users where:**
- At least 1 `is_viewed = true`
- ALL `is_liked = null` (never decided on anyone)

---

### 8b. Pass-Only Users (Decided but never liked anyone)

```
PASS-ONLY USERS (Took action but never liked anyone)
══════════════════════════════════════════════════════════════════════════════════════════

Total Pass-Only Users:    89 users (7.1% of users who decided)

Their decision patterns:
──────────────────────────────────────────────────────────────────────────────────────────
All Passed (0 dislikes):    ████████████████████  34 users (38.2%)
All Disliked (0 passes):    ██████████████        28 users (31.5%)
Mix of Dislike + Pass:      ████████████          27 users (30.3%)
──────────────────────────────────────────────────────────────────────────────────────────

Avg matches seen before giving up: 6.2
Avg Know More clicks: 1.8
```

**Pass-Only = Users where:**
- At least 1 `is_liked IN ('disliked', 'passed')`
- ZERO `is_liked = 'liked'`

---

### 8c. User Behavior Segments Summary

```
USER BEHAVIOR SEGMENTS
══════════════════════════════════════════════════════════════════════════════════════════

Segment              │ Count │ % of All │ Avg Matches │ Avg KM   │ Description
                     │       │  Users   │   Viewed    │ Clicks   │
─────────────────────┼───────┼──────────┼─────────────┼──────────┼─────────────────────────
Active (liked ≥1)    │  420  │  56.0%   │    7.8      │   2.4    │ Liked at least 1 person
Pass-Only (0 likes)  │   89  │  11.9%   │    6.2      │   1.8    │ Decided but never liked
Ghost (viewed, 0 dec)│  156  │  20.8%   │    3.4      │   1.2    │ Viewed but never decided
Never Viewed         │   85  │  11.3%   │    0.0      │   0.0    │ Got matches, never opened
══════════════════════════════════════════════════════════════════════════════════════════

📊 Key Insight:
- 32.7% of users either ghosted or never viewed (156 + 85 = 241 users)
- Pass-Only users view 6.2 matches on avg before giving up
- Active users have 2x more KM clicks than ghosts
```

---

### Fields Used
- `current_user_id` (for unique user identification)
- `is_viewed` (boolean)
- `is_liked` (enum: 'liked', 'disliked', 'passed', null)
- `know_more_count` (integer)

### Status: ✅ VERIFIED

---

## Data Sources

| Table | Fields Needed | Purpose |
|-------|---------------|---------|
| `user_matches` | All fields | Core metrics data |
| `user_metadata` | `user_id`, `gender`, `professional_tier` | Segmentation |

---

# TECHNICAL SPECIFICATIONS

## Supabase Connection

**Environment Variables Required:**
```
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

**Tables to Query:**
1. `user_matches` - Main analytics data
2. `user_metadata` - User demographics (gender, tier)

---

## Table Schema: `user_matches`

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | uuid | Primary key | `550e8400-e29b-41d4-a716-446655440000` |
| `current_user_id` | uuid | Viewer (person viewing matches) | `user-123-abc` |
| `matched_user_id` | uuid | Candidate (profile being shown) | `user-456-def` |
| `rank` | integer | Match rank position (1-9) | `1` |
| `is_viewed` | boolean | Did user view this match? | `true` |
| `viewed_at` | timestamp | When viewed (IST +05:30) | `2025-12-28T21:30:00+05:30` |
| `is_liked` | enum | Decision made | `'liked'` / `'disliked'` / `'passed'` / `null` |
| `liked_at` | timestamp | When decision was made | `2025-12-28T21:35:00+05:30` |
| `know_more_count` | integer | Times "Know More" clicked | `3` |
| `origin_phase` | string | How match was generated | `'DETERMINISTIC'` / `'ONE_SIDED_BACKFILL'` |
| `created_at` | timestamp | When match was created | `2025-12-28T00:00:00+05:30` |

---

## Table Schema: `user_metadata`

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `user_id` | uuid | User identifier (FK) | `user-123-abc` |
| `gender` | string | User's gender | `'male'` / `'female'` |
| `professional_tier` | integer | User's tier level | `1` / `2` / `3` |

---

## Sample JSON: `user_matches.json`

```json
{
  "metadata": {
    "fetched_at": "2025-12-28T11:45:00+05:30",
    "total_rows": 13560,
    "table": "user_matches"
  },
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "current_user_id": "user-123-abc",
      "matched_user_id": "user-456-def",
      "rank": 1,
      "is_viewed": true,
      "viewed_at": "2025-12-28T21:30:00+05:30",
      "is_liked": "liked",
      "liked_at": "2025-12-28T21:35:00+05:30",
      "know_more_count": 3,
      "origin_phase": "DETERMINISTIC",
      "created_at": "2025-12-28T00:00:00+05:30"
    },
    {
      "id": "...",
      "current_user_id": "user-789-ghi",
      "matched_user_id": "user-012-jkl",
      "rank": 2,
      "is_viewed": true,
      "viewed_at": "2025-12-28T20:15:00+05:30",
      "is_liked": null,
      "liked_at": null,
      "know_more_count": 0,
      "origin_phase": "ONE_SIDED_BACKFILL",
      "created_at": "2025-12-28T00:00:00+05:30"
    }
  ]
}
```

---

## Sample JSON: `user_metadata.json`

```json
{
  "metadata": {
    "fetched_at": "2025-12-28T11:46:00+05:30",
    "total_rows": 1506,
    "table": "user_metadata"
  },
  "data": [
    {
      "user_id": "user-123-abc",
      "gender": "male",
      "professional_tier": 1
    },
    {
      "user_id": "user-456-def",
      "gender": "female",
      "professional_tier": 2
    }
  ]
}
```

---

## Key Join Logic

```
For Viewer metrics:
  user_matches.current_user_id → user_metadata.user_id

For Candidate metrics:
  user_matches.matched_user_id → user_metadata.user_id
```

---

## Important Notes

1. **Timestamps are IST (+05:30)** - No conversion needed
2. **Unique counting** - All metrics use unique `current_user_id`, not row counts
3. **Null handling** - `is_liked = null` means no decision yet (Ghost users)
4. **Rank range** - 1 to 9 (9 matches per user per day typically)
5. **Date filtering** - Use `created_at` field for date-based filtering
