"""
IMS Analytics
Upload a states-table JSON export and analyse why users were marked `skipped`.

For each skipped user we read the LAST record in `error_history` and surface a
reason:
  - If the error is `filtered_pre_compat` (metadata is null), derive the reason
    from the user's own fields: verification_status != verified, deleted_at not
    null, or looking_to_match = false.
  - Otherwise show the error name + any `ineligibility_reasons` from metadata.
"""
import json
import streamlit as st
import pandas as pd

st.title("IMS Analytics")
st.caption("Upload the states JSON and see why skipped users got skipped.")

uploaded = st.file_uploader("Upload states JSON", type=["json"])
if not uploaded:
    st.info("Upload a JSON with top-level `states: [...]` to begin.")
    st.stop()

try:
    payload = json.load(uploaded)
except Exception as e:
    st.error(f"Failed to parse JSON: {e}")
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
# `matches` may be either:
#   - dict: {user_id: count}  (new shape)
#   - list: [{current_user_id: ...}, ...]  (old shape — count by current_user_id)
matches_raw = payload.get("matches")
matches_per_user: dict = {}
if isinstance(matches_raw, dict):
    matches_per_user = {uid: int(n or 0) for uid, n in matches_raw.items()}
elif isinstance(matches_raw, list):
    for m in matches_raw:
        uid = m.get("current_user_id")
        if uid:
            matches_per_user[uid] = matches_per_user.get(uid, 0) + 1

completed_states = [
    s for s in states if s.get("status") in ("completed", "completed_empty")
]

dist_rows = []
for s in completed_states:
    uid = s.get("user_id")
    n = matches_per_user.get(uid, 0)
    dist_rows.append({
        "user_id": uid,
        "status": s.get("status"),
        "gender": s.get("gender"),
        "prof_tier": s.get("prof_tier"),
        "attractiveness_score": s.get("attractiveness_score"),
        "match_count": n,
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

    # Split by status
    st.markdown("**By status**")
    pivot = (
        dist_df.groupby(["bucket", "status"]).size()
        .unstack(fill_value=0)
        .reindex(bucket_order, fill_value=0)
    )
    for col in ("completed", "completed_empty"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot[["completed", "completed_empty"]].reset_index().rename(columns={"bucket": "matches"})
    st.dataframe(pivot, hide_index=True, use_container_width=True)

    with st.expander("Per-user table"):
        st.dataframe(
            dist_df.sort_values("match_count", ascending=False),
            hide_index=True, use_container_width=True,
        )
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
    file_name="ims_skipped_analysis.csv",
    mime="text/csv",
)
