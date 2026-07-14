import re

with open('streamlit_app.py', 'r') as f:
    code = f.read()

# Replace the duplicated blocks with the clean version
old = """    # ═════════════════════════════════════════════════════════
    # PAGE: EXPERT PANEL
    # ═════════════════════════════════════════════════════════
    elif page == "Expert Panel":
        st.subheader("🌿 Expert Panel - Agricultural Experts")

        st.markdown(\"""
        <div style="background:linear-gradient(135deg,#1A3526,#2D5A3D);
        border-radius:16px;padding:1.2rem;margin-bottom:1rem;">
            <p style="color:#E8F5E2;font-size:1.2rem;margin:0;">🌿 खेती विशेषज्ञ सल्लाह</p>
            <p style="color:#A8C5A0;font-size:0.8rem;margin:0;">प्रमाणित कृषि विशेषज्ञहरूसँग सम्पर्क गर्नुहोस्</p>
        </div>
        \""", unsafe_allow_html=True)

        contacts = [
            ("📞", "फोन / Call", "+977-01-4211685"),
            ("🕐", "उपलब्ध समय", "आइत – शुक्र, बिहान ९ – साँझ ५"),
            ("��", "कार्यालय", "काठमाडौं, नेपाल"),
        ]
        for icon, label, value in contacts:
            st.markdown(f\"""
            <div style="background:#F0F7EE;border:1px solid #D4E8CC;border-radius:12px;
            padding:0.9rem 1.1rem;margin-bottom:0.6rem;
            display:flex;align-items:center;gap:0.9rem;">
                <div style="width:38px;height:38px;background:#2D5A3D;border-radius:10px;
                display:flex;align-items:center;justify-content:center;font-size:1.1rem;">{icon}</div>
                <div>
                    <div style="font-size:0.7rem;color:#6B8F6B;font-weight:600;">{label}</div>
                    <div style="font-size:0.9rem;color:#1A3526;font-weight:600;">{value}</div>
                </div>
            </div>
            \""", unsafe_allow_html=True)

        st.markdown(\"""
        <div style="background:#FFF8E6;border-left:3px solid #F5A623;
        border-radius:0 10px 10px 0;padding:0.8rem 1rem;
        font-size:0.82rem;color:#7A5500;margin-top:0.8rem;">
        💡 विशेषज्ञसँग कुरा गर्नु अघि रोगको नाम र फोटो तयार राख्नुहोस्।
        </div>
        \""", unsafe_allow_html=True)
        st.markdown("🌐 [www.narc.gov.np](http://www.narc.gov.np)")

    # ── Show Expert Panel (modal) ──────────────────────────────
    if st.session_state.show_expert:
        st.markdown(\"""
        <div style="background:linear-gradient(135deg,#1A3526,#2D5A3D);
        border-radius:16px;padding:1.2rem;margin-bottom:1rem;">
            <p style="color:#E8F5E2;font-size:1.2rem;margin:0;">🌿 खेती विशेषज्ञ सल्लाह</p>
            <p style="color:#A8C5A0;font-size:0.8rem;margin:0;">प्रमाणित कृषि विशेषज्ञहरूसँग सम्पर्क गर्नुहोस्</p>
        </div>
        \""", unsafe_allow_html=True)

        contacts = [
            ("📞", "फोन / Call", "+977-01-4211685"),
            ("🕐", "उपलब्ध समय", "आइत – शुक्र, बिहान ९ – साँझ ५"),
            ("��", "कार्यालय", "काठमाडौं, नेपाल"),
        ]
        for icon, label, value in contacts:
            st.markdown(f\"""
            <div style="background:#F0F7EE;border:1px solid #D4E8CC;border-radius:12px;
            padding:0.9rem 1.1rem;margin-bottom:0.6rem;
            display:flex;align-items:center;gap:0.9rem;">
                <div style="width:38px;height:38px;background:#2D5A3D;border-radius:10px;
                display:flex;align-items:center;justify-content:center;font-size:1.1rem;">{icon}</div>
                <div>
                    <div style="font-size:0.7rem;color:#6B8F6B;font-weight:600;">{label}</div>
                    <div style="font-size:0.9rem;color:#1A3526;font-weight:600;">{value}</div>
                </div>
            </div>
            \""", unsafe_allow_html=True)

        st.markdown(\"""
        <div style="background:#FFF8E6;border-left:3px solid #F5A623;
        border-radius:0 10px 10px 0;padding:0.8rem 1rem;
        font-size:0.82rem;color:#7A5500;margin-top:0.8rem;">
        💡 विशेषज्ञसँग कुरा गर्नु अघि रोगको नाम र फोटो तयार राख्नुहोस्।
        </div>
        \""", unsafe_allow_html=True)
        st.markdown("🌐 [www.narc.gov.np](http://www.narc.gov.np)")

        if st.button("← बातचितमा फर्कनुहोस्"):
            st.session_state.show_expert = False
            st.rerun()"""

new = """    # ═════════════════════════════════════════════════════════
    # PAGE: EXPERT PANEL
    # ═════════════════════════════════════════════════════════
    elif page == "Expert Panel":
        st.subheader("🌿 Expert Panel - Agricultural Experts")
        render_expert_panel()

    # ── Show Expert Panel (modal) ──────────────────────────────
    if st.session_state.show_expert and page != "Expert Panel":
        render_expert_panel()
        if st.button("← बातचितमा फर्कनुहोस्"):
            st.session_state.show_expert = False
            st.rerun()"""

# Do regex replacement to handle any whitespace issues
import re
new_code = re.sub(r'    # ═════════════════════════════════════════════════════════\n    # PAGE: EXPERT PANEL.*?st\.rerun\(\)', new, code, flags=re.DOTALL)

with open('streamlit_app.py', 'w') as f:
    f.write(new_code)
print("Done fixing export panel")
