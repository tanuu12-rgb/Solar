"""ऊर्जाSetu - Smart Feeder Solarization Planning & Decision Support System.

Rich, modern, dark glassmorphic UI design system:
- Deep obsidian/navy canvas (#0A0F1D / #0F172A) with radiant solar & emerald mesh glows
- Frosted glass cards with glowing border gradients and backdrop blur
- Luminous solar amber (#F59E0B / #FBBF24), electric emerald (#10B981 / #34D399), and cyber blue (#3B82F6)
- Typography: Outfit (bold display), Plus Jakarta Sans (crisp UI), Noto Sans Devanagari
- Micro-interactions, hover glow effects, and modern dark-mode Plotly figures
"""

from __future__ import annotations

import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any, List
import plotly.graph_objects as go
import plotly.express as px

# Brand & Color Tokens
APP_NAME = "ऊर्जाSetu"
APP_SUBTITLE = "Smart Feeder Solarization & Decision Support System"

COLOR_DARK_BG = "#0A0F1D"
COLOR_NAVY = "#0F172A"
COLOR_CARD_BG = "rgba(17, 24, 39, 0.75)"
COLOR_BORDER = "rgba(255, 255, 255, 0.09)"

COLOR_AMBER = "#F59E0B"
COLOR_AMBER_BRIGHT = "#FBBF24"
COLOR_AMBER_GLOW = "rgba(245, 158, 11, 0.25)"
COLOR_AMBER_GRAD = "linear-gradient(135deg, #FBBF24 0%, #F59E0B 50%, #D97706 100%)"

COLOR_TEAL = "#10B981"
COLOR_TEAL_BRIGHT = "#34D399"
COLOR_TEAL_GLOW = "rgba(16, 185, 129, 0.25)"
COLOR_TEAL_GRAD = "linear-gradient(135deg, #34D399 0%, #10B981 100%)"

COLOR_BLUE = "#3B82F6"
COLOR_BLUE_GLOW = "rgba(59, 130, 246, 0.25)"

COLOR_VIOLET = "#8B5CF6"
COLOR_VIOLET_GLOW = "rgba(139, 92, 246, 0.25)"

# Backward-compatible Color Aliases
COLOR_PRIMARY_BLUE = COLOR_BLUE
COLOR_SOLAR_AMBER = COLOR_AMBER
COLOR_AGRI_GREEN = COLOR_TEAL


URJA_RICH_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Noto+Sans+Devanagari:wght@600;700;800&display=swap');

:root {
    --bg-dark: #0A0F1D;
    --card-bg: rgba(17, 24, 39, 0.82);
    --card-hover: rgba(23, 33, 53, 0.92);
    --border: rgba(255, 255, 255, 0.09);
    --border-glow: rgba(245, 158, 11, 0.4);
    --text-main: #F8FAFC;
    --text-muted: #94A3B8;
    --text-dim: #64748B;
    --amber: #F59E0B;
    --amber-bright: #FBBF24;
    --teal: #10B981;
    --teal-bright: #34D399;
    --blue: #3B82F6;
    --violet: #8B5CF6;
}

/* Background Atmosphere & Canvas */
html, body, [data-testid="stAppViewContainer"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--text-main) !important;
    background-color: #0A0F1D !important;
    background-image: 
        radial-gradient(at 90% 10%, rgba(245, 158, 11, 0.12) 0px, transparent 50%),
        radial-gradient(at 10% 30%, rgba(16, 185, 129, 0.09) 0px, transparent 45%),
        radial-gradient(at 80% 80%, rgba(59, 130, 246, 0.08) 0px, transparent 50%),
        radial-gradient(at 20% 90%, rgba(139, 92, 246, 0.07) 0px, transparent 50%) !important;
    background-attachment: fixed !important;
}

[data-testid="stHeader"] {
    background: rgba(10, 15, 29, 0.75) !important;
    backdrop-filter: blur(16px) !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
}

h1, h2, h3, h4, .brand-title, .metric-value, .hero-title {
    font-family: 'Outfit', 'Noto Sans Devanagari', sans-serif !important;
    color: #FFFFFF !important;
    letter-spacing: -0.02em;
}

p, span, label, div {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

/* Container Spacing */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 3.5rem;
    max-width: 1440px;
}

/* Sidebar Custom Styling */
section[data-testid="stSidebar"] {
    background-color: rgba(10, 15, 29, 0.96) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    backdrop-filter: blur(20px) !important;
}

section[data-testid="stSidebar"] .block-container {
    padding-top: 1.4rem;
    padding-left: 1.2rem;
    padding-right: 1.2rem;
}

[data-testid="stSidebarNav"] a {
    border-radius: 10px !important;
    margin: 3px 0 !important;
    padding: 8px 14px !important;
    color: #94A3B8 !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

[data-testid="stSidebarNav"] a:hover {
    color: #FFFFFF !important;
    background: rgba(255, 255, 255, 0.07) !important;
    transform: translateX(4px) !important;
}

[data-testid="stSidebarNav"] a[aria-current="page"] {
    color: #FBBF24 !important;
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.18) 0%, rgba(245, 158, 11, 0.03) 100%) !important;
    border-left: 3px solid #F59E0B !important;
    font-weight: 700 !important;
    box-shadow: inset 0 0 12px rgba(245, 158, 11, 0.08) !important;
}

/* Sidebar Brand Box */
.sidebar-brand-box {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 4px 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 16px;
}

.sidebar-brand-logo {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(217, 119, 6, 0.15) 100%);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #FBBF24;
    font-size: 22px;
    box-shadow: 0 0 20px rgba(245, 158, 11, 0.3);
}

.sidebar-brand-text strong {
    display: block;
    font-size: 19px;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1.2;
    font-family: 'Outfit', 'Noto Sans Devanagari', sans-serif;
    background: linear-gradient(135deg, #FFFFFF 0%, #FBBF24 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.sidebar-brand-text span {
    display: block;
    font-size: 11px;
    color: #94A3B8;
    margin-top: 2px;
    font-weight: 500;
}

.sidebar-workspace-tag {
    color: #F59E0B;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.6px;
    margin-bottom: 12px;
    text-transform: uppercase;
}

.sidebar-system-card {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 12px;
    padding: 13px 15px;
    margin: 16px 0;
    backdrop-filter: blur(10px);
}

.sidebar-system-top {
    color: #34D399;
    font-size: 11.5px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 7px;
}

.sidebar-live-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #10B981;
    border-radius: 50%;
    box-shadow: 0 0 10px #10B981;
    animation: neonPulse 2s infinite;
}

@keyframes neonPulse {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
    70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.sidebar-system-card p {
    color: #CBD5E1;
    font-size: 11.5px;
    line-height: 1.45;
    margin: 6px 0 0;
}

/* Glassmorphic Topbar */
.urja-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(17, 24, 39, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 14px 22px;
    margin-bottom: 22px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(16px);
}

.urja-crumb {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #94A3B8;
    font-size: 12px;
    font-weight: 500;
}

.urja-crumb strong {
    color: #F8FAFC;
    font-weight: 700;
}

.urja-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 15px;
    border-radius: 9999px;
    background: rgba(16, 185, 129, 0.12);
    color: #34D399;
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.3px;
    border: 1px solid rgba(16, 185, 129, 0.3);
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.15);
}

/* Radiant Hero Section */
.hero-container {
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 32px;
    background: linear-gradient(135deg, rgba(23, 33, 53, 0.85) 0%, rgba(15, 23, 42, 0.92) 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    padding: 38px 42px;
    margin-bottom: 24px;
    box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(20px);
    align-items: center;
    position: relative;
}

.hero-copy .eyebrow {
    font-size: 11px;
    color: #FBBF24;
    letter-spacing: 2px;
    font-weight: 800;
    display: flex;
    align-items: center;
    gap: 8px;
    text-transform: uppercase;
    margin-bottom: 10px;
    text-shadow: 0 0 10px rgba(251, 191, 36, 0.4);
}

.hero-copy h1 {
    font-size: 38px;
    font-weight: 900;
    color: #FFFFFF !important;
    line-height: 1.15;
    margin: 0 0 14px;
    letter-spacing: -0.03em;
}

.hero-copy h1 em {
    font-style: normal;
    background: linear-gradient(135deg, #FDE68A 0%, #F59E0B 50%, #D97706 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 30px rgba(245, 158, 11, 0.4);
}

.hero-copy p {
    color: #CBD5E1;
    font-size: 14.5px;
    line-height: 1.65;
    margin: 0 0 20px;
}

.hero-meta {
    display: flex;
    align-items: center;
    gap: 22px;
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 12px;
    color: #94A3B8;
    font-weight: 600;
}

.meta-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}
.meta-dot.amber { background: #F59E0B; box-shadow: 0 0 8px #F59E0B; }
.meta-dot.teal { background: #10B981; box-shadow: 0 0 8px #10B981; }

.hero-visual-box {
    position: relative;
    border-radius: 14px;
    overflow: hidden;
    height: 320px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6);
}

.hero-visual-main-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.hero-visual-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(10, 15, 29, 0.1) 0%, rgba(10, 15, 29, 0.8) 100%);
}

.hero-caption {
    position: absolute;
    bottom: 20px;
    left: 22px;
    color: #FFFFFF;
}

.hero-caption span {
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #FDE68A;
    display: block;
    margin-bottom: 3px;
    text-shadow: 0 0 10px rgba(251, 191, 36, 0.5);
}

.hero-caption strong {
    font-size: 20px;
    font-weight: 800;
    line-height: 1.2;
    display: block;
    font-family: 'Outfit', sans-serif;
}

.hero-inset-badge {
    position: absolute;
    top: 16px;
    right: 16px;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
    padding: 7px 13px;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.hero-chip-stat {
    position: absolute;
    bottom: 20px;
    right: 20px;
    background: rgba(15, 23, 42, 0.88);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 9999px;
    padding: 7px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 700;
    color: #F8FAFC;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
}

/* Field Story & Video Section */
.field-story-container {
    display: grid;
    grid-template-columns: 1.05fr 1.25fr 0.95fr;
    gap: 24px;
    background: linear-gradient(135deg, rgba(23, 33, 53, 0.8) 0%, rgba(15, 23, 42, 0.88) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 18px;
    padding: 26px 30px;
    margin-bottom: 24px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(16px);
    align-items: center;
}

.field-story-copy .eyebrow {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: #34D399;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    text-shadow: 0 0 10px rgba(52, 211, 153, 0.4);
}

.field-story-copy h2 {
    font-size: 22px;
    font-weight: 800;
    color: #FFFFFF !important;
    line-height: 1.25;
    margin: 0 0 10px;
}

.field-story-copy p {
    font-size: 13px;
    color: #CBD5E1;
    line-height: 1.6;
    margin: 0 0 14px;
}

.story-stat-box {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 12px;
    padding: 10px 15px;
}

.story-stat-box strong {
    font-size: 28px;
    font-weight: 900;
    color: #34D399;
    font-family: 'Outfit', sans-serif;
    text-shadow: 0 0 12px rgba(52, 211, 153, 0.4);
}

.story-stat-box span {
    font-size: 11.5px;
    color: #A7F3D0;
    line-height: 1.35;
    font-weight: 600;
}

.field-video-card {
    position: relative;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    background: #000000;
    height: 200px;
    border: 1px solid rgba(255, 255, 255, 0.15);
}

.field-video-card video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.video-card-overlay {
    position: absolute;
    bottom: 12px;
    left: 14px;
    color: #FFFFFF;
    pointer-events: none;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.8);
}

.video-card-overlay span {
    font-size: 9.5px;
    font-weight: 800;
    letter-spacing: 1.4px;
    color: #34D399;
    text-transform: uppercase;
    display: block;
}

.video-card-overlay strong {
    font-size: 15px;
    font-weight: 800;
    display: block;
    font-family: 'Outfit', sans-serif;
}

.field-story-side-img {
    width: 100%;
    height: 200px;
    object-fit: cover;
    border-radius: 14px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: block;
}

/* Luminous Magnetic Metric Cards */
.metric-card {
    background: linear-gradient(135deg, rgba(23, 33, 53, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 22px 24px;
    display: flex;
    align-items: flex-start;
    min-height: 118px;
    position: relative;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(16px);
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.metric-card:hover {
    box-shadow: 0 14px 35px -5px rgba(245, 158, 11, 0.2);
    border-color: rgba(245, 158, 11, 0.5);
    transform: translateY(-4px);
}

.metric-icon-wrap {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    margin-right: 15px;
    font-size: 22px;
    flex-shrink: 0;
}

.metric-icon-wrap.amber { color: #FBBF24; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); box-shadow: 0 0 15px rgba(245, 158, 11, 0.2); }
.metric-icon-wrap.blue { color: #60A5FA; background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); box-shadow: 0 0 15px rgba(59, 130, 246, 0.2); }
.metric-icon-wrap.green { color: #34D399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); box-shadow: 0 0 15px rgba(16, 185, 129, 0.2); }
.metric-icon-wrap.violet { color: #A78BFA; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); box-shadow: 0 0 15px rgba(139, 92, 246, 0.2); }

.metric-copy p {
    font-size: 11.5px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 6px;
}

.metric-copy strong {
    display: block;
    font-family: 'Outfit', sans-serif;
    font-size: 28px;
    font-weight: 800;
    color: #FFFFFF !important;
    line-height: 1.1;
    letter-spacing: -0.02em;
}

.metric-copy span {
    display: block;
    color: #94A3B8;
    font-size: 12px;
    margin-top: 5px;
    font-weight: 500;
}

.metric-arrow {
    position: absolute;
    right: 18px;
    top: 20px;
    color: #64748B;
    font-size: 14px;
    font-weight: 700;
}

/* Native Streamlit Metrics Styling */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(23, 33, 53, 0.75) 0%, rgba(15, 23, 42, 0.85) 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35) !important;
    backdrop-filter: blur(14px) !important;
    transition: all 0.25s ease !important;
}

[data-testid="stMetric"]:hover {
    border-color: rgba(245, 158, 11, 0.4) !important;
    box-shadow: 0 8px 30px rgba(245, 158, 11, 0.15) !important;
    transform: translateY(-2px) !important;
}

[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] {
    color: #94A3B8 !important;
    font-size: 11.5px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

[data-testid="stMetricValue"] div, [data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 24px !important;
    font-weight: 800 !important;
    font-family: 'Outfit', sans-serif !important;
}

/* Frosted Glass Cards */
.urja-card {
    background: linear-gradient(135deg, rgba(23, 33, 53, 0.75) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 22px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(16px);
}

.urja-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 12px;
}

.urja-card-title {
    font-size: 17px;
    font-weight: 800;
    color: #FFFFFF !important;
    display: flex;
    align-items: center;
    gap: 9px;
    margin: 0;
    font-family: 'Outfit', sans-serif;
}

/* Status Badges */
.status-badge-feasible {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.35);
    padding: 5px 14px;
    border-radius: 9999px;
    font-size: 11.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.2);
}

.status-badge-marginal {
    background: rgba(245, 158, 11, 0.15);
    color: #FBBF24;
    border: 1px solid rgba(245, 158, 11, 0.35);
    padding: 5px 14px;
    border-radius: 9999px;
    font-size: 11.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.2);
}

.status-badge-rejected {
    background: rgba(239, 68, 68, 0.15);
    color: #F87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
    padding: 5px 14px;
    border-radius: 9999px;
    font-size: 11.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.2);
}

/* Inputs & Form Controls */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input {
    background-color: rgba(15, 23, 42, 0.85) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 10px !important;
    color: #F8FAFC !important;
    font-weight: 500 !important;
}

div[data-baseweb="select"] > div:hover,
div[data-baseweb="input"] > div:hover,
div[data-testid="stNumberInput"] input:hover {
    border-color: rgba(245, 158, 11, 0.4) !important;
}

div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"] > div:focus-within {
    border-color: #F59E0B !important;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25) !important;
}

/* Expanders */
div[data-testid="stExpander"] {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(12px) !important;
    margin-bottom: 16px !important;
}

div[data-testid="stExpander"] summary {
    color: #F8FAFC !important;
    font-weight: 700 !important;
}

/* Tables in Dark Glass */
table {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    overflow: hidden;
    margin: 12px 0;
    background: rgba(15, 23, 42, 0.6);
}

th {
    background-color: rgba(30, 41, 59, 0.85) !important;
    color: #94A3B8 !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
    padding: 12px 18px !important;
}

td {
    font-size: 13.5px !important;
    color: #F1F5F9 !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    padding: 12px 18px !important;
}

/* Primary Button with Neon Glow */
button[kind="primary"] {
    background: linear-gradient(135deg, #FBBF24 0%, #F59E0B 50%, #D97706 100%) !important;
    color: #0A0F1D !important;
    font-weight: 800 !important;
    border: none !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.35) !important;
    transition: all 0.25s ease !important;
}

button[kind="primary"]:hover {
    box-shadow: 0 6px 28px rgba(245, 158, 11, 0.55) !important;
    transform: translateY(-2px) !important;
}

button[kind="secondary"] {
    background: rgba(30, 41, 59, 0.8) !important;
    color: #F8FAFC !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    backdrop-filter: blur(10px) !important;
}

button[kind="secondary"]:hover {
    border-color: rgba(245, 158, 11, 0.4) !important;
    background: rgba(45, 58, 80, 0.9) !important;
}

/* Tabs Styling */
div[data-testid="stTabs"] button {
    color: #94A3B8 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #FBBF24 !important;
    border-bottom-color: #F59E0B !important;
    font-weight: 800 !important;
}

/* Alerts */
div[data-testid="stAlert"] {
    border-radius: 12px !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

/* Custom glowing scrollbars */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #0A0F1D;
}
::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(245, 158, 11, 0.4);
}
</style>
"""


def apply_theme() -> None:
    """Inject the global rich dark glassmorphic CSS and layout styles."""
    st.markdown(URJA_RICH_THEME_CSS, unsafe_allow_html=True)
    render_sidebar_brand()


def render_sidebar_brand() -> None:
    """Render the sidebar branding and status module."""
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-brand-box">
                <div class="sidebar-brand-logo">☀️</div>
                <div class="sidebar-brand-text">
                    <strong>{APP_NAME}</strong>
                    <span>Smart Feeder Solarization</span>
                </div>
            </div>
            <div class="sidebar-workspace-tag">WORKSPACE • LATUR</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="sidebar-system-card">
                <div class="sidebar-system-top">
                    <span class="sidebar-live-dot"></span>
                    <span>Data System Online</span>
                </div>
                <p>2024 local datasets loaded<br><b>Latur District, Maharashtra</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_urja_header(
    title: str,
    subtitle: str = "Agricultural Feeder Solarization Decision Support System",
    badge_label: str = "Latur, Maharashtra",
    icon: str = "☀️",
) -> None:
    """Render standardized ऊर्जाSetu top branding topbar."""
    header_html = f"""
    <div class="urja-topbar">
        <div class="urja-crumb">
            <span>Planning Workspace</span>
            <span style="color: #64748B; margin: 0 2px;">›</span>
            <strong>{title}</strong>
        </div>
        <div class="urja-status-pill">
            <span class="sidebar-live-dot" style="width:7px; height:7px; margin-right:4px;"></span>
            <span>{badge_label}</span>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_magnetic_kpi_card(
    label: str,
    value: str,
    detail: str,
    tone: str = "amber",
    icon: str = "⚡",
) -> str:
    """Return HTML string for a magnetic metric card."""
    return f"""
    <div class="metric-card">
        <div class="metric-icon-wrap {tone}">{icon}</div>
        <div class="metric-copy">
            <p>{label}</p>
            <strong>{value}</strong>
            <span>{detail}</span>
        </div>
        <div class="metric-arrow">↗</div>
    </div>
    """


def render_scenario_banner(is_illustrative: bool = False, feeder_name: Optional[str] = None) -> None:
    """Render active scenario mode banner."""
    if is_illustrative:
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(217, 119, 6, 0.08) 100%); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 14px; padding: 16px 22px; margin-bottom: 22px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25); backdrop-filter: blur(12px);">
                <div style="display: flex; align-items: center; gap: 14px;">
                    <span style="font-size: 22px;">✨</span>
                    <div>
                        <strong style="color: #FBBF24; font-size: 14px; font-family: Outfit, sans-serif;">Illustrative Scenario Active (33/11 kV Bhatangali Case Study)</strong>
                        <p style="color: #CBD5E1; font-size: 12px; margin: 3px 0 0;">Pre-loaded with 2.5 MWp solar, 5 MVA PT, and 500 kW connected pumps across Kharif, Rabi, and Summer seasons.</p>
                    </div>
                </div>
                <span class="status-badge-marginal" style="background: rgba(15, 23, 42, 0.8);">Demo Mode</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        name_str = f"Feeder: {feeder_name}" if feeder_name else "Custom Feeder Data Configured"
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.08) 100%); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 14px; padding: 16px 22px; margin-bottom: 22px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25); backdrop-filter: blur(12px);">
                <div style="display: flex; align-items: center; gap: 14px;">
                    <span style="font-size: 22px;">🌱</span>
                    <div>
                        <strong style="color: #34D399; font-size: 14px; font-family: Outfit, sans-serif;">Active Project Scenario ({name_str})</strong>
                        <p style="color: #CBD5E1; font-size: 12px; margin: 3px 0 0;">Running calculations with custom configured crop areas, connected pump ratings, and GIS plant coordinates.</p>
                    </div>
                </div>
                <span class="status-badge-feasible" style="background: rgba(15, 23, 42, 0.8);">User Custom</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_missing_input_card(error: Exception) -> None:
    """Render a clean missing input state with 1-click scenario loader."""
    key_name = getattr(error, "missing_key", "Configuration Key")
    msg = str(error)
    st.error(f"⚠️ **Missing Input:** `{key_name}`\n\n{msg}")
    st.info(
        "💡 **To get started immediately:** Configure custom feeder parameters on **Page 1: Inputs & Data**, "
        "or click below to load the complete **Bhatangali Case Study**."
    )
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("✨ Load Illustrative Scenario (Bhatangali Demo)", type="primary", key=f"btn_demo_missing_{key_name}"):
            from app.state import save_scenario_inputs, get_illustrative_scenario_inputs
            save_scenario_inputs(get_illustrative_scenario_inputs())
            st.rerun()


def render_verdict_badge(verdict: str) -> str:
    """Return HTML verdict badge for feasibility verdict."""
    v_upper = verdict.strip().upper()
    if "FEASIBLE" in v_upper and "NOT" not in v_upper and "REJECT" not in v_upper and "MARGINAL" not in v_upper:
        return '<span class="status-badge-feasible">✅ FEASIBLE</span>'
    elif "MARGINAL" in v_upper:
        return '<span class="status-badge-marginal">⚠️ MARGINAL</span>'
    else:
        return '<span class="status-badge-rejected">❌ REJECTED</span>'


def render_status_chip(status_type: str, label: str) -> str:
    """Render an inline status chip conforming to the dark glass design system."""
    status_lower = status_type.lower()
    if "sourced" in status_lower or "feasible" in status_lower or "green" in status_lower:
        bg = "rgba(16, 185, 129, 0.15)"
        color = "#34D399"
        border = "rgba(16, 185, 129, 0.35)"
        dot = "#10B981"
    elif "user" in status_lower or "blue" in status_lower:
        bg = "rgba(59, 130, 246, 0.15)"
        color = "#60A5FA"
        border = "rgba(59, 130, 246, 0.35)"
        dot = "#3B82F6"
    elif "illustrative" in status_lower or "amber" in status_lower or "marginal" in status_lower:
        bg = "rgba(245, 158, 11, 0.15)"
        color = "#FBBF24"
        border = "rgba(245, 158, 11, 0.35)"
        dot = "#F59E0B"
    elif "check" in status_lower or "violet" in status_lower or "purple" in status_lower:
        bg = "rgba(139, 92, 246, 0.15)"
        color = "#A78BFA"
        border = "rgba(139, 92, 246, 0.35)"
        dot = "#8B5CF6"
    elif "missing" in status_lower or "red" in status_lower or "reject" in status_lower:
        bg = "rgba(239, 68, 68, 0.15)"
        color = "#F87171"
        border = "rgba(239, 68, 68, 0.35)"
        dot = "#EF4444"
    else:
        bg = "rgba(255, 255, 255, 0.08)"
        color = "#94A3B8"
        border = "rgba(255, 255, 255, 0.15)"
        dot = "#94A3B8"

    return (
        f'<span style="display:inline-flex; align-items:center; gap:6px; background:{bg}; '
        f'color:{color}; border:1px solid {border}; padding:3px 10px; border-radius:9999px; '
        f'font-size:11px; font-weight:700; letter-spacing:0.4px; box-shadow:0 0 10px {bg};">'
        f'<span style="width:6px; height:6px; border-radius:50%; background:{dot}; display:inline-block;"></span>'
        f'{label}'
        f'</span>'
    )



def get_urja_plotly_layout(height: int = 380, title: Optional[str] = None) -> Dict[str, Any]:
    """Return a consistent, dark glassmorphic Plotly figure layout conforming to the ऊर्जाSetu design system."""
    layout = {
        "height": height,
        "margin": dict(l=35, r=20, t=40 if title else 20, b=35),
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(15, 23, 42, 0.6)",
        "font": dict(family="Plus Jakarta Sans, sans-serif", size=11, color="#94A3B8"),
        "xaxis": dict(
            gridcolor="rgba(255, 255, 255, 0.06)",
            zerolinecolor="rgba(255, 255, 255, 0.1)",
            showline=True,
            linecolor="rgba(255, 255, 255, 0.1)",
        ),
        "yaxis": dict(
            gridcolor="rgba(255, 255, 255, 0.06)",
            zerolinecolor="rgba(255, 255, 255, 0.1)",
            showline=True,
            linecolor="rgba(255, 255, 255, 0.1)",
        ),
        "legend": dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, family="Plus Jakarta Sans, sans-serif", color="#CBD5E1"),
        ),
        "hovermode": "x unified",
    }
    if title:
        layout["title"] = dict(text=title, font=dict(family="Outfit, sans-serif", size=14, color="#FFFFFF"))
    return layout
