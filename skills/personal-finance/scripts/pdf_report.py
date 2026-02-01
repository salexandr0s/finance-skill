#!/usr/bin/env python3
"""
Infographic-style PDF Financial Report
Modern dual-column layout with charts and metrics.

Usage:
    python3 pdf_report.py --month 1 --year 2026
    python3 pdf_report.py --month 1 --year 2026 --output ~/report.pdf
"""

import sys
import os
import argparse
import base64
from datetime import datetime
from calendar import monthrange
from pathlib import Path
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import requests

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from db import get_transactions, get_accounts
from config import get_user_config

try:
    import keychain
    HAS_KEYCHAIN = True
except ImportError:
    HAS_KEYCHAIN = False

PAGE_W, PAGE_H = A4

# Layout constants
MARGIN = 15*mm
COL_GAP = 8*mm
COL_W = (PAGE_W - 2*MARGIN - COL_GAP) / 2
COL1_X = MARGIN
COL2_X = MARGIN + COL_W + COL_GAP


def get_zerion_api_key():
    """Get Zerion API key for crypto portfolio."""
    if HAS_KEYCHAIN:
        key = keychain.get("zerion_api_key")
        if key:
            return key
    return os.environ.get("ZERION_API_KEY")


def get_crypto_wallets():
    """Get crypto wallets from config."""
    try:
        config = get_user_config()
        return config.get("crypto", {}).get("wallets", {})
    except:
        return {}


def get_crypto_portfolio() -> dict:
    """Fetch current crypto portfolio from Zerion."""
    api_key = get_zerion_api_key()
    wallets = get_crypto_wallets()
    
    if not api_key or not wallets:
        return {"total_usd": 0, "wallets": {}}
    
    auth = base64.b64encode(f"{api_key}:".encode()).decode()
    portfolio = {"total_usd": 0, "wallets": {}}
    
    for name, addr in wallets.items():
        try:
            resp = requests.get(
                f"https://api.zerion.io/v1/wallets/{addr}/portfolio?currency=usd",
                headers={"Authorization": f"Basic {auth}"},
                timeout=10
            )
            data = resp.json()
            value = data.get("data", {}).get("attributes", {}).get("total", {}).get("positions", 0)
            portfolio["wallets"][name] = {"address": addr, "value_usd": value}
            portfolio["total_usd"] += value
        except Exception as e:
            print(f"Warning: Could not fetch {name} wallet: {e}")
            portfolio["wallets"][name] = {"address": addr, "value_usd": 0}
    
    return portfolio


def analyze_transactions(transactions: list, currency: str = "CHF") -> dict:
    """Analyze transactions and compute metrics."""
    income = []
    expenses = []
    by_category = {}
    by_merchant = {}
    subscriptions = []
    daily_flow = {}
    
    for tx in transactions:
        amount = tx.get("amount", 0)
        if not amount:
            continue
        
        category = tx.get("category", "Other")
        description = tx.get("description", "Unknown")
        date = tx.get("date", "")
        is_recurring = tx.get("recurring", False)
        
        flow_amount = 0
        
        if amount < 0:
            expenses.append({"amount": abs(amount), "description": description, "date": date, "category": category})
            flow_amount = amount
            by_category[category] = by_category.get(category, 0) + abs(amount)
            merchant = description.split()[0] if description else "Unknown"
            by_merchant[merchant] = by_merchant.get(merchant, 0) + abs(amount)
            if is_recurring:
                subscriptions.append({"name": description, "amount": abs(amount)})
        else:
            income.append({"amount": amount, "description": description, "date": date})
            flow_amount = amount
        
        if date:
            daily_flow[date] = daily_flow.get(date, 0) + flow_amount
    
    total_income = sum(i["amount"] for i in income)
    total_expenses = sum(e["amount"] for e in expenses)
    net_flow = total_income - total_expenses
    
    top_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    top_merchants = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_flow": net_flow,
        "income_transactions": income,
        "expense_transactions": expenses,
        "by_category": dict(top_categories),
        "top_merchants": dict(top_merchants),
        "subscriptions": subscriptions,
        "daily_flow": daily_flow,
        "tx_count": len(transactions),
        "currency": currency
    }


def create_neutral_chart(daily_flow: dict, year: int, month: int) -> BytesIO:
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(7, 1.6))
    
    sorted_dates = sorted(daily_flow.keys())
    if not sorted_dates:
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close()
        buf.seek(0)
        return buf
    
    dates = [datetime.strptime(d, "%Y-%m-%d") for d in sorted_dates]
    cumulative = []
    running = 0
    for d in sorted_dates:
        running += daily_flow[d]
        cumulative.append(running)
    
    ax.fill_between(dates, cumulative, 0, where=[c >= 0 for c in cumulative], 
                    alpha=0.25, color='#0d9488', interpolate=True)
    ax.fill_between(dates, cumulative, 0, where=[c < 0 for c in cumulative], 
                    alpha=0.25, color='#f97316', interpolate=True)
    ax.plot(dates, cumulative, color='#1e293b', linewidth=1.5)
    
    ax.axhline(y=0, color='#e4e4e7', linewidth=0.5)
    
    if cumulative:
        final = cumulative[-1]
        color = '#0d9488' if final >= 0 else '#f97316'
        ax.annotate(f'{final:+,.0f}', xy=(dates[-1], final),
                   xytext=(5, 0), textcoords='offset points',
                   fontsize=8, color=color, fontweight='bold')
    
    ax.set_xlim(dates[0], dates[-1])
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='both', labelsize=7, colors='#71717a')
    ax.set_facecolor('#fafafa')
    fig.patch.set_facecolor('#fafafa')
    
    plt.tight_layout(pad=0.3)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf


def generate_infographic(year: int, month: int, analysis: dict, crypto: dict, output: str):
    """Generate the infographic-style report."""
    
    c = canvas.Canvas(output, pagesize=A4)
    month_name = datetime(year, month, 1).strftime("%B %Y")
    currency = analysis.get("currency", "CHF")
    
    # Colors
    SLATE = colors.HexColor("#1e293b")
    ZINC = colors.HexColor("#71717a")
    STONE = colors.HexColor("#a1a1aa")
    LIGHT = colors.HexColor("#f4f4f5")
    WHITE = colors.white
    
    TEAL = colors.HexColor("#0d9488")
    CORAL = colors.HexColor("#f97316")
    BLUE = colors.HexColor("#3b82f6")
    
    bar_colors = [
        colors.HexColor("#0d9488"),
        colors.HexColor("#3b82f6"),
        colors.HexColor("#6366f1"),
        colors.HexColor("#8b5cf6"),
        colors.HexColor("#f59e0b"),
        colors.HexColor("#64748b"),
    ]
    
    # =========================================================================
    # HEADER
    # =========================================================================
    header_h = 35*mm
    c.setFillColor(SLATE)
    c.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)
    
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(WHITE)
    c.drawString(MARGIN, PAGE_H - 22*mm, month_name)
    
    c.setFont("Helvetica", 9)
    c.setFillColor(STONE)
    c.drawString(MARGIN, PAGE_H - 30*mm, "Monthly Financial Report")
    
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(WHITE)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 16*mm, f"{analysis['tx_count']}")
    c.setFont("Helvetica", 7)
    c.setFillColor(STONE)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 22*mm, "transactions")
    
    avg_tx = analysis['total_expenses'] / len(analysis['expense_transactions']) if analysis['expense_transactions'] else 0
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(WHITE)
    c.drawRightString(PAGE_W - MARGIN - 35*mm, PAGE_H - 16*mm, f"{currency} {avg_tx:.0f}")
    c.setFont("Helvetica", 7)
    c.setFillColor(STONE)
    c.drawRightString(PAGE_W - MARGIN - 35*mm, PAGE_H - 22*mm, "avg expense")
    
    # =========================================================================
    # KPI CARDS
    # =========================================================================
    kpi_y = PAGE_H - header_h - 35*mm
    kpi_h = 26*mm
    kpi_w = (PAGE_W - 2*MARGIN - 2*6*mm) / 3
    
    kpis = [
        ("INCOME", analysis['total_income'], TEAL),
        ("EXPENSES", analysis['total_expenses'], CORAL),
        ("NET FLOW", analysis['net_flow'], BLUE)
    ]
    
    for i, (label, value, accent) in enumerate(kpis):
        x = MARGIN + i * (kpi_w + 6*mm)
        
        c.setFillColor(LIGHT)
        c.roundRect(x, kpi_y, kpi_w, kpi_h, 2*mm, fill=1, stroke=0)
        
        c.setFillColor(accent)
        c.rect(x, kpi_y + kpi_h - 2.5*mm, kpi_w, 2.5*mm, fill=1, stroke=0)
        
        c.setFont("Helvetica", 7)
        c.setFillColor(ZINC)
        c.drawString(x + 4*mm, kpi_y + kpi_h - 10*mm, label)
        
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(SLATE)
        prefix = "+" if label == "NET FLOW" and value >= 0 else ""
        c.drawString(x + 4*mm, kpi_y + 4*mm, f"{currency} {prefix}{value:,.0f}")
    
    # =========================================================================
    # DUAL COLUMN CONTENT
    # =========================================================================
    content_top = kpi_y - 8*mm
    section_gap = 6*mm
    
    def section_header(x, y, title):
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(SLATE)
        c.drawString(x, y, title)
        return y - 5*mm
    
    # ----- LEFT COLUMN: Categories & Merchants -----
    y_left = content_top
    y_left = section_header(COL1_X, y_left, "SPENDING BY CATEGORY")
    
    total_exp = analysis['total_expenses'] or 1
    categories = list(analysis['by_category'].items())[:6]
    
    for i, (cat, amt) in enumerate(categories):
        pct = amt / total_exp * 100
        bar_max = COL_W - 45*mm
        bar_width = bar_max * (pct / 100)
        
        c.setFillColor(colors.HexColor("#e4e4e7"))
        c.rect(COL1_X, y_left - 2*mm, bar_max, 5*mm, fill=1, stroke=0)
        
        c.setFillColor(bar_colors[i % len(bar_colors)])
        c.rect(COL1_X, y_left - 2*mm, max(bar_width, 2*mm), 5*mm, fill=1, stroke=0)
        
        c.setFont("Helvetica", 8)
        c.setFillColor(SLATE)
        c.drawString(COL1_X + bar_max + 3*mm, y_left, f"{cat[:12]}")
        c.setFillColor(ZINC)
        c.setFont("Helvetica", 7)
        c.drawRightString(COL1_X + COL_W, y_left, f"{amt:,.0f}")
        
        y_left -= 9*mm
    
    y_left -= section_gap
    y_left = section_header(COL1_X, y_left, "TOP MERCHANTS")
    
    merchants = list(analysis['top_merchants'].items())[:5]
    for i, (merchant, amt) in enumerate(merchants, 1):
        c.setFillColor(bar_colors[(i-1) % len(bar_colors)])
        c.circle(COL1_X + 3*mm, y_left + 1*mm, 2.5*mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(COL1_X + 3*mm, y_left - 0.5*mm, str(i))
        
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 8)
        c.drawString(COL1_X + 10*mm, y_left, merchant[:18])
        c.setFillColor(ZINC)
        c.drawRightString(COL1_X + COL_W, y_left, f"{currency} {amt:,.0f}")
        
        y_left -= 8*mm
    
    # Subscriptions
    y_left -= section_gap
    if analysis['subscriptions']:
        y_left = section_header(COL1_X, y_left, "RECURRING COSTS")
        
        subs_total = 0
        for sub in analysis['subscriptions'][:4]:
            c.setFillColor(SLATE)
            c.setFont("Helvetica", 8)
            c.drawString(COL1_X, y_left, f"• {sub['name'][:20]}")
            c.setFillColor(ZINC)
            c.drawRightString(COL1_X + COL_W, y_left, f"{sub['amount']:,.0f}")
            subs_total += sub['amount']
            y_left -= 7*mm
        
        c.setStrokeColor(colors.HexColor("#e4e4e7"))
        c.setLineWidth(0.5)
        c.line(COL1_X, y_left + 2*mm, COL1_X + COL_W, y_left + 2*mm)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(CORAL)
        c.drawString(COL1_X, y_left - 3*mm, "Monthly total")
        c.drawRightString(COL1_X + COL_W, y_left - 3*mm, f"{currency} {subs_total:,.0f}")
    
    # ----- RIGHT COLUMN: Stats & Income -----
    y_right = content_top
    y_right = section_header(COL2_X, y_right, "QUICK STATS")
    
    box_h = 42*mm
    c.setFillColor(LIGHT)
    c.roundRect(COL2_X, y_right - box_h, COL_W, box_h, 2*mm, fill=1, stroke=0)
    box_top = y_right - 5*mm
    
    if analysis['expense_transactions']:
        largest = max(analysis['expense_transactions'], key=lambda x: x['amount'])
        c.setFont("Helvetica", 7)
        c.setFillColor(ZINC)
        c.drawString(COL2_X + 5*mm, box_top, "Largest expense")
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(SLATE)
        c.drawString(COL2_X + 5*mm, box_top - 7*mm, f"{currency} {largest['amount']:,.0f}")
        c.setFont("Helvetica", 7)
        c.setFillColor(ZINC)
        c.drawString(COL2_X + 5*mm, box_top - 14*mm, largest['description'][:22])
    
    days_in_month = monthrange(year, month)[1]
    daily_avg = analysis['total_expenses'] / days_in_month
    c.setFont("Helvetica", 7)
    c.setFillColor(ZINC)
    c.drawString(COL2_X + 5*mm, box_top - 24*mm, "Daily average")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(SLATE)
    c.drawString(COL2_X + 5*mm, box_top - 31*mm, f"{currency} {daily_avg:,.0f}")
    
    if analysis['total_income'] > 0:
        savings_rate = (analysis['net_flow'] / analysis['total_income']) * 100
        c.setFont("Helvetica", 7)
        c.setFillColor(ZINC)
        c.drawString(COL2_X + COL_W/2 + 5*mm, box_top, "Savings rate")
        c.setFont("Helvetica-Bold", 18)
        rate_color = TEAL if savings_rate >= 0 else CORAL
        c.setFillColor(rate_color)
        c.drawString(COL2_X + COL_W/2 + 5*mm, box_top - 10*mm, f"{savings_rate:+.0f}%")
    
    y_right -= box_h + section_gap
    
    # Spending by day
    y_right = section_header(COL2_X, y_right, "SPENDING BY DAY")
    
    dow_spending = {i: 0 for i in range(7)}
    dow_names = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    
    for tx in analysis['expense_transactions']:
        if tx['date']:
            try:
                dt = datetime.strptime(tx['date'], "%Y-%m-%d")
                dow_spending[dt.weekday()] += tx['amount']
            except:
                pass
    
    max_dow = max(dow_spending.values()) or 1
    bar_w = (COL_W - 6*mm) / 7
    chart_h = 22*mm
    
    for i, (dow, amt) in enumerate(dow_spending.items()):
        bar_x = COL2_X + i * bar_w
        bar_h = chart_h * (amt / max_dow) if amt > 0 else 1*mm
        
        c.setFillColor(BLUE)
        c.rect(bar_x + 1*mm, y_right - chart_h, bar_w - 2*mm, bar_h, fill=1, stroke=0)
        
        c.setFont("Helvetica", 6)
        c.setFillColor(ZINC)
        c.drawCentredString(bar_x + bar_w/2, y_right - chart_h - 4*mm, dow_names[i])
    
    y_right -= chart_h + 8*mm + section_gap
    
    # Income sources
    y_right = section_header(COL2_X, y_right, "INCOME SOURCES")
    
    if analysis['income_transactions']:
        income_by_source = {}
        for inc in analysis['income_transactions']:
            source = inc['description'][:18] or "Other"
            income_by_source[source] = income_by_source.get(source, 0) + inc['amount']
        
        sorted_income = sorted(income_by_source.items(), key=lambda x: x[1], reverse=True)[:4]
        
        for source, amt in sorted_income:
            c.setFillColor(TEAL)
            c.setFont("Helvetica", 8)
            c.drawString(COL2_X, y_right, "▸")
            c.setFillColor(SLATE)
            c.drawString(COL2_X + 5*mm, y_right, source[:16])
            c.setFillColor(ZINC)
            c.drawRightString(COL2_X + COL_W, y_right, f"{amt:,.0f}")
            y_right -= 7*mm
        
        c.setStrokeColor(colors.HexColor("#e4e4e7"))
        c.setLineWidth(0.5)
        c.line(COL2_X, y_right + 2*mm, COL2_X + COL_W, y_right + 2*mm)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(TEAL)
        c.drawString(COL2_X, y_right - 3*mm, "Total income")
        c.drawRightString(COL2_X + COL_W, y_right - 3*mm, f"{currency} {analysis['total_income']:,.0f}")
    
    # Crypto portfolio
    y_right -= section_gap
    if crypto and crypto.get("total_usd", 0) > 0:
        y_right = section_header(COL2_X, y_right, "CRYPTO PORTFOLIO")
        
        box_h = 18*mm
        c.setFillColor(colors.HexColor("#0f172a"))
        c.roundRect(COL2_X, y_right - box_h, COL_W, box_h, 2*mm, fill=1, stroke=0)
        
        c.setFont("Helvetica", 7)
        c.setFillColor(STONE)
        c.drawString(COL2_X + 5*mm, y_right - 6*mm, "Total Holdings")
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#22c55e"))
        c.drawString(COL2_X + 5*mm, y_right - 14*mm, f"${crypto['total_usd']:,.0f}")
    
    # =========================================================================
    # CASH FLOW CHART
    # =========================================================================
    chart_section_top = 68*mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(SLATE)
    c.drawString(MARGIN, chart_section_top, "CASH FLOW")
    
    if analysis['daily_flow']:
        chart_buf = create_neutral_chart(analysis['daily_flow'], year, month)
        c.drawImage(ImageReader(chart_buf), MARGIN, 22*mm, 
                   width=PAGE_W - 2*MARGIN, height=42*mm, preserveAspectRatio=True)
    
    # =========================================================================
    # FOOTER
    # =========================================================================
    c.setFont("Helvetica", 7)
    c.setFillColor(ZINC)
    c.drawString(MARGIN, 12*mm, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.drawRightString(PAGE_W - MARGIN, 12*mm, f"All amounts in {currency}")
    
    c.save()
    print(f"✓ Report saved to: {output}")


def main():
    parser = argparse.ArgumentParser(description="Generate PDF financial report")
    parser.add_argument("--month", "-m", type=int, required=True, help="Month (1-12)")
    parser.add_argument("--year", "-y", type=int, required=True, help="Year")
    parser.add_argument("--output", "-o", type=str, help="Output PDF path")
    parser.add_argument("--no-crypto", action="store_true", help="Skip crypto portfolio")
    args = parser.parse_args()
    
    if args.month < 1 or args.month > 12:
        print("Error: Month must be between 1 and 12")
        sys.exit(1)
    
    # Get user config for currency
    try:
        config = get_user_config()
        currency = config.get("currency", "EUR")
    except:
        currency = "EUR"
    
    # Fetch transactions
    print(f"Fetching data for {args.month:02d}/{args.year}...")
    start_date = f"{args.year}-{args.month:02d}-01"
    _, last_day = monthrange(args.year, args.month)
    end_date = f"{args.year}-{args.month:02d}-{last_day}"
    
    transactions = get_transactions(start_date=start_date, end_date=end_date)
    print(f"Found {len(transactions)} transactions")
    
    analysis = analyze_transactions(transactions, currency)
    
    if not args.output:
        output_dir = Path.home() / "Documents" / "Financial Reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(output_dir / f"report-{args.month:02d}-{args.year}.pdf")
    
    crypto = {}
    if not args.no_crypto:
        print("  Fetching crypto portfolio...")
        crypto = get_crypto_portfolio()
        if crypto.get("total_usd", 0) > 0:
            print(f"  Crypto total: ${crypto['total_usd']:,.0f}")
    
    generate_infographic(args.year, args.month, analysis, crypto, args.output)


if __name__ == "__main__":
    main()
