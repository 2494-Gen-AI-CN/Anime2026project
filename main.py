import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

data = pd.read_csv('data/anime-dataset-2026.csv')

def load_frame(data):
    return pd.DataFrame(data)

_data = load_frame(data)
print(_data.columns)


def isekai_lol():
    isekai = _data[_data['Genres'].str.contains('Isekai', na=False)]
    tv_only = isekai.loc[lambda f: f['Type'] == 'TV']

    # Include 'Name' (fallback if English name is UNKNOWN) and 'Premiered' (e.g., 'Winter 2025')
    df = tv_only.filter(
        items=['Name', 'English name', 'Premiered', 'Aired', 'Score', 'Popularity'],
        axis='columns'
    ).copy()

    # Use English name if available, otherwise fallback to Romaji Name
    df['Title'] = df['English name'].where(df['English name'] != 'UNKNOWN', df['Name'])
    df['Title_Length'] = df['Title'].str.split().str.len()  # Or use .str.split().str.len() for word count

    # Extract Season ('Winter', 'Spring', 'Summer', 'Fall') and Year from 'Premiered'
    extracted = df['Premiered'].str.extract(r'^(Winter|Spring|Summer|Fall)\s+(\d{4})$')
    df['Season'] = extracted[0]
    df['Year'] = pd.to_numeric(extracted[1], errors='coerce')
    df = df.dropna(subset=['Season', 'Year'])
    df = df[df['Year'] >= 2012]  # Focus on modern Isekai boom (2012-2026)

    # Map Season names to their decimal offset (center of each 0.25 block) and color
    season_offsets = {'Winter': 0.125, 'Spring': 0.375, 'Summer': 0.625, 'Fall': 0.875}
    season_colors = {'Winter': '#3b82f6', 'Spring': '#22c55e', 'Summer': '#f97316', 'Fall': '#ef4444'}
    season_blocks = [
        ('Winter', 0.00, 0.25, '#3b82f6'),
        ('Spring', 0.25, 0.25, '#22c55e'),
        ('Summer', 0.50, 0.25, '#f97316'),
        ('Fall',   0.75, 0.25, '#ef4444'),
    ]

    df['x_pos'] = df['Year'] + df['Season'].map(season_offsets)
    df['color'] = df['Season'].map(season_colors)

    fig, (ax_main, ax_strip) = plt.subplots(
        2, 1,
        figsize=(12, 6),
        sharex=True,
        gridspec_kw={'height_ratios': [35, 1], 'hspace': 0.03}
    )

    # Plot the scatter points and yearly average trendline on ax_main
    ax_main.scatter(
        df['x_pos'],
        df['Title_Length'],
        c=df['color'],
        alpha=0.75,
        s=45,
        edgecolors='black',
        linewidth=0.4
    )
    yearly_avg = df.groupby('Year')['Title_Length'].mean()
    ax_main.plot(
        yearly_avg.index + 0.5,
        yearly_avg.values,
        color='black',
        linestyle='--',
        linewidth=2,
        marker='o',
        label='Yearly Average'
    )
    ax_main.set_ylabel('Title Length (Word Count)')
    ax_main.set_title('TV Isekai Title Length Over Time')


    start_year = int(df['Year'].min())
    end_year = int(df['Year'].max()) + 1

    for year in range(start_year, end_year + 1):
        ax_main.axvline(year, color='gray', linestyle='--', alpha=0.4)

    # --- BOTTOM STRIP (Repeating Blue-Green-Orange-Red per Year) ---
    for year in range(start_year, end_year):
        for name, offset, width, color in season_blocks:
            # Draw each 0.25-wide season block inside the current year
            ax_strip.broken_barh(
                [(year + offset, width)],
                (0, 1),
                facecolors=color,
                edgecolors='white',
                linewidth=0.5
            )
        # Draw a stronger black divider line at the start of each year block
        ax_strip.axvline(year, color='black', linewidth=1.2)

    ax_strip.axvline(end_year, color='black', linewidth=1.2)
    ax_strip.set_ylim(0, 1)
    ax_strip.set_yticks([])  # Hide Y-axis numbers on the color strip
    ax_strip.set_xlim(start_year, end_year)

    # 3. Put the Year text centered underneath each 4-color year block (at year + 0.5)
    year_centers = [y + 0.5 for y in range(start_year, end_year)]
    ax_strip.set_xticks(year_centers)
    ax_strip.set_xticklabels([str(y) for y in range(start_year, end_year)], fontsize=10, fontweight='bold')
    ax_strip.tick_params(axis='x', length=0, pad=6)  # Hide tick marks, just show the year text

    # 4. Add a small legend underneath explaining Blue/Green/Orange/Red
    legend_patches = [mpatches.Patch(color=c, label=n) for n, c in season_colors.items()]
    ax_main.legend(
        handles=legend_patches,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.12),
        ncol=4,
        frameon=False,
        fontsize=9
    )

    plt.tight_layout()
    plt.show()


isekai_lol()
