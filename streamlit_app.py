import streamlit as st
import streamlit.components.v1 as components
import requests
import io
from PIL import Image

# ─────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────
API_URL     = "http://localhost:8050/api/v1"
AUTH_URL    = "http://localhost:8050/api/v1/auth"
BACKEND_URL = "http://localhost:8050/api/v1"
ADMIN_EMAIL = "admin@gmail.com"

# ─────────────────────────────────────────────────────────
# CACHE FUNCTIONS
# ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_season(month: int):
    try:
        resp = requests.get(f"{BACKEND_URL}/season", params={"month": month})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Could not fetch season: {e}")
    return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_recommendations(month: int, lang: str = "ne"):
    try:
        resp = requests.get(f"{BACKEND_URL}/recommendations", params={"month": month, "lang": lang})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Could not fetch recommendations: {e}")
    return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_dashboard(month: int, lang: str = "ne"):
    try:
        resp = requests.get(f"{BACKEND_URL}/dashboard", params={"month": month, "lang": lang})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Could not fetch dashboard: {e}")
    return None


# ── FIXED: single definition, high limit, handles list or dict response ──
def fetch_all_farmers(token: str):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{BACKEND_URL}/admin/farmers",
            headers=headers,
            params={"skip": 0, "limit": 1000},
        )
        print("STATUS:", resp.status_code)
        print("BODY:", resp.text[:500])
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("farmers") or data.get("data") or data.get("results") or []
    except Exception as e:
        print(f"Could not fetch farmers: {e}")
    return []


# ─────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="KrishiMitra - Agri-Fintech", page_icon="🌾", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Sora', sans-serif; }
.metric-card {
    background: linear-gradient(145deg, #064e3b, #0f2027);
    border: 1px solid rgba(52,211,153,0.2);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    text-align: center;
    margin-bottom: 0.5rem;
}
.metric-card .m-label { font-size:0.7rem; color:#6ee7b7; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; }
.metric-card .m-value { font-size:1.8rem; font-weight:700; color:#ecfdf5; font-family:monospace; }
.metric-card .m-sub   { font-size:0.72rem; color:#a7f3d0; margin-top:2px; }
.admin-header {
    background: linear-gradient(135deg, #064e3b, #065f46);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    border: 1px solid rgba(52,211,153,0.3);
}
.admin-header h2 { color:#ecfdf5; margin:0; font-size:1.6rem; font-weight:700; }
.admin-header p  { color:#a7f3d0; margin:4px 0 0 0; font-size:0.85rem; }
</style>
""", unsafe_allow_html=True)

st.title("KrishiMitra (कृषिमित्र) 🌾")

# ─────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────
defaults = {
    "access_token": None, "user_id": None, "user_email": None,
    "messages": [{"role": "assistant", "content": "नमस्ते! म कृषिमित्र हुँ। मलाई तपाईको बाली वा समस्याको बारेमा सोध्न सक्नुहुन्छ। तस्बिर पठाउन 🖼️ बटन थिच्नुहोस्।"}],
    "disease_raw": None, "show_uploader": False, "pending_image": None,
    "show_expert": False, "pending_prompt": None, "page": "chat",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────
if not st.session_state.access_token:
    st.subheader("Login or Register")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login_form"):
            login_email    = st.text_input("Email")
            login_password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                try:
                    res = requests.post(f"{AUTH_URL}/login", json={"email": login_email, "password": login_password})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.access_token = data["access_token"]
                        st.session_state.user_id      = data["user_id"]
                        st.session_state.user_email   = login_email
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
                except Exception:
                    st.error("Could not connect to the backend server.")

    with tab2:
        with st.form("register_form"):
            reg_name     = st.text_input("Full Name")
            reg_email    = st.text_input("Email")
            reg_password = st.text_input("Password", type="password")
            if st.form_submit_button("Register"):
                try:
                    res = requests.post(f"{AUTH_URL}/register", json={"email": reg_email, "password": reg_password, "name": reg_name})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.access_token = data["access_token"]
                        st.session_state.user_id      = data["user_id"]
                        st.session_state.user_email   = reg_email
                        st.rerun()
                    else:
                        st.error(f"Registration failed: {res.json().get('detail', 'Error')}")
                except Exception:
                    st.error("Could not connect to the backend server.")

# ─────────────────────────────────────────────────────────
# LOGGED IN
# ─────────────────────────────────────────────────────────
else:
    is_admin = (st.session_state.user_email == ADMIN_EMAIL)

    st.success(f"Logged in as {st.session_state.user_email}" + (" 👑 Admin" if is_admin else ""))
    if st.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.markdown("---")

    # ── FIXED: admin sees only admin board, regular users see chat/dashboard/expert ──
    if is_admin:
        # Admin goes straight to farmer profiles — no other pages shown
        page = "👑 Admin — Farmer Profiles"
        st.sidebar.title("KrishiMitra Admin")
        st.sidebar.info("👑 Admin panel — farmer profiles & credit scores")
    else:
        nav_options = ["Chat", "Dashboard", "Expert Panel"]
        st.sidebar.title("KrishiMitra")
        page = st.sidebar.radio("Go to", nav_options)

    # ─────────────────────────────────────────────────────
    # HELPER: Expert panel
    # ─────────────────────────────────────────────────────
    def render_expert_panel():
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1A3526,#2D5A3D);border-radius:16px;padding:1.2rem;margin-bottom:1rem;">
            <p style="color:#E8F5E2;font-size:1.2rem;margin:0;">🌿 खेती विशेषज्ञ सल्लाह</p>
            <p style="color:#A8C5A0;font-size:0.8rem;margin:0;">प्रमाणित कृषि विशेषज्ञहरूसँग सम्पर्क गर्नुहोस्</p>
        </div>
        """, unsafe_allow_html=True)
        for icon, label, value in [
            ("📞","फोन / Call","+977-01-00000"),
            ("🕐","उपलब्ध समय","आइत – शुक्र, बिहान ९ – साँझ ५"),
            ("📍","कार्यालय","काठमाडौं, नेपाल"),
        ]:
            st.markdown(f"""
            <div style="background:#F0F7EE;border:1px solid #D4E8CC;border-radius:12px;
            padding:0.9rem 1.1rem;margin-bottom:0.6rem;display:flex;align-items:center;gap:0.9rem;">
                <div style="width:38px;height:38px;background:#2D5A3D;border-radius:10px;
                display:flex;align-items:center;justify-content:center;font-size:1.1rem;">{icon}</div>
                <div>
                    <div style="font-size:0.7rem;color:#6B8F6B;font-weight:600;">{label}</div>
                    <div style="font-size:0.9rem;color:#1A3526;font-weight:600;">{value}</div>
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#FFF8E6;border-left:3px solid #F5A623;border-radius:0 10px 10px 0;
        padding:0.8rem 1rem;font-size:0.82rem;color:#7A5500;margin-top:0.8rem;">
        💡 विशेषज्ञसँग कुरा गर्नु अघि रोगको नाम र फोटो तयार राख्नुहोस्।
        </div>""", unsafe_allow_html=True)
        st.markdown("🌐 [www.khetifam.com](https://kheti.farm)")

    # ─────────────────────────────────────────────────────
    # HELPER: Farmer card
    # ─────────────────────────────────────────────────────
    def render_farmer_card(f: dict):
        name         = f.get("name", "Unknown")
        crop         = f.get("crop", "N/A").title()
        ftype        = f.get("farmer_type", "?")
        district     = f.get("district", "N/A").title()
        zone         = f.get("zone", "N/A")
        land         = f.get("land_size_hectares", 0)
        income       = f.get("estimated_income_npr", 0)
        yield_kg     = f.get("estimated_yield_kg", 0)
        exp          = f.get("experience_years", 0)
        risk         = f.get("risk_level", "medium").lower()
        score        = f.get("credit_score", 0)
        rec          = f.get("recommendation", "N/A").lower()
        max_loan     = f.get("max_safe_loan_npr", 0)
        headroom     = f.get("headroom_npr", 0)
        default_prob = f.get("default_probability", 0)
        irrigation   = f.get("irrigation_type", "N/A").title()
        land_own     = f.get("land_ownership", "N/A").title()
        farming_type = f.get("farming_type", "N/A").title()
        has_loan     = "Yes" if f.get("has_loan", False) else "No"
        season       = f.get("season", "N/A")
        sowing       = f.get("sowing_date_original", "N/A").title()
        note         = f.get("decision_note", "")
        watch_points = f.get("watch_points", [])
        breakdown    = f.get("score_breakdown", {})

        risk_colors = {
            "high":   ("#4c1d24", "#fca5a5", "#ef4444"),
            "medium": ("#451a03", "#fcd34d", "#f59e0b"),
            "low":    ("#052e16", "#6ee7b7", "#10b981"),
        }
        rbg, rfg, rbd = risk_colors.get(risk, risk_colors["medium"])

        # ── FIXED: approve / review / decline (not reject) ──
        rec_colors = {"approve": "#10b981", "review": "#f59e0b", "decline": "#ef4444"}
        rec_icons  = {"approve": "✅",       "review": "⚠️",      "decline": "❌"}
        rec_color  = rec_colors.get(rec, "#9ca3af")
        rec_icon   = rec_icons.get(rec, "❓")

        score_border = "#ef4444" if score < 40 else ("#f59e0b" if score < 65 else "#10b981")
        score_color  = "#fca5a5" if score < 40 else ("#fcd34d" if score < 65 else "#6ee7b7")

        # Score breakdown bars — matched to actual scorer fields (no income_score)
        bar_defs = [
            ("dti_score",        "DTI",        35, "#34d399"),
            ("irrigation_score", "Irrigation", 20, "#a78bfa"),
            ("land_score",       "Land",       20, "#f472b6"),
            ("experience_score", "Experience", 15, "#fb923c"),
            ("crop_score",       "Crop",       10, "#facc15"),
        ]
        bars_html = ""
        for key, label, maximum, color in bar_defs:
            val = breakdown.get(key, 0)
            pct = min(100, int((val / maximum) * 100)) if maximum else 0
            bars_html += f"""
            <div style="margin:3px 0;">
                <div style="font-size:0.68rem;color:#9ca3af;display:flex;justify-content:space-between;">
                    <span>{label}</span><span>{val}/{maximum}</span>
                </div>
                <div style="background:#1f2937;border-radius:4px;height:6px;margin:2px 0 5px 0;overflow:hidden;">
                    <div style="width:{pct}%;height:100%;border-radius:4px;background:{color};"></div>
                </div>
            </div>"""

        watch_html = ""
        for w in watch_points:
            watch_html += f"""
            <div style="background:rgba(245,158,11,0.08);border-left:3px solid #f59e0b;
            border-radius:0 8px 8px 0;padding:0.4rem 0.8rem;font-size:0.78rem;
            color:#fcd34d;margin:4px 0;">⚠ {w}</div>"""

        note_html = ""
        if note:
            note_html = f"""
            <div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);
            border-radius:10px;padding:0.6rem 0.9rem;margin-top:0.8rem;">
                <div style="font-size:0.65rem;color:#a5b4fc;font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;">Decision Note</div>
                <div style="font-size:0.82rem;color:#e0e7ff;margin-top:3px;">{note}</div>
            </div>"""

        watch_section = ""
        if watch_html:
            watch_section = f"""
            <div style="margin-top:0.8rem;">
                <div style="font-size:0.65rem;color:#fcd34d;font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:0.3rem;">Watch Points</div>
                {watch_html}
            </div>"""

        def badge(label, value, size="1.05rem"):
            return f"""
            <div style="background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);
            border-radius:10px;padding:0.55rem 0.9rem;text-align:center;margin:0.3rem;display:inline-block;min-width:100px;">
                <div style="font-size:0.65rem;color:#6ee7b7;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;">{label}</div>
                <div style="font-size:{size};color:#ecfdf5;font-weight:700;font-family:monospace;margin-top:2px;">{value}</div>
            </div>"""

        html = f"""
        <!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&display=swap" rel="stylesheet">
        <style>body {{ margin:0; padding:0; background:transparent; font-family:'Sora',sans-serif; }}</style>
        </head><body>
        <div style="background:linear-gradient(145deg,#0f2027,#1a3a2e,#0f2027);
            border:1px solid rgba(52,211,153,0.2);border-radius:20px;padding:1.5rem;
            margin-bottom:0.5rem;position:relative;overflow:hidden;">

            <div style="position:absolute;top:0;left:0;right:0;height:3px;
            background:linear-gradient(90deg,#34d399,#059669,#10b981);"></div>

            <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">
                <div>
                    <div style="font-size:1.25rem;font-weight:700;color:#ecfdf5;margin:0;">
                        {name}
                        <span style="background:linear-gradient(135deg,#059669,#047857);color:white;
                        border-radius:6px;padding:2px 10px;font-size:0.7rem;font-weight:700;
                        letter-spacing:0.05em;margin-left:8px;">TYPE {ftype}</span>
                    </div>
                    <div style="font-size:0.78rem;color:#6ee7b7;margin:4px 0 0.8rem 0;">
                        🌾 {crop} &nbsp;|&nbsp; 📍 {district}, {zone} &nbsp;|&nbsp; 🗓 {season} — {sowing}
                    </div>
                    <div style="display:flex;flex-wrap:wrap;gap:0.4rem;align-items:center;margin-bottom:0.6rem;">
                        <span style="background:{rbg};color:{rfg};border:1px solid {rbd};
                        border-radius:20px;padding:3px 12px;font-size:0.78rem;font-weight:700;">
                            🔴 {risk.upper()} RISK
                        </span>
                        <span style="background:rgba(255,255,255,0.05);border:1px solid {rec_color};
                        color:{rec_color};border-radius:20px;padding:3px 12px;font-size:0.78rem;font-weight:700;">
                            {rec_icon} {rec.upper()}
                        </span>
                    </div>
                </div>
                <div style="text-align:center;">
                    <div style="width:70px;height:70px;border-radius:50%;display:flex;align-items:center;
                    justify-content:center;font-family:monospace;font-size:1.3rem;font-weight:700;
                    border:3px solid {score_border};color:{score_color};background:#0f2027;
                    margin:0 auto 0.4rem auto;">{score}</div>
                    <div style="font-size:0.65rem;color:#6ee7b7;font-weight:600;text-transform:uppercase;">Credit Score</div>
                </div>
            </div>

            <div style="display:flex;flex-wrap:wrap;margin:-0.3rem;">
                {badge("Land (ha)", f"{land:.4f}")}
                {badge("Income (NPR)", f"Rs.{income:,.0f}", "0.85rem")}
                {badge("Yield (kg)", f"{yield_kg:,.0f}")}
                {badge("Max Loan", f"Rs.{max_loan:,.0f}", "0.85rem")}
                {badge("Headroom", f"Rs.{headroom:,.0f}", "0.85rem")}
                {badge("Default %", f"{default_prob*100:.0f}%")}
                {badge("Experience", f"{exp} yrs")}
                {badge("Irrigation", irrigation, "0.82rem")}
                {badge("Land Own", land_own, "0.82rem")}
                {badge("Farming", farming_type, "0.82rem")}
                {badge("Has Loan", has_loan)}
            </div>

            <div style="margin-top:1rem;">
                <div style="font-size:0.7rem;color:#6ee7b7;font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:0.4rem;">Score Breakdown</div>
                {bars_html}
            </div>

            {note_html}
            {watch_section}
        </div>
        </body></html>"""

        components.html(html, height=620, scrolling=False)


    # ═══════════════════════════════════════════════════════
    # PAGE: CHAT  (regular users only)
    # ═══════════════════════════════════════════════════════
    if page == "Chat":
        st.subheader("💬 Chat with KrishiMitra")

        def parse_suggestions(content):
            if "SUGGESTIONS:" in content:
                parts = content.split("SUGGESTIONS:")
                return parts[0].strip(), [s.strip() for s in parts[1].split("|")]
            return content, []

        for i, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                if msg.get("image"):
                    st.image(msg["image"], width=200)
                if msg["role"] == "assistant":
                    main_content, suggestions = parse_suggestions(msg["content"])
                    st.markdown(main_content)
                    if suggestions and i >= len(st.session_state.messages) - 2:
                        st.markdown("---")
                        expert_chip = "👨‍🌾 विशेषज्ञ सल्लाह चाहिन्छ?"
                        all_chips   = suggestions + [expert_chip]
                        cols        = st.columns(len(all_chips))
                        for j, suggestion in enumerate(all_chips):
                            with cols[j]:
                                key = f"sug_{hash(msg['content'])}_{j}"
                                if suggestion == expert_chip:
                                    if st.button(suggestion, key=key, use_container_width=True):
                                        st.session_state.show_expert = True
                                        st.rerun()
                                else:
                                    if st.button(suggestion, key=key, use_container_width=True):
                                        st.session_state.pending_prompt = suggestion
                                        st.rerun()
                else:
                    st.markdown(msg["content"])

        prompt = st.chat_input("Type your farming question here...")
        if st.session_state.pending_prompt:
            prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                try:
                    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                    response = requests.post(f"{API_URL}/chat", json={"message": prompt}, headers=headers)
                    if response.status_code == 200:
                        reply = response.json().get("reply","")
                    elif response.status_code == 401:
                        st.error("Session expired."); st.session_state.access_token = None; reply = ""
                    else:
                        st.error(f"Error from backend API: {response.text}")
                        reply = ""

                    # if reply:
                    #     st.markdown(reply)
                    #     st.session_state.messages.append({"role": "assistant", "content": reply})
                    if reply:
                        main_content, suggestions = parse_suggestions(reply)
                        st.markdown(main_content)
                        
                        if suggestions:
                            st.markdown("---")
                            expert_chip = "👨‍🌾 विशेषज्ञ सल्लाह चाहिन्छ?"
                            all_chips = suggestions + [expert_chip]
                            cols = st.columns(len(all_chips))
                            for j, suggestion in enumerate(all_chips):
                                with cols[j]:
                                    if suggestion == expert_chip:
                                        if st.button(suggestion, key=f"live_expert_{j}"):
                                            st.session_state.show_expert = True
                                            st.rerun()
                                    else:
                                        if st.button(suggestion, key=f"live_sug_{j}"):
                                            st.session_state.pending_prompt = suggestion
                                            st.rerun()
                        
                        st.session_state.messages.append({"role": "assistant", "content": reply})


                except Exception as e:
                    st.error("Failed to connect to the KrishiMitra backend.")

        st.session_state.page = page

        if st.session_state.show_expert and page != "Expert Panel":
            render_expert_panel()
            if st.button("← बातचितमा फर्कनुहोस्"):
                st.session_state.show_expert = False
                st.rerun()

    # ═══════════════════════════════════════════════════════
    # PAGE: DASHBOARD  (regular users only)
    # ═══════════════════════════════════════════════════════
    elif page == "Dashboard":
        st.subheader("📊 Crop & Farm Dashboard")
        col1, col2 = st.columns(2)
        with col1:
            month_names = {
                "Baisakh (1)":1,"Jestha (2)":2,"Ashadh (3)":3,"Shrawan (4)":4,
                "Bhadra (5)":5,"Ashwin (6)":6,"Kartik (7)":7,"Mangsir (8)":8,
                "Poush (9)":9,"Magh (10)":10,"Falgun (11)":11,"Chaitra (12)":12
            }
            selected_month_label = st.selectbox("📅 Select Month (Nepali)", list(month_names.keys()), index=1)
            selected_month       = month_names[selected_month_label]
        with col2:
            lang_options        = {"Nepali":"ne","English":"en"}
            selected_lang_label = st.selectbox("🌐 Language", list(lang_options.keys()), index=0)
            selected_lang       = lang_options[selected_lang_label]

        st.markdown("---")
        with st.spinner("Loading dashboard data..."):
            season_data = fetch_season(month=selected_month)
            recs_data   = fetch_recommendations(month=selected_month, lang=selected_lang)
            dash_data   = fetch_dashboard(month=selected_month, lang=selected_lang)

        if season_data:
            st.metric("📅 Current Season", season_data.get("season","Unknown"))
        else:
            st.info("Season information not available")
        st.markdown("---")

        if recs_data:
            st.subheader("📋 Verified Recommendations")
            recs_list   = recs_data.get("recommendations",[])
            corrections = recs_data.get("corrections_made",0)
            st.info(f"Total: {len(recs_list)} crops | LLM corrections: {corrections}")
            for i, crop in enumerate(recs_list, 1):
                with st.expander(f"#{i} - {crop.get('crop_name_en', crop.get('crop_key','Unknown'))}"):
                    c1,c2,c3 = st.columns(3)
                    with c1:
                        st.write(f"**Crop Key:** {crop.get('crop_key','N/A')}")
                        st.write(f"**Nepali Name:** {crop.get('crop_name_ne','N/A')}")
                    with c2:
                        st.write(f"**Risk Tier:** {crop.get('risk_tier','N/A')}")
                        st.write(f"**Opportunity Score:** {crop.get('opportunity_score','N/A')}/10")
                    with c3:
                        st.write(f"**Corrected:** {'Yes' if crop.get('was_corrected') else 'No'}")
                        st.write(f"**Plant Timing:** {crop.get('plant_timing','N/A')}")
                    st.write(f"**Planting Window (EN):** {crop.get('planting_en','N/A')}")
                    st.write(f"**Planting Window (NE):** {crop.get('planting_ne','N/A')}")
                    st.write(f"**Forecast Price:** {crop.get('forecasted_price','N/A')}")
        else:
            st.warning("Could not fetch recommendations")
        st.markdown("---")

        if dash_data:
            st.subheader("🌾 Seasonal Crop Cards")
            cards = dash_data.get("cards",[])
            st.info(f"Total seasonal crops: {dash_data.get('total',0)}")
            for i, card in enumerate(cards, 1):
                with st.expander(f"Card #{i} - {card.get('crop_name_en', card.get('crop_key','Unknown'))}"):
                    c1,c2 = st.columns(2)
                    with c1:
                        st.write(f"**Crop Key:** {card.get('crop_key','N/A')}")
                        st.write(f"**English Name:** {card.get('crop_name_en','N/A')}")
                        st.write(f"**Nepali Name:** {card.get('crop_name_ne','N/A')}")
                    with c2:
                        st.write(f"**Planting Status:** {card.get('planting_status','N/A')}")
                        st.write(f"**Risk Level:** {card.get('risk_level','N/A')}")
                        st.write(f"**Market Price:** {card.get('market_price','N/A')}")
                    st.write(f"**Description (EN):** {card.get('description_en','N/A')}")
                    st.write(f"**Description (NE):** {card.get('description_ne','N/A')}")
        else:
            st.warning("Could not fetch dashboard cards")

    # ═══════════════════════════════════════════════════════
    # PAGE: EXPERT PANEL  (regular users only)
    # ═══════════════════════════════════════════════════════
    elif page == "Expert Panel":
        st.subheader("🌿 Expert Panel - Agricultural Experts")
        render_expert_panel()

    # ═══════════════════════════════════════════════════════
    # PAGE: ADMIN — FARMER PROFILES  (admin only)
    # ═══════════════════════════════════════════════════════
    elif page == "👑 Admin — Farmer Profiles":

        st.markdown("""
        <div class="admin-header">
            <h2>👑 Farmer Profile Dashboard</h2>
            <p>Complete credit profiles, risk scores and loan assessments for all registered farmers.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Loading farmer profiles..."):
            farmers = fetch_all_farmers(st.session_state.access_token)

        if not farmers:
            st.info("No farmer data returned from the API. Showing a demo profile below.")
            farmers = [{
                "name": "Shyam Karki", "farmer_type": "A", "crop": "tomato",
                "district": "mahottari", "zone": "Terai", "season": "Spring",
                "sowing_date_original": "Jestha", "land_size_hectares": 0.0497,
                "estimated_income_npr": 68383.22, "estimated_yield_kg": 1292.2,
                "experience_years": 2, "risk_level": "high", "credit_score": 41,
                "recommendation": "decline", "max_safe_loan_npr": 390761,
                "headroom_npr": 390761, "default_probability": 0.22,
                "irrigation_type": "canal", "land_ownership": "leased",
                "farming_type": "organic", "has_loan": False,
                "decision_note": "High risk. Reduce loan amount or require collateral/group guarantee.",
                "watch_points": [
                    "Tomato price volatile — recommend crop insurance",
                    "Leased land — no collateral available for recovery"
                ],
                "score_breakdown": {
                    "dti_score": 18, "irrigation_score": 12, "land_score": 2,
                    "experience_score": 8, "crop_score": 1,
                    "total": 41, "max_possible": 100
                }
            }]

        # ── Summary metrics ────────────────────────────────
        total        = len(farmers)
        avg_score    = sum(f.get("credit_score", 0) for f in farmers) / total if total else 0
        high_risk    = sum(1 for f in farmers if f.get("risk_level","").lower() == "high")
        approved     = sum(1 for f in farmers if f.get("recommendation","").lower() == "approve")
        review_count = sum(1 for f in farmers if f.get("recommendation","").lower() == "review")
        # ── FIXED: count decline (not reject) ──
        declined     = sum(1 for f in farmers if f.get("recommendation","").lower() == "decline")
        total_income = sum(f.get("estimated_income_npr", 0) for f in farmers)

        m1,m2,m3,m4,m5,m6,m7 = st.columns(7)
        for col, label, val, sub in [
            (m1, "Total Farmers",    str(total),              "registered"),
            (m2, "Avg Credit Score", f"{avg_score:.0f}",      "out of 100"),
            (m3, "High Risk",        str(high_risk),          "need attention"),
            (m4, "Approved",         str(approved),           "loan eligible"),
            (m5, "Under Review",     str(review_count),       "need assessment"),
            (m6, "Declined",         str(declined),           "not eligible"),
            (m7, "Est. Income",      f"Rs.{total_income:,.0f}", "combined NPR"),
        ]:
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="m-label">{label}</div>
                    <div class="m-value">{val}</div>
                    <div class="m-sub">{sub}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Filters ────────────────────────────────────────
        with st.expander("🔍 Filter Profiles", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns(4)
            # ── FIXED: all three risk values selected by default ──
            with fc1:
                f_risk = st.multiselect(
                    "Risk Level",
                    ["high", "medium", "low"],
                    default=["high", "medium", "low"],
                )
            # ── FIXED: approve / review / decline (not reject) ──
            with fc2:
                f_rec = st.multiselect(
                    "Recommendation",
                    ["approve", "review", "decline"],
                    default=["approve", "review", "decline"],
                )
            with fc3:
                f_type = st.multiselect("Farmer Type", ["A", "B"], default=["A", "B"])
            with fc4:
                f_crop = st.text_input("Crop", placeholder="e.g. tomato")

        # ── FIXED: normalise both sides of comparison so case never breaks filter ──
        filtered = [
            f for f in farmers
            if f.get("risk_level", "").lower().strip() in f_risk
            and f.get("recommendation", "").lower().strip() in f_rec
            and (not f_type or f.get("farmer_type", "") in f_type)
            and (not f_crop or f_crop.lower() in f.get("crop", "").lower())
        ]

        st.markdown(f"**Showing {len(filtered)} of {total} farmers**")
        st.markdown("---")

        if not filtered:
            st.warning("No farmers match the current filters.")
        else:
            for farmer in filtered:
                render_farmer_card(farmer)