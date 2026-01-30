#!/usr/bin/env python3
"""
Chart generation for finance reports
Creates mobile-optimized PNG charts for Telegram/WhatsApp
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from datetime import date, datetime

try:
    from config import PIE_CHART_MINIMUM_PERCENTAGE, CHART_RETENTION_DAYS
except ImportError:
    PIE_CHART_MINIMUM_PERCENTAGE = 0.03
    CHART_RETENTION_DAYS = 7

# Mobile-optimized chart settings
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#333333',
    'text.color': '#333333',
    'figure.dpi': 100
})

# Category colors - consistent and accessible
CATEGORY_COLORS = {
    'groceries': '#2ecc71',      # Green
    'dining': '#e74c3c',         # Red  
    'transport': '#3498db',      # Blue
    'shopping': '#9b59b6',       # Purple
    'subscriptions': '#f39c12',  # Orange
    'utilities': '#1abc9c',      # Teal
    'entertainment': '#e91e63',  # Pink
    'health': '#00bcd4',         # Cyan
    'housing': '#795548',        # Brown
    'other': '#95a5a6',          # Gray
    'transfers': '#34495e',      # Dark gray
    'income': '#27ae60'          # Dark green
}

def get_category_color(category: str) -> str:
    """Get consistent color for category"""
    return CATEGORY_COLORS.get(category.lower(), '#95a5a6')

def create_spending_pie_chart(data: Dict[str, float], title: str = "Spending by Category") -> Optional[str]:
    """
    Create mobile-optimized pie chart
    
    Args:
        data: {category_name: amount} dict
        title: Chart title
        
    Returns:
        Path to saved PNG file or None if error
    """
    if not data:
        return None
        
    try:
        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        
        # Sort by value, group small slices into "Other"
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        total = sum(data.values())
        
        labels, sizes, colors = [], [], []
        other_amount = 0
        
        for category, amount in sorted_data:
            if amount / total < PIE_CHART_MINIMUM_PERCENTAGE:
                other_amount += amount
            else:
                labels.append(f"{category.title()}\n{amount:,.0f} CHF")
                sizes.append(amount)
                colors.append(get_category_color(category))
        
        if other_amount > 0:
            labels.append(f"Other\n{other_amount:,.0f} CHF")
            sizes.append(other_amount)
            colors.append(get_category_color('other'))
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            sizes, 
            labels=labels,
            colors=colors,
            autopct='%1.0f%%',
            pctdistance=0.75,
            startangle=90,
            textprops={'fontsize': 10, 'color': '#333333'}
        )
        
        # Style percentage labels
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_weight('bold')
            autotext.set_fontsize(9)
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20, color='#333333')
        
        # Save to file
        chart_dir = Path.home() / '.config' / 'clawdbot-finance' / 'charts'
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"spending_pie_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = chart_dir / filename
        
        fig.savefig(filepath, format='png', bbox_inches='tight', 
                    facecolor='white', edgecolor='none', dpi=100)
        plt.close(fig)
        
        return str(filepath)
        
    except Exception as e:
        print(f"Error creating pie chart: {e}")
        if 'fig' in locals():
            plt.close(fig)
        return None

def create_spending_bar_chart(data: List[Tuple[str, float]], title: str = "Daily Spending") -> Optional[str]:
    """
    Create horizontal bar chart for spending comparison
    
    Args:
        data: List of (label, amount) tuples
        title: Chart title
        
    Returns:
        Path to saved PNG file or None if error
    """
    if not data:
        return None
        
    try:
        fig, ax = plt.subplots(figsize=(8, max(4, len(data) * 0.4)), dpi=100)
        
        labels = [item[0] for item in data]
        amounts = [item[1] for item in data]
        
        # Create horizontal bar chart
        bars = ax.barh(labels, amounts, color='#3498db', alpha=0.8)
        
        # Add value labels on bars
        for i, (bar, amount) in enumerate(zip(bars, amounts)):
            width = bar.get_width()
            ax.text(width + max(amounts) * 0.01, bar.get_y() + bar.get_height()/2, 
                   f'{amount:,.0f}', ha='left', va='center', fontsize=9, color='#333333')
        
        ax.set_xlabel('Amount (CHF)', fontsize=12, color='#333333')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20, color='#333333')
        
        # Style axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cccccc')
        ax.spines['bottom'].set_color('#cccccc')
        ax.grid(True, axis='x', alpha=0.3, linestyle='--')
        
        # Save to file
        chart_dir = Path.home() / '.config' / 'clawdbot-finance' / 'charts'
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"spending_bar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = chart_dir / filename
        
        fig.savefig(filepath, format='png', bbox_inches='tight', 
                    facecolor='white', edgecolor='none', dpi=100)
        plt.close(fig)
        
        return str(filepath)
        
    except Exception as e:
        print(f"Error creating bar chart: {e}")
        if 'fig' in locals():
            plt.close(fig)
        return None

def create_trend_line_chart(data: List[Tuple[str, float]], title: str = "Spending Trend") -> Optional[str]:
    """
    Create line chart showing spending trend over time
    
    Args:
        data: List of (date_string, amount) tuples
        title: Chart title
        
    Returns:
        Path to saved PNG file or None if error
    """
    if not data or len(data) < 2:
        return None
        
    try:
        fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
        
        dates = [item[0] for item in data]
        amounts = [item[1] for item in data]
        
        # Create line chart
        ax.plot(dates, amounts, color='#3498db', linewidth=2.5, marker='o', markersize=4)
        
        # Fill area under curve
        ax.fill_between(dates, amounts, alpha=0.2, color='#3498db')
        
        ax.set_ylabel('Amount (CHF)', fontsize=12, color='#333333')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20, color='#333333')
        
        # Style axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cccccc')
        ax.spines['bottom'].set_color('#cccccc')
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Rotate x-axis labels if many data points
        if len(dates) > 7:
            plt.xticks(rotation=45, ha='right')
        
        # Save to file
        chart_dir = Path.home() / '.config' / 'clawdbot-finance' / 'charts'
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"spending_trend_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = chart_dir / filename
        
        fig.savefig(filepath, format='png', bbox_inches='tight', 
                    facecolor='white', edgecolor='none', dpi=100)
        plt.close(fig)
        
        return str(filepath)
        
    except Exception as e:
        print(f"Error creating trend chart: {e}")
        if 'fig' in locals():
            plt.close(fig)
        return None

def create_budget_progress_chart(budgets: List[Dict]) -> Optional[str]:
    """
    Create horizontal progress bars for budget tracking
    
    Args:
        budgets: List of dicts with 'category', 'spent', 'monthly_limit'
        
    Returns:
        Path to saved PNG file or None if error
    """
    if not budgets:
        return None
        
    try:
        fig, ax = plt.subplots(figsize=(8, max(4, len(budgets) * 0.6)), dpi=100)
        
        categories = []
        spent_amounts = []
        limit_amounts = []
        colors = []
        
        for budget in budgets:
            category = budget['category'].title()
            spent = budget['spent']
            limit = budget['monthly_limit']
            percentage = (spent / limit) * 100 if limit > 0 else 0
            
            categories.append(category)
            spent_amounts.append(spent)
            limit_amounts.append(limit)
            
            # Color based on budget status
            if percentage > 100:
                colors.append('#e74c3c')  # Red - over budget
            elif percentage > 80:
                colors.append('#f39c12')  # Orange - approaching limit
            else:
                colors.append('#2ecc71')  # Green - under budget
        
        y_pos = np.arange(len(categories))
        
        # Create background bars (full budget)
        ax.barh(y_pos, limit_amounts, color='#ecf0f1', alpha=0.5, height=0.6)
        
        # Create progress bars (spent amount)
        bars = ax.barh(y_pos, spent_amounts, color=colors, alpha=0.8, height=0.6)
        
        # Add percentage labels
        for i, (spent, limit) in enumerate(zip(spent_amounts, limit_amounts)):
            percentage = (spent / limit) * 100 if limit > 0 else 0
            ax.text(limit * 1.02, y_pos[i], f'{percentage:.0f}%', 
                   ha='left', va='center', fontsize=10, color='#333333', weight='bold')
        
        # Add amount labels on bars
        for i, (bar, spent, limit) in enumerate(zip(bars, spent_amounts, limit_amounts)):
            ax.text(bar.get_width() / 2, bar.get_y() + bar.get_height()/2,
                   f'{spent:,.0f}', ha='center', va='center', 
                   fontsize=9, color='white', weight='bold')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories)
        ax.set_xlabel('Amount (CHF)', fontsize=12, color='#333333')
        ax.set_title('Budget Progress', fontsize=14, fontweight='bold', pad=20, color='#333333')
        
        # Style axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cccccc')
        ax.spines['bottom'].set_color('#cccccc')
        ax.grid(True, axis='x', alpha=0.3, linestyle='--')
        
        # Add legend
        legend_elements = [
            plt.Rectangle((0,0),1,1, facecolor='#2ecc71', alpha=0.8, label='Under Budget'),
            plt.Rectangle((0,0),1,1, facecolor='#f39c12', alpha=0.8, label='Approaching Limit'),
            plt.Rectangle((0,0),1,1, facecolor='#e74c3c', alpha=0.8, label='Over Budget')
        ]
        ax.legend(handles=legend_elements, loc='lower right', fontsize=9)
        
        # Save to file
        chart_dir = Path.home() / '.config' / 'clawdbot-finance' / 'charts'
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"budget_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = chart_dir / filename
        
        fig.savefig(filepath, format='png', bbox_inches='tight', 
                    facecolor='white', edgecolor='none', dpi=100)
        plt.close(fig)
        
        return str(filepath)
        
    except Exception as e:
        print(f"Error creating budget chart: {e}")
        if 'fig' in locals():
            plt.close(fig)
        return None

def create_comparison_chart(current_data: Dict[str, float], previous_data: Dict[str, float], 
                           title: str = "Monthly Comparison") -> Optional[str]:
    """
    Create side-by-side comparison chart
    
    Args:
        current_data: {category: amount} for current period
        previous_data: {category: amount} for previous period  
        title: Chart title
        
    Returns:
        Path to saved PNG file or None if error
    """
    if not current_data and not previous_data:
        return None
        
    try:
        # Combine all categories
        all_categories = set(current_data.keys()) | set(previous_data.keys())
        
        categories = []
        current_amounts = []
        previous_amounts = []
        
        for category in sorted(all_categories):
            categories.append(category.title())
            current_amounts.append(current_data.get(category, 0))
            previous_amounts.append(previous_data.get(category, 0))
        
        if not categories:
            return None
            
        fig, ax = plt.subplots(figsize=(8, max(4, len(categories) * 0.4)), dpi=100)
        
        y_pos = np.arange(len(categories))
        width = 0.35
        
        # Create bars
        bars1 = ax.barh(y_pos - width/2, previous_amounts, width, 
                       label='Previous', color='#95a5a6', alpha=0.7)
        bars2 = ax.barh(y_pos + width/2, current_amounts, width,
                       label='Current', color='#3498db', alpha=0.8)
        
        # Add value labels
        for bars, amounts in [(bars1, previous_amounts), (bars2, current_amounts)]:
            for bar, amount in zip(bars, amounts):
                if amount > 0:
                    ax.text(bar.get_width() + max(max(current_amounts), max(previous_amounts)) * 0.01, 
                           bar.get_y() + bar.get_height()/2, f'{amount:,.0f}',
                           ha='left', va='center', fontsize=8, color='#333333')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories)
        ax.set_xlabel('Amount (CHF)', fontsize=12, color='#333333')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20, color='#333333')
        ax.legend(fontsize=10)
        
        # Style axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cccccc')
        ax.spines['bottom'].set_color('#cccccc')
        ax.grid(True, axis='x', alpha=0.3, linestyle='--')
        
        # Save to file
        chart_dir = Path.home() / '.config' / 'clawdbot-finance' / 'charts'
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = chart_dir / filename
        
        fig.savefig(filepath, format='png', bbox_inches='tight', 
                    facecolor='white', edgecolor='none', dpi=100)
        plt.close(fig)
        
        return str(filepath)
        
    except Exception as e:
        print(f"Error creating comparison chart: {e}")
        if 'fig' in locals():
            plt.close(fig)
        return None

def cleanup_old_charts(days_to_keep: int = None):
    """Remove chart files older than specified days"""
    if days_to_keep is None:
        days_to_keep = CHART_RETENTION_DAYS
    try:
        chart_dir = Path.home() / '.config' / 'clawdbot-finance' / 'charts'
        if not chart_dir.exists():
            return
            
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        
        for chart_file in chart_dir.glob('*.png'):
            if chart_file.stat().st_mtime < cutoff_time:
                chart_file.unlink()
                
    except Exception as e:
        print(f"Error cleaning up charts: {e}")

if __name__ == '__main__':
    # Test chart generation
    test_data = {
        'groceries': 342.50,
        'dining': 189.75,
        'transport': 125.30,
        'shopping': 89.90,
        'subscriptions': 45.99
    }
    
    print("Testing chart generation...")
    
    pie_chart = create_spending_pie_chart(test_data, "Test Spending Breakdown")
    if pie_chart:
        print(f"✅ Pie chart created: {pie_chart}")
    else:
        print("❌ Failed to create pie chart")
        
    bar_data = [('Monday', 45.20), ('Tuesday', 67.80), ('Wednesday', 23.50), 
                ('Thursday', 89.40), ('Friday', 156.90)]
    
    bar_chart = create_spending_bar_chart(bar_data, "Test Daily Spending")
    if bar_chart:
        print(f"✅ Bar chart created: {bar_chart}")
    else:
        print("❌ Failed to create bar chart")