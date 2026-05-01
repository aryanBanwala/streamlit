"""
Instant Matches Analytics
Fetch (or upload) a states-table JSON export and analyse why users were marked
`skipped`.

For each skipped user we read the LAST record in `error_history` and surface a
reason:
  - If the error is `filtered_pre_compat` (metadata is null), derive the reason
    from the user's own fields: verification_status != verified, deleted_at not
    null, or looking_to_match = false.
  - Otherwise show the error name + any `ineligibility_reasons` from metadata.
"""
import json
import os
from datetime import datetime, time, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv


# --- Env ---
_current_dir = os.path.dirname(__file__)
_repo_root = os.path.abspath(os.path.join(_current_dir, "..", ".."))
load_dotenv(os.path.join(_repo_root, ".env"))

INSTANT_MATCH_API_URL = os.getenv("INSTANT_MATCH_API_URL", "")
INSTANT_MATCH_API_KEY = os.getenv("INSTANT_MATCH_API_KEY", "")
IST = timezone(timedelta(hours=5, minutes=30))


def fetch_instant_match_data(since_utc_iso: str, timeout: int = 60) -> dict:
    """POST to the inspect endpoint and return the parsed JSON payload."""
    if not INSTANT_MATCH_API_URL or not INSTANT_MATCH_API_KEY:
        raise RuntimeError(
            "INSTANT_MATCH_API_URL and INSTANT_MATCH_API_KEY must be set in .env"
        )
    resp = requests.post(
        INSTANT_MATCH_API_URL,
        headers={
            "x-api-key": INSTANT_MATCH_API_KEY,
            "content-type": "application/json",
        },
        json={"since": since_utc_iso},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def ist_to_utc_iso(d, t) -> str:
    """Combine an IST date+time and emit `YYYY-MM-DDTHH:MM:SSZ`."""
    dt_ist = datetime.combine(d, t).replace(tzinfo=IST)
    dt_utc = dt_ist.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


st.title("Instant Matches Analytics")
st.caption("Fetch from the API or upload a states JSON, then see why skipped users got skipped.")

# --- Source selector ---
tab_fetch, tab_upload = st.tabs(["Fetch from API", "Upload JSON"])

with tab_fetch:
    col_d, col_t = st.columns(2)
    default_dt = datetime.now(IST) - timedelta(hours=24)
    since_date = col_d.date_input("Since (IST date)", value=default_dt.date(), key="im_since_date")
    since_time = col_t.time_input("Since (IST time)", value=time(0, 0), key="im_since_time")
    since_utc = ist_to_utc_iso(since_date, since_time)
    st.caption(f"Will send `since`: `{since_utc}` (UTC)")

    if st.button("Fetch data", type="primary"):
        try:
            with st.spinner("Calling instant-match inspect API…"):
                st.session_state["im_payload"] = fetch_instant_match_data(since_utc)
            st.success("Fetched.")
        except requests.HTTPError as e:
            st.error(f"HTTP {e.response.status_code}: {e.response.text[:500]}")
        except Exception as e:
            st.error(f"Fetch failed: {e}")

with tab_upload:
    uploaded = st.file_uploader("Upload states JSON", type=["json"])
    if uploaded is not None:
        try:
            st.session_state["im_payload"] = json.load(uploaded)
            st.success("Loaded uploaded JSON.")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")

payload = st.session_state.get("im_payload")
if not payload:
    st.info("Fetch from the API or upload a JSON with top-level `states: [...]` to begin.")
    st.stop()

states = payload.get("states") or []
if not states:
    st.warning("No `states` array found in this JSON.")
    st.stop()


# --- Summary ---
total = len(states)
by_status = {}
for s in states:
    by_status[s.get("status", "unknown")] = by_status.get(s.get("status", "unknown"), 0) + 1

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Since", str(payload.get("since", "—"))[:19])
c2.metric("Picked", payload.get("picked_state_count", total))
c3.metric("Completed", by_status.get("completed", 0))
c4.metric("Completed empty", by_status.get("completed_empty", 0))
c5.metric("Skipped", by_status.get("skipped", 0))

st.markdown("---")


# --- Completed / completed_empty match-count distribution ---
# `matches` shapes seen so far:
#   - dict of dicts: {user_id: {count, actions, viewed, unviewed}}  (current)
#     where actions = {action_name: [matched_user_ids]} OR {action_name: count}
#   - dict of ints:  {user_id: count}                                (older)
#   - list:          [{current_user_id: ...}, ...]                   (oldest)
def _action_count(v):
    """Return a count for an action value that might be a list of ids or an int."""
    if v is None:
        return 0
    if isinstance(v, list):
        return len(v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


matches_raw = payload.get("matches")
matches_per_user: dict = {}            # user_id -> count
match_info_per_user: dict = {}         # user_id -> {count, actions, viewed, unviewed}

if isinstance(matches_raw, dict):
    for uid, v in matches_raw.items():
        if isinstance(v, dict):
            matches_per_user[uid] = int(v.get("count") or 0)
            match_info_per_user[uid] = {
                "count": int(v.get("count") or 0),
                "viewed": int(v.get("viewed") or 0),
                "unviewed": int(v.get("unviewed") or 0),
                "actions": v.get("actions") or {},
            }
        else:
            matches_per_user[uid] = int(v or 0)
elif isinstance(matches_raw, list):
    for m in matches_raw:
        uid = m.get("current_user_id")
        if uid:
            matches_per_user[uid] = matches_per_user.get(uid, 0) + 1


# --- Action totals + viewed/unviewed (top-level) ---
action_totals = payload.get("action_totals") or {}
total_count_all = sum(matches_per_user.values()) or payload.get("total_matches") or 0
total_viewed = sum(v.get("viewed", 0) for v in match_info_per_user.values())
total_unviewed = sum(v.get("unviewed", 0) for v in match_info_per_user.values())

if action_totals or match_info_per_user:
    st.subheader("Match actions & view stats")

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Shortlisted", action_totals.get("shortlisted", 0))
    a2.metric("Rejected", action_totals.get("rejected", 0))
    a3.metric("Passed", action_totals.get("passed", 0))
    a4.metric("No action", action_totals.get("none", 0))

    v1, v2, v3 = st.columns(3)
    v1.metric("Total matches", total_count_all)
    v2.metric("Viewed", total_viewed)
    v3.metric("Unviewed", total_unviewed)

    st.markdown("---")


completed_states = [
    s for s in states if s.get("status") in ("completed", "completed_empty")
]

dist_rows = []
for s in completed_states:
    uid = s.get("user_id")
    n = matches_per_user.get(uid, 0)
    info = match_info_per_user.get(uid, {})
    actions = info.get("actions") or {}
    dist_rows.append({
        "user_id": uid,
        "status": s.get("status"),
        "gender": s.get("gender"),
        "prof_tier": s.get("prof_tier"),
        "attractiveness_score": s.get("attractiveness_score"),
        "match_count": n,
        "viewed": info.get("viewed", 0),
        "unviewed": info.get("unviewed", 0),
        "shortlisted": _action_count(actions.get("shortlisted")),
        "rejected": _action_count(actions.get("rejected")),
        "passed": _action_count(actions.get("passed")),
        "no_action": _action_count(actions.get("none")),
    })

st.subheader(f"Completed / completed_empty — matches per user")

if dist_rows:
    dist_df = pd.DataFrame(dist_rows)

    # Bucket counts: 0, 1, 2, 3, 4, 5+
    def bucket(n: int) -> str:
        return "5+" if n >= 5 else str(n)

    dist_df["bucket"] = dist_df["match_count"].apply(bucket)
    bucket_order = ["0", "1", "2", "3", "4", "5+"]

    # Overall
    overall = (
        dist_df["bucket"].value_counts().reindex(bucket_order, fill_value=0)
        .rename_axis("matches").reset_index(name="users")
    )
    st.markdown("**Overall**")
    st.dataframe(overall, hide_index=True, use_container_width=True)
    st.bar_chart(overall.set_index("matches")["users"])

    # Split by gender
    st.markdown("**By gender**")
    gender_df = dist_df.copy()
    gender_df["gender"] = gender_df["gender"].fillna("unknown")

    # Per-gender summary: users, total matches, avg, % with 0
    summary = (
        gender_df.groupby("gender")
        .agg(
            users=("user_id", "count"),
            total_matches=("match_count", "sum"),
            avg_matches=("match_count", "mean"),
            zero_match_users=("match_count", lambda x: int((x == 0).sum())),
        )
        .reset_index()
    )
    summary["avg_matches"] = summary["avg_matches"].round(2)
    st.dataframe(summary, hide_index=True, use_container_width=True)

    # Bucket pivot by gender
    gpivot = (
        gender_df.groupby(["bucket", "gender"]).size()
        .unstack(fill_value=0)
        .reindex(bucket_order, fill_value=0)
        .reset_index()
        .rename(columns={"bucket": "matches"})
    )
    st.dataframe(gpivot, hide_index=True, use_container_width=True)

    # Actions + view stats by gender
    st.markdown("**Actions & views by gender**")
    action_summary = (
        gender_df.groupby("gender")
        .agg(
            users=("user_id", "count"),
            matches=("match_count", "sum"),
            viewed=("viewed", "sum"),
            unviewed=("unviewed", "sum"),
            shortlisted=("shortlisted", "sum"),
            rejected=("rejected", "sum"),
            passed=("passed", "sum"),
            no_action=("no_action", "sum"),
        )
        .reset_index()
    )
    st.dataframe(action_summary, hide_index=True, use_container_width=True)

    # User-level engagement by gender (only users who actually got matches)
    st.markdown("**User engagement by gender** (denominator = users with ≥1 match)")
    eligible = gender_df[gender_df["match_count"] > 0]
    engagement = (
        eligible.groupby("gender")
        .agg(
            users_with_matches=("user_id", "count"),
            viewed_atleast_one=("viewed", lambda x: int((x >= 1).sum())),
            shortlisted_atleast_one=("shortlisted", lambda x: int((x >= 1).sum())),
        )
        .reset_index()
    )
    st.dataframe(engagement, hide_index=True, use_container_width=True)

    with st.expander("Per-user table (completed only)"):
        st.dataframe(
            dist_df[dist_df["status"] == "completed"]
            .drop(columns=["bucket"])
            .sort_values("match_count", ascending=False),
            hide_index=True, use_container_width=True,
        )

    # Detailed completed_empty users
    empty_users = [s for s in completed_states if s.get("status") == "completed_empty"]
    st.markdown(f"**`completed_empty` users — {len(empty_users)}**")
    if empty_users:
        def _ltm(v):
            if v is True:
                return "true"
            if v is False:
                return "false"
            return "—"

        empty_detail = pd.DataFrame([
            {
                "user_id": s.get("user_id"),
                "gender": s.get("gender"),
                "prof_tier": s.get("prof_tier"),
                "attractiveness_score": s.get("attractiveness_score"),
                "verification_status": s.get("verification_status"),
                "looking_to_match": _ltm(s.get("looking_to_match")),
                "deleted_at": s.get("deleted_at"),
                "attempts": s.get("attempts"),
            }
            for s in empty_users
        ])
        st.dataframe(empty_detail, hide_index=True, use_container_width=True)
        st.download_button(
            "Download completed_empty CSV",
            data=empty_detail.to_csv(index=False).encode(),
            file_name="instant_matches_completed_empty.csv",
            mime="text/csv",
        )
    else:
        st.caption("No `completed_empty` users in this export.")

    # completed_empty split by gender
    st.markdown("**`completed_empty` by gender**")
    empty_df = gender_df[gender_df["status"] == "completed_empty"]
    if len(empty_df):
        empty_summary = (
            empty_df.groupby("gender")
            .size()
            .reset_index(name="completed_empty_users")
        )
        totals = gender_df.groupby("gender").size().reset_index(name="total_users")
        empty_summary = empty_summary.merge(totals, on="gender", how="right").fillna(0)
        empty_summary["completed_empty_users"] = empty_summary["completed_empty_users"].astype(int)
        st.dataframe(empty_summary, hide_index=True, use_container_width=True)
    else:
        st.caption("No `completed_empty` users in this export.")
else:
    st.info("No completed/completed_empty users in this export.")

st.markdown("---")


# --- Reason derivation ---
def derive_filtered_pre_compat_reason(user: dict) -> str:
    reasons = []
    if (user.get("verification_status") or "").lower() != "verified":
        reasons.append(f"verification_status={user.get('verification_status')!r}")
    if user.get("deleted_at"):
        reasons.append(f"deleted_at={user.get('deleted_at')}")
    if user.get("looking_to_match") is False:
        reasons.append("looking_to_match=false")
    return ", ".join(reasons) if reasons else "no obvious user-field reason"


def analyse(user: dict) -> dict:
    hist = user.get("error_history") or []
    last = hist[-1] if hist else None

    error = last.get("error") if last else None
    metadata = (last or {}).get("metadata") or {}

    if last is None:
        reason = "no error_history"
        reason_kind = "missing"
    elif error == "filtered_pre_compat":
        reason = derive_filtered_pre_compat_reason(user)
        reason_kind = "filtered_pre_compat"
    else:
        inelig = metadata.get("ineligibility_reasons") or []
        reason = ", ".join(inelig) if inelig else "—"
        reason_kind = error or "unknown"

    return {
        "user_id": user.get("user_id"),
        "status": user.get("status"),
        "attempts": user.get("attempts"),
        "gender": user.get("gender"),
        "prof_tier": user.get("prof_tier"),
        "attractiveness_score": user.get("attractiveness_score"),
        "verification_status": user.get("verification_status"),
        "looking_to_match": user.get("looking_to_match"),
        "deleted_at": user.get("deleted_at"),
        "last_error": error,
        "reason_kind": reason_kind,
        "reason": reason,
        "last_error_at": (last or {}).get("at"),
    }


skipped = [analyse(s) for s in states if s.get("status") == "skipped"]

st.subheader(f"Skipped users — {len(skipped)}")

if not skipped:
    st.success("No skipped users in this export.")
    st.stop()

df = pd.DataFrame(skipped)

# --- Reason breakdown ---
st.markdown("**Reason-kind breakdown**")
kind_counts = df["reason_kind"].value_counts().rename_axis("reason_kind").reset_index(name="count")
st.dataframe(kind_counts, hide_index=True, use_container_width=True)

st.markdown("**Top specific reasons**")
reason_counts = df["reason"].value_counts().rename_axis("reason").reset_index(name="count")
st.dataframe(reason_counts.head(25), hide_index=True, use_container_width=True)

st.markdown("---")

# --- Filters + table ---
kinds = sorted(df["reason_kind"].unique().tolist())
chosen = st.multiselect("Filter by reason_kind", kinds, default=kinds)
view = df[df["reason_kind"].isin(chosen)].copy()

st.markdown(f"**Rows: {len(view)}**")
st.dataframe(
    view[
        [
            "user_id", "reason_kind", "reason", "last_error", "attempts",
            "gender", "prof_tier", "attractiveness_score",
            "verification_status", "looking_to_match", "deleted_at",
            "last_error_at",
        ]
    ],
    hide_index=True,
    use_container_width=True,
)

st.download_button(
    "Download analysis CSV",
    data=view.to_csv(index=False).encode(),
    file_name="instant_matches_skipped_analysis.csv",
    mime="text/csv",
)


# =====================================================================
# Match Action Demographics
# Look at who got shortlisted/rejected/passed/none, broken down by the
# matched user's tier / attractiveness / gender.
# Uses: payload.matches[viewer_id].actions = {action: [matched_user_ids]}
#       payload.matched_users[user_id]    = {prof_tier, attractiveness_score, gender}
# =====================================================================
st.markdown("---")
st.header("Match action demographics")

matched_users = payload.get("matched_users") or {}
viewer_info = {s.get("user_id"): s for s in states}

action_rows = []
for viewer_id, m in (payload.get("matches") or {}).items():
    if not isinstance(m, dict):
        continue
    actions = m.get("actions") or {}
    viewer = viewer_info.get(viewer_id, {}) or {}
    for action_name, matched_ids in actions.items():
        # New schema: {action: [user_ids]}.  Older shape was {action: count}.
        if not isinstance(matched_ids, list):
            continue
        for mid in matched_ids:
            mu = matched_users.get(mid, {}) or {}
            action_rows.append({
                "viewer_id": viewer_id,
                "viewer_gender": viewer.get("gender"),
                "viewer_tier": viewer.get("prof_tier"),
                "viewer_attr": viewer.get("attractiveness_score"),
                "action": action_name,
                "matched_user_id": mid,
                "matched_gender": mu.get("gender"),
                "matched_tier": mu.get("prof_tier"),
                "matched_attr": mu.get("attractiveness_score"),
            })

if not action_rows:
    st.info("No per-match action data found (matches[].actions must be lists of user_ids).")
else:
    a_df = pd.DataFrame(action_rows)

    # --- Filters ---
    fc1, fc2 = st.columns(2)
    viewer_genders = ["all"] + sorted(g for g in a_df["viewer_gender"].dropna().unique())
    vg = fc1.selectbox("Viewer gender", viewer_genders, key="ad_viewer_gender")
    all_actions = sorted(a_df["action"].unique())
    chosen_actions = fc2.multiselect("Actions", all_actions, default=all_actions, key="ad_actions")

    f_df = a_df.copy()
    if vg != "all":
        f_df = f_df[f_df["viewer_gender"] == vg]
    if chosen_actions:
        f_df = f_df[f_df["action"].isin(chosen_actions)]

    st.caption(f"Filtered rows: **{len(f_df)}**")

    if f_df.empty:
        st.info("No rows after filters.")
    else:
        breakdown = pd.pivot_table(
            f_df,
            index=[
                "viewer_tier", "viewer_gender", "viewer_attr",
                "matched_tier", "matched_gender", "matched_attr",
            ],
            columns="action",
            aggfunc="size",
            fill_value=0,
            dropna=False,
        )
        breakdown["total"] = breakdown.sum(axis=1)
        breakdown = breakdown.sort_values("total", ascending=False).reset_index()
        st.dataframe(breakdown, hide_index=True, use_container_width=True)

        # --- Rejection matrices ---
        rej = f_df[f_df["action"] == "rejected"].copy()
        st.markdown("---")
        st.subheader("Rejection matrices (rows = viewer, cols = matched)")

        st.markdown("**Tier × tier**")
        tier_levels = ["1", "2", "3"]
        rej["_vt"] = rej["viewer_tier"].astype(str)
        rej["_mt"] = rej["matched_tier"].astype(str)
        tier_mat = (
            pd.crosstab(rej["_vt"], rej["_mt"])
            .reindex(index=tier_levels, columns=tier_levels, fill_value=0)
        )
        tier_mat.index.name = "viewer_tier"
        tier_mat.columns.name = "matched_tier"
        st.dataframe(tier_mat, use_container_width=True)

        st.markdown("**Attractiveness × attractiveness** (rounded, 1-10)")
        attr_levels = list(range(1, 11))
        rej["_va"] = rej["viewer_attr"].round().astype("Int64")
        rej["_ma"] = rej["matched_attr"].round().astype("Int64")
        attr_mat = (
            pd.crosstab(rej["_va"], rej["_ma"])
            .reindex(index=attr_levels, columns=attr_levels, fill_value=0)
        )
        attr_mat.index.name = "viewer_attr"
        attr_mat.columns.name = "matched_attr"
        st.dataframe(attr_mat, use_container_width=True)

        st.download_button(
            "Download CSV",
            data=breakdown.to_csv(index=False).encode(),
            file_name="instant_matches_action_demographics.csv",
            mime="text/csv",
        )
