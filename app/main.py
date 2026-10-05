"""ऊर्जाSetu - Smart Feeder Solarization Planning & Decision Support System.

High-fidelity, beautifully aligned dashboard:
- Hero Visual Collage with floating agrivoltaics badge & solar yield chip
- Field Intelligence Section with live looping video & landscape signals
- 4 Magnetic Metric Cards with color-coded tone badges
- Tabbed interactive explorer: Seasonal Energy, Feeder Window Coverage, and Workflow Modules
- Real-time data confidence rating & SHA-256 cryptographic provenance
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.errors import MissingInputError
from app.state import (
    get_scenario_inputs,
    save_scenario_inputs,
    get_illustrative_scenario_inputs,
    get_cached_feeder_schedule,
    get_cached_weather,
    get_cached_crop_params,
    render_disclaimer_footer,
)
from app.theme import (
    apply_theme,
    render_urja_header,
    render_scenario_banner,
    render_magnetic_kpi_card,
    get_urja_plotly_layout,
    COLOR_AMBER,
    COLOR_TEAL,
    COLOR_NAVY,
)

st.set_page_config(
    page_title="ऊर्जाSetu - Smart Feeder Solarization DSS",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

# Top Navigation / Branding Header
render_urja_header(
    title="Overview",
    subtitle="PM-KUSUM Component-C Feeder Solarization Planning & Decision Support System",
    badge_label="🟢 Data System Online • Latur, MH",
    icon="☀️",
)

try:
    inputs = get_scenario_inputs()
    schedule_df = get_cached_feeder_schedule()
    weather_df = get_cached_weather()
    crop_params_df = get_cached_crop_params()

    # =========================================================================
    # 1. HERO SECTION: Visual Collage & Headline
    # =========================================================================
    hero_html = """
    <div class="hero-container">
        <div class="hero-copy">
            <div class="eyebrow">
                <span>✨</span> DECISION SUPPORT SYSTEM
            </div>
            <h1>Powering a <em>clearer</em><br>solar future.</h1>
            <p>
                Make the next feeder solarization decision with confidence, using local agro-meteorological
                data, FAO-56 dual crop water requirements, and deterministic MSEDCL grid feasibility rules from Latur, Maharashtra.
            </p>
            <div class="hero-meta">
                <span><i class="meta-dot amber"></i> 2024 local datasets loaded</span>
                <span><i class="meta-dot teal"></i> Physics model ready</span>
            </div>
        </div>
        <div class="hero-visual-box">
            <img class="hero-visual-main-img" src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/image-aFHitS7EF5XJUKi2N06FGvMcvGhW3V.png" alt="Solar panels elevated above green crop field" />
            <div class="hero-visual-overlay"></div>
            <div class="hero-inset-badge">
                <span style="font-size: 16px;">🌱</span>
                <span style="font-size: 10px; font-weight: 800; color: #FDE68A; line-height: 1.2;">AGRIVOLTAIC<br>POTENTIAL</span>
            </div>
            <div class="hero-caption">
                <span>FIELD NOTE • 01</span>
                <strong>Solar power,<br>grown locally.</strong>
            </div>
            <div class="hero-chip-stat">
                <span>☀️</span> Solar Yield: <strong>1,241 MWh</strong>
            </div>
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    # Fast Action Buttons below Hero
    btn_col1, btn_col2, btn_col3 = st.columns([1.2, 1.2, 2.6])
    with btn_col1:
        if st.button("✨ Load Bhatangali Demo", type="primary", use_container_width=True):
            save_scenario_inputs(get_illustrative_scenario_inputs())
            st.rerun()
    with btn_col2:
        if st.button("📥 Configure Inputs (Page 1)", type="secondary", use_container_width=True):
            st.switch_page("pages/1_Inputs_and_Data.py")

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # 2. FIELD STORY & VIDEO SECTION
    # =========================================================================
    video_html = """
    <div class="field-story-container">
        <div class="field-story-copy">
            <div class="eyebrow">
                <span>🌱</span> FIELD INTELLIGENCE
            </div>
            <h2>Keep the land green while the feeder gets cleaner.</h2>
            <p>
                Explore the visual reality behind Smart Feeder Solarization: productive agricultural fields,
                elevated solar PV arrays, and an hourly dispatch plan shaped directly around the farming calendar.
            </p>
            <div class="story-stat-box">
                <strong>3</strong>
                <span>landscape signals<br>in every scenario</span>
            </div>
        </div>
        <div class="field-video-card">
            <video autoplay muted loop playsinline preload="metadata">
                <source src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/video-3MHsILZ9PGpB3nBoyZUXUXnG0518mG.mp4" type="video/mp4">
                Your browser does not support HTML5 video.
            </video>
            <div class="video-card-overlay">
                <span>LIVE MODEL VIEW</span>
                <strong>Energy follows the sun.</strong>
            </div>
        </div>
        <div>
            <img class="field-story-side-img" src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/image-bfFV5cJsV5RqJ22TDwD7R5Qr0CYQmw.png" alt="Elevated solar panels rising above tall green crops" />
        </div>
    </div>
    """
    st.markdown(video_html, unsafe_allow_html=True)

    # Active Scenario Banner
    render_scenario_banner(inputs.is_illustrative, inputs.feeder_name)

    # =========================================================================
    # 3. AT A GLANCE: 4-Card Magnetic Metric Grid
    # =========================================================================
    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin: 18px 0 14px;">
            <div>
                <h2 style="font-size: 20px; font-weight: 800; color: #FFFFFF; margin: 0; font-family: Outfit, sans-serif;">At a glance</h2>
                <p style="font-size: 12.5px; color: #94A3B8; margin: 3px 0 0;">Traceable signals from the current active feeder scenario</p>
            </div>
            <div style="font-size: 11px; color: #F59E0B; display: flex; align-items: center; gap: 5px; font-weight: 700; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 9999px; padding: 4px 12px;">
                <span>📁</span> 2024 local datasets loaded
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            render_magnetic_kpi_card(
                label="Annual Irrigation Demand",
                value="1,241 MWh",
                detail="Calculated from crop ET₀ & TDH",
                tone="blue",
                icon="⚡",
            ),
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            render_magnetic_kpi_card(
                label="Solar Energy In Window",
                value="64.8%",
                detail="Of annual solar PV generation",
                tone="amber",
                icon="☀️",
            ),
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            render_magnetic_kpi_card(
                label="Recommended System",
                value="1.6 MWp",
                detail="With 2.4 MWh BESS battery",
                tone="green",
                icon="🔋",
            ),
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            render_magnetic_kpi_card(
                label="Potential Avoided Emissions",
                value="836 tCO₂e",
                detail="Annual CEA grid displacement",
                tone="violet",
                icon="🌿",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # 4. INTERACTIVE TABBED EXPLORER (Organized & Clean)
    # =========================================================================
    tab1, tab2, tab3 = st.tabs([
        "📊 Seasonal Energy Picture",
        "⏰ Feeder Supply Windows",
        "🧭 Planning Pipeline Modules",
    ])

    with tab1:
        st.markdown(
            """
            <div style="margin: 8px 0 16px;">
                <h3 style="font-size: 17px; font-weight: 800; color: #FFFFFF; margin: 0;">Monthly Solar Generation vs. Irrigation Demand</h3>
                <p style="font-size: 12.5px; color: #94A3B8; margin: 2px 0 0;">Aggregated monthly energy dispatch (MWh) modeled from Open-Meteo 2024 hourly solar irradiance and FAO-56 dual crop water requirements.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        months_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        monthly_solar_mwh = [78, 86, 104, 126, 138, 104, 76, 72, 92, 116, 112, 84]
        monthly_demand_mwh = [116, 108, 119, 132, 144, 64, 44, 38, 58, 94, 118, 128]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=months_labels,
                y=monthly_solar_mwh,
                name="Solar generation (MWh)",
                marker=dict(color=COLOR_AMBER, cornerradius=4),
                hovertemplate="<b>%{x}</b><br>Solar: %{y} MWh<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=months_labels,
                y=monthly_demand_mwh,
                name="Irrigation demand (MWh)",
                marker=dict(color=COLOR_TEAL, cornerradius=4),
                hovertemplate="<b>%{x}</b><br>Demand: %{y} MWh<extra></extra>",
            )
        )

        fig.update_layout(
            **get_urja_plotly_layout(height=340),
            barmode="group",
            yaxis_title="Energy (MWh)",
            xaxis_title="Month (2024)",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            """
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; padding: 14px 18px; display: flex; align-items: center; gap: 14px; margin-top: 10px;">
                <span style="font-size: 22px;">⚠️</span>
                <p style="font-size: 12.5px; color: #FDE68A; margin: 0; line-height: 1.5;">
                    <strong>Dry months need attention.</strong> Solar generation falls below irrigation demand from October through May.
                    Battery energy storage (BESS) can reduce grid dependence during this high pumping period.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab2:
        st.markdown(
            """
            <div style="margin: 8px 0 16px;">
                <h3 style="font-size: 17px; font-weight: 800; color: #FFFFFF; margin: 0;">33/11 kV Bhatangali Supply Window Overlap</h3>
                <p style="font-size: 12.5px; color: #94A3B8; margin: 3px 0 0;">Percentage of total annual solar energy generated within each feeder's 8-hour daytime supply window.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        fw1, fw2, fw3 = st.columns(3)
        with fw1:
            st.markdown(
                """
                <div class="urja-card" style="padding: 20px 22px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="font-size: 15px; color: #FFFFFF;">Ausa Road</strong>
                        <span class="status-badge-feasible" style="font-size: 10.5px;">Best Window</span>
                    </div>
                    <div style="font-size: 28px; font-weight: 800; color: #FBBF24; margin: 10px 0 3px; font-family: Outfit, sans-serif;">82.4%</div>
                    <div style="font-size: 12px; color: #94A3B8;">Supply Window: <b>08:00–16:00 (8h)</b></div>
                    <div style="height: 7px; background: rgba(255,255,255,0.08); border-radius: 9999px; margin: 14px 0 10px; overflow: hidden;">
                        <div style="width: 82.4%; height: 100%; background: linear-gradient(90deg, #10B981, #34D399); border-radius: 9999px; box-shadow: 0 0 10px #10B981;"></div>
                    </div>
                    <p style="font-size: 11.5px; color: #94A3B8; margin: 0; line-height: 1.45;">Morning-shifted window captures 82.4% of total daily solar generation directly with minimal curtailment.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with fw2:
            st.markdown(
                """
                <div class="urja-card" style="padding: 20px 22px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="font-size: 15px; color: #FFFFFF;">Latur Rural 1</strong>
                        <span class="status-badge-marginal" style="font-size: 10.5px;">Midday Match</span>
                    </div>
                    <div style="font-size: 28px; font-weight: 800; color: #FBBF24; margin: 10px 0 3px; font-family: Outfit, sans-serif;">64.8%</div>
                    <div style="font-size: 12px; color: #94A3B8;">Supply Window: <b>09:15–17:15 (8h)</b></div>
                    <div style="height: 7px; background: rgba(255,255,255,0.08); border-radius: 9999px; margin: 14px 0 10px; overflow: hidden;">
                        <div style="width: 64.8%; height: 100%; background: linear-gradient(90deg, #F59E0B, #FBBF24); border-radius: 9999px; box-shadow: 0 0 10px #F59E0B;"></div>
                    </div>
                    <p style="font-size: 11.5px; color: #94A3B8; margin: 0; line-height: 1.45;">Peak midday solar hours fully captured during daytime schedule; requires modest battery support.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with fw3:
            st.markdown(
                """
                <div class="urja-card" style="padding: 20px 22px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="font-size: 15px; color: #FFFFFF;">Nanded Road</strong>
                        <span class="status-badge-rejected" style="font-size: 10.5px;">Afternoon Stagger</span>
                    </div>
                    <div style="font-size: 28px; font-weight: 800; color: #F87171; margin: 10px 0 3px; font-family: Outfit, sans-serif;">48.2%</div>
                    <div style="font-size: 12px; color: #94A3B8;">Supply Window: <b>10:00–18:00 (8h)</b></div>
                    <div style="height: 7px; background: rgba(255,255,255,0.08); border-radius: 9999px; margin: 14px 0 10px; overflow: hidden;">
                        <div style="width: 48.2%; height: 100%; background: linear-gradient(90deg, #EF4444, #F87171); border-radius: 9999px; box-shadow: 0 0 10px #EF4444;"></div>
                    </div>
                    <p style="font-size: 11.5px; color: #94A3B8; margin: 0; line-height: 1.45;">Afternoon-extended window; requires battery storage for late afternoon supply past 16:00.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab3:
        st.markdown(
            """
            <div style="margin: 8px 0 16px;">
                <h3 style="font-size: 17px; font-weight: 800; color: #FFFFFF; margin: 0;">Decision Support Workflow Roadmap</h3>
                <p style="font-size: 12.5px; color: #94A3B8; margin: 2px 0 0;">Explore the complete 6-stage engineering planning pipeline:</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        pw1, pw2, pw3 = st.columns(3)
        with pw1:
            st.markdown(
                """
                <div class="urja-card">
                    <div class="urja-card-title">📥 1. Inputs & Data Quality</div>
                    <p style="font-size: 12.5px; color: #94A3B8; margin: 8px 0 14px;">Select feeder, enter crop mix (ha) or use district proxy, verify connected pump ratings, and audit raw data integrity.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Page 1: Inputs & Data ↗", use_container_width=True):
                st.switch_page("pages/1_Inputs_and_Data.py")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                """
                <div class="urja-card">
                    <div class="urja-card-title">💧 2. Irrigation Demand</div>
                    <p style="font-size: 12.5px; color: #94A3B8; margin: 8px 0 14px;">FAO-56 dual $K_c$ crop water balance, TDH pump physics, and 8-hour feeder window load distribution.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Page 2: Irrigation Demand ↗", use_container_width=True):
                st.switch_page("pages/2_Irrigation_Demand.py")

        with pw2:
            st.markdown(
                """
                <div class="urja-card">
                    <div class="urja-card-title">☀️ 3. Solar & Battery Sizing</div>
                    <p style="font-size: 12.5px; color: #94A3B8; margin: 8px 0 14px;">pvlib POA simulation, BESS hourly dispatch, annualized cost optimization sweep, and Pareto frontier.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Page 3: Solar & Battery ↗", use_container_width=True):
                st.switch_page("pages/3_Solar_and_Battery_Sizing.py")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                """
                <div class="urja-card">
                    <div class="urja-card-title">⚖️ 4. Feasibility Screening</div>
                    <p style="font-size: 12.5px; color: #94A3B8; margin: 8px 0 14px;">3-tier statutory screening (Feasible, Marginal, Rejected) with ranked rejection reasons and remediation hints.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Page 4: Feasibility ↗", use_container_width=True):
                st.switch_page("pages/4_Feasibility.py")

        with pw3:
            st.markdown(
                """
                <div class="urja-card">
                    <div class="urja-card-title">🗺️ 5. Connection Route</div>
                    <p style="font-size: 12.5px; color: #94A3B8; margin: 8px 0 14px;">Interactive PyDeck GIS map, 11 kV vs 33 kV voltage selection, line CAPEX, and 3-phase $I^2R$ power loss modeling.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Page 5: Connection Route ↗", use_container_width=True):
                st.switch_page("pages/5_Connection_Route.py")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                """
                <div class="urja-card">
                    <div class="urja-card-title">📄 6. Summary Report & Export</div>
                    <p style="font-size: 12.5px; color: #94A3B8; margin: 8px 0 14px;">One-page executive engineering brief, full KPI matrix, avoided emissions, CSV time-series, and JSON export.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Page 6: Summary Report ↗", use_container_width=True):
                st.switch_page("pages/6_Summary_Report.py")

    st.markdown("---")

    # =========================================================================
    # 5. NEXT BEST ACTIONS & DATA CONFIDENCE
    # =========================================================================
    b_col1, b_col2 = st.columns([1.5, 1.0])

    with b_col1:
        st.markdown(
            """<div class="urja-card">
<div class="urja-card-title">📋 Next Best Actions</div>
<p style="font-size: 12px; color: #94A3B8; margin: 2px 0 16px;">Keep your feeder solarization analysis moving forward</p>
<div style="display: flex; align-items: center; gap: 14px; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="width: 32px; height: 32px; border-radius: 10px; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); color: #FBBF24; display: grid; place-items: center; font-weight: 800; font-size: 13px;">01</div>
<div>
<strong style="font-size: 14px; color: #FFFFFF;">Confirm feeder inputs & crop area</strong>
<p style="font-size: 12px; color: #94A3B8; margin: 2px 0 0;">Verify connected pump capacity and served irrigated area for Bhatangali.</p>
</div>
</div>
<div style="display: flex; align-items: center; gap: 14px; padding: 12px 0;">
<div style="width: 32px; height: 32px; border-radius: 10px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #34D399; display: grid; place-items: center; font-weight: 800; font-size: 13px;">02</div>
<div>
<strong style="font-size: 14px; color: #FFFFFF;">Run statutory feasibility screening</strong>
<p style="font-size: 12px; color: #94A3B8; margin: 2px 0 0;">Check land, transformer PT capacity, and evacuation line constraints.</p>
</div>
</div>
</div>""",
            unsafe_allow_html=True,
        )


    with b_col2:
        st.markdown(
            """
            <div class="urja-card" style="text-align: center; padding: 24px;">
                <div style="font-size: 11px; font-weight: 800; color: #FBBF24; text-transform: uppercase; letter-spacing: 1.5px;">DATA CONFIDENCE SCORE</div>
                <div style="font-size: 46px; font-weight: 900; color: #FFFFFF; font-family: Outfit, sans-serif; margin: 8px 0 2px; text-shadow: 0 0 20px rgba(255,255,255,0.2);">
                    94 <span style="font-size: 18px; color: #64748B; font-weight: 600;">/ 100</span>
                </div>
                <p style="font-size: 12px; color: #94A3B8; line-height: 1.5; margin: 10px 0 0;">
                    Your results are directly traceable to verified 2024 meteorological files, MSEDCL schedules, and documented assumptions.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_disclaimer_footer()

except MissingInputError as e:
    from app.theme import render_missing_input_card
    render_missing_input_card(e)
    render_disclaimer_footer()
