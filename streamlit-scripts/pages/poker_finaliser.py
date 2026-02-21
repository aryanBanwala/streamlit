"""
Poker Amount Finaliser - Settle poker debts with maximum roasting.
"""
import streamlit as st
import os
import sys
from dotenv import load_dotenv

# Setup paths
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, scripts_dir)

try:
    from dependencies import get_openrouter_client
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)


# --- Settlement Logic ---

def calculate_settlement(players: list[dict]) -> dict:
    summary = []
    for p in players:
        net = p["final_amount"] - p["taken_from_bank"]
        summary.append({
            "name": p["name"],
            "taken_from_bank": p["taken_from_bank"],
            "final_amount": p["final_amount"],
            "net": round(net, 2)
        })

    total_taken = sum(p["taken_from_bank"] for p in players)
    total_final = sum(p["final_amount"] for p in players)
    discrepancy = round(total_final - total_taken, 2)

    debtors = [{"name": s["name"], "amount": -s["net"]} for s in summary if s["net"] < 0]
    creditors = [{"name": s["name"], "amount": s["net"]} for s in summary if s["net"] > 0]

    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)

    transactions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        d = debtors[i]
        c = creditors[j]
        settle_amount = round(min(d["amount"], c["amount"]), 2)

        if settle_amount > 0:
            transactions.append({
                "from": d["name"],
                "to": c["name"],
                "amount": settle_amount
            })

        d["amount"] = round(d["amount"] - settle_amount, 2)
        c["amount"] = round(c["amount"] - settle_amount, 2)

        if d["amount"] == 0:
            i += 1
        if c["amount"] == 0:
            j += 1

    return {
        "player_summary": summary,
        "total_taken": total_taken,
        "total_final": total_final,
        "discrepancy": discrepancy,
        "has_discrepancy": abs(discrepancy) > 0.01,
        "transactions": transactions
    }


def generate_roast_commentary(result: dict) -> str:
    """Use LLM to generate hilarious roast commentary for the poker results."""
    client = get_openrouter_client()
    if not client:
        return _fallback_commentary(result)

    summary_text = ""
    for p in result["player_summary"]:
        sign = "+" if p["net"] >= 0 else ""
        summary_text += f"- {p['name']}: took ₹{p['taken_from_bank']} from bank, ended with ₹{p['final_amount']}, net: {sign}{p['net']}\n"

    transactions_text = ""
    for t in result["transactions"]:
        transactions_text += f"- {t['from']} pays ₹{t['amount']} to {t['to']}\n"

    discrepancy_text = ""
    if result["has_discrepancy"]:
        discrepancy_text = f"\nDISCREPANCY: ₹{result['discrepancy']} {'extra' if result['discrepancy'] > 0 else 'missing'} chips!"

    prompt = f"""You are a savage poker commentary roaster who speaks in Hinglish (Hindi + English mix). You're the group's brutally honest friend who has ZERO chill.

Here are the poker game results:

PLAYERS:
{summary_text}
{discrepancy_text}

SETTLEMENTS:
{transactions_text if transactions_text else "No settlements needed - everyone broke even (boring game lol)"}

Now generate a HILARIOUS roast commentary. Rules:
1. Roast each player individually based on their performance - the bigger the loss, the harder the roast
2. Give special savage treatment to whoever lost the most (call them ATM machine, charity foundation, etc.)
3. Hype up the winners like they're poker gods (but also hint ki shayad luck tha)
4. If someone broke even, mock them for being boring
5. If there's a discrepancy, make a conspiracy theory about who stole the chips
6. Add a "Player of the Night" award (most entertaining loser) and "Luckiest Bastard" award
7. End with a prediction for next game
8. Use lots of Hinglish, desi references, bollywood dialogues
9. Keep it funny, not mean-spirited - ye sab apne bhai hain
10. Use emojis generously
11. Keep it concise - max 300 words

Format it nicely with headers and sections."""

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.9,
        )
        return response.choices[0].message.content
    except Exception as e:
        return _fallback_commentary(result)


def _fallback_commentary(result: dict) -> str:
    """Fallback funny commentary when LLM is unavailable."""
    lines = []
    lines.append("## Poker Night Ka Result Aa Gaya Bhai Log")
    lines.append("")

    sorted_players = sorted(result["player_summary"], key=lambda x: x["net"])

    # Biggest loser
    biggest_loser = sorted_players[0]
    if biggest_loser["net"] < 0:
        lines.append(f"### Sabse Bada ATM Machine: {biggest_loser['name']}")
        lines.append(f"Bhai ₹{abs(biggest_loser['net'])} haar gaya. Agli baar poker mat khel, teen patti khel, wahan bhi toh haarna hi hai.")
        lines.append("")

    # Biggest winner
    biggest_winner = sorted_players[-1]
    if biggest_winner["net"] > 0:
        lines.append(f"### Tonight's Sher: {biggest_winner['name']}")
        lines.append(f"₹{biggest_winner['net']} jeeta. Bhai party toh banti hai, ya fir next game mein sab wapas le lenge.")
        lines.append("")

    # Everyone else
    for p in sorted_players[1:-1]:
        if p["net"] == 0:
            lines.append(f"**{p['name']}**: Break even. Bhai tu poker khelne aaya tha ya time pass karne?")
        elif p["net"] < 0:
            lines.append(f"**{p['name']}**: ₹{abs(p['net'])} gaye. Tera toh 'Apna Paisa Apni Marzi' chal raha tha.")
        else:
            lines.append(f"**{p['name']}**: ₹{p['net']} profit. Chal theek hai, chai toh pila de.")

    if result["has_discrepancy"]:
        lines.append("")
        lines.append(f"### SUS ALERT")
        lines.append(f"₹{abs(result['discrepancy'])} {'zyada' if result['discrepancy'] > 0 else 'kum'} hai. Kisi ne chips khaaye kya? CBI jaanch honi chahiye.")

    lines.append("")
    lines.append("---")
    lines.append("*Agli baar phir milenge, phir se kisi ka wallet khaali karenge.*")

    return "\n".join(lines)


# --- Session State Init ---
if "poker_players" not in st.session_state:
    st.session_state.poker_players = [
        {"name": "", "taken_from_bank": 0, "final_amount": 0}
        for _ in range(4)
    ]
if "poker_result" not in st.session_state:
    st.session_state.poker_result = None
if "poker_commentary" not in st.session_state:
    st.session_state.poker_commentary = None


# --- UI ---
st.title("Poker Amount Finaliser")
st.caption("Settle poker debts. Roast the losers. Repeat next weekend.")

st.divider()

# --- Player Input Section ---
st.subheader("Players")

num_players = st.number_input(
    "Number of players",
    min_value=2,
    max_value=20,
    value=len(st.session_state.poker_players),
    step=1,
    key="poker_num_players"
)

# Adjust player list size
current_count = len(st.session_state.poker_players)
if num_players > current_count:
    for _ in range(num_players - current_count):
        st.session_state.poker_players.append({"name": "", "taken_from_bank": 0, "final_amount": 0})
elif num_players < current_count:
    st.session_state.poker_players = st.session_state.poker_players[:num_players]

# Header row
header_cols = st.columns([2, 2, 2, 1])
header_cols[0].markdown("**Name**")
header_cols[1].markdown("**Taken from Bank (Buy-ins)**")
header_cols[2].markdown("**Final Amount (Chips)**")
header_cols[3].markdown("**Net**")

# Player rows
for idx in range(len(st.session_state.poker_players)):
    cols = st.columns([2, 2, 2, 1])

    with cols[0]:
        name = st.text_input(
            "Name",
            value=st.session_state.poker_players[idx]["name"],
            key=f"poker_name_{idx}",
            label_visibility="collapsed",
            placeholder=f"Player {idx + 1}"
        )
        st.session_state.poker_players[idx]["name"] = name

    with cols[1]:
        taken = st.number_input(
            "Taken",
            min_value=0,
            value=st.session_state.poker_players[idx]["taken_from_bank"],
            step=100,
            key=f"poker_taken_{idx}",
            label_visibility="collapsed"
        )
        st.session_state.poker_players[idx]["taken_from_bank"] = taken

    with cols[2]:
        final = st.number_input(
            "Final",
            min_value=0,
            value=st.session_state.poker_players[idx]["final_amount"],
            step=100,
            key=f"poker_final_{idx}",
            label_visibility="collapsed"
        )
        st.session_state.poker_players[idx]["final_amount"] = final

    with cols[3]:
        net = final - taken
        if net > 0:
            st.markdown(f"<p style='color: #00c853; font-size: 1.2em; margin-top: 8px;'>+{net}</p>", unsafe_allow_html=True)
        elif net < 0:
            st.markdown(f"<p style='color: #ff1744; font-size: 1.2em; margin-top: 8px;'>{net}</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='color: #9e9e9e; font-size: 1.2em; margin-top: 8px;'>0</p>", unsafe_allow_html=True)

# Live totals bar
total_taken = sum(p["taken_from_bank"] for p in st.session_state.poker_players)
total_final = sum(p["final_amount"] for p in st.session_state.poker_players)
live_disc = total_final - total_taken

info_cols = st.columns(3)
info_cols[0].metric("Total Taken from Bank", f"₹{total_taken:,}")
info_cols[1].metric("Total Final Amounts", f"₹{total_final:,}")
if abs(live_disc) > 0:
    info_cols[2].metric("Discrepancy", f"₹{live_disc:,}", delta=f"{live_disc:+,}", delta_color="inverse")
else:
    info_cols[2].metric("Discrepancy", "₹0", delta="Balanced", delta_color="off")

st.divider()

# --- Calculate Button ---
calc_col1, calc_col2 = st.columns([3, 1])

with calc_col1:
    calculate_clicked = st.button(
        "Calculate Settlements",
        type="primary",
        use_container_width=True,
        key="poker_calculate_btn"
    )

with calc_col2:
    use_llm = st.checkbox("AI Roast", value=True, key="poker_use_llm", help="Use AI to generate savage commentary")

if calculate_clicked:
    # Validate
    players = st.session_state.poker_players
    valid_players = [p for p in players if p["name"].strip()]

    if len(valid_players) < 2:
        st.error("Kam se kam 2 players ka naam toh daal bhai!")
    else:
        # Check for duplicate names
        names = [p["name"].strip() for p in valid_players]
        if len(names) != len(set(names)):
            st.error("Duplicate names! Sab ka alag naam daal.")
        else:
            # Clean up player data
            clean_players = [
                {
                    "name": p["name"].strip(),
                    "taken_from_bank": p["taken_from_bank"],
                    "final_amount": p["final_amount"]
                }
                for p in valid_players
            ]

            result = calculate_settlement(clean_players)
            st.session_state.poker_result = result

            # Generate commentary
            if use_llm:
                with st.spinner("AI roast generate ho raha hai... hold tight"):
                    st.session_state.poker_commentary = generate_roast_commentary(result)
            else:
                st.session_state.poker_commentary = _fallback_commentary(result)


# --- Results Display ---
if st.session_state.poker_result:
    result = st.session_state.poker_result

    st.divider()
    st.subheader("Results")

    # --- Discrepancy Alert ---
    if result["has_discrepancy"]:
        if result["discrepancy"] > 0:
            st.error(f"DISCREPANCY: ₹{result['discrepancy']:,} EXTRA chips detected. Players ke paas bank se zyada paisa hai. Kisi ne chori ki ya galat count hai!")
        else:
            st.warning(f"DISCREPANCY: ₹{abs(result['discrepancy']):,} chips MISSING. Chips gayab hain. Ginatri galat hai ya kisi ne kha liye.")
    else:
        st.success("Amounts perfectly balanced, as all things should be.")

    # --- Summary Table ---
    st.markdown("#### Player Summary")

    # Sort by net descending (winners first)
    sorted_summary = sorted(result["player_summary"], key=lambda x: x["net"], reverse=True)

    table_html = """
    <style>
        .poker-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        .poker-table th { background: #1a1a2e; color: #e0e0e0; padding: 12px 16px; text-align: left; border-bottom: 2px solid #16213e; }
        .poker-table td { padding: 10px 16px; border-bottom: 1px solid #1a1a2e; }
        .poker-table tr:hover { background: #16213e; }
        .winner { color: #00e676; font-weight: bold; }
        .loser { color: #ff5252; font-weight: bold; }
        .even { color: #9e9e9e; }
        .rank-badge { display: inline-block; width: 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; margin-right: 8px; }
    </style>
    <table class="poker-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Player</th>
                <th>Taken from Bank</th>
                <th>Final Amount</th>
                <th>Net P/L</th>
            </tr>
        </thead>
        <tbody>
    """

    for rank, p in enumerate(sorted_summary, 1):
        if p["net"] > 0:
            net_class = "winner"
            net_str = f"+₹{p['net']:,}"
            badge = "🏆" if rank == 1 else "📈"
        elif p["net"] < 0:
            net_class = "loser"
            net_str = f"-₹{abs(p['net']):,}"
            badge = "💀" if rank == len(sorted_summary) else "📉"
        else:
            net_class = "even"
            net_str = "₹0"
            badge = "😐"

        table_html += f"""
            <tr>
                <td>{badge}</td>
                <td><strong>{p['name']}</strong></td>
                <td>₹{p['taken_from_bank']:,}</td>
                <td>₹{p['final_amount']:,}</td>
                <td class="{net_class}">{net_str}</td>
            </tr>
        """

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

    # --- Settlement Transactions ---
    st.markdown("#### Settlements")

    if not result["transactions"]:
        st.info("No settlements needed. Everyone broke even. Kya boring game tha.")
    else:
        st.markdown("Follow these transactions to settle all debts:")
        for idx, t in enumerate(result["transactions"], 1):
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 16px 20px; border-radius: 12px; margin: 8px 0; border-left: 4px solid #ff5252; display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <span style="color: #ff5252; font-weight: bold; font-size: 1.1em;">{t['from']}</span>
                        <span style="color: #9e9e9e; margin: 0 12px;">pays</span>
                        <span style="color: #00e676; font-weight: bold; font-size: 1.1em;">{t['to']}</span>
                    </div>
                    <div style="background: #0a0a1a; padding: 8px 16px; border-radius: 8px;">
                        <span style="color: #ffd740; font-weight: bold; font-size: 1.3em;">₹{t['amount']:,}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Verification note
        total_settled = sum(t["amount"] for t in result["transactions"])
        st.caption(f"Total money moving: ₹{total_settled:,} across {len(result['transactions'])} transaction(s)")

    # --- Commentary ---
    st.divider()
    st.subheader("Post-Game Commentary")

    if st.session_state.poker_commentary:
        st.markdown(st.session_state.poker_commentary)

    # Regenerate button (won't reload the whole page - just updates commentary)
    if st.button("🔄 Generate New Roast", key="poker_regen_roast"):
        with st.spinner("Naya roast aa raha hai..."):
            st.session_state.poker_commentary = generate_roast_commentary(result)
            st.rerun()
