import plotly.graph_objects as go
from plotly.offline import plot
from django.utils import timezone


BLUE = '#173984'
BLUE_LIGHT = '#4f72c6'
GOLD = '#d9aa47'
GOLD_LIGHT = '#f5e4b9'
INK = '#07142f'
MUTED = '#68758d'
GRID = '#e6eaf1'


def _render(figure, height=320):
    figure.update_layout(
        height=height,
        margin=dict(l=22, r=20, t=20, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='DM Sans, sans-serif', color=MUTED, size=12),
        hoverlabel=dict(bgcolor=INK, font_color='white', bordercolor=INK),
        showlegend=False,
    )
    return plot(
        figure,
        output_type='div',
        include_plotlyjs=False,
        config={
            'displayModeBar': False,
            'responsive': True,
            'scrollZoom': False,
        },
    )


def membership_tenure_chart(members):
    rows = list(members.exclude(church_entry_date=None).order_by('church_entry_date')[:6])
    labels = [member.name.split()[0] for member in rows]
    today = timezone.localdate()
    values = [round(max(0, (today - member.church_entry_date).days) / 365.2425, 1) for member in rows]
    figure = go.Figure(go.Scatter(
        x=labels,
        y=values,
        mode='lines+markers',
        line=dict(color=BLUE, width=4, shape='spline'),
        marker=dict(size=11, color=GOLD, line=dict(color=BLUE, width=3)),
        fill='tozeroy',
        fillcolor='rgba(23,57,132,.10)',
        hovertemplate='<b>%{x}</b><br>Tempo de igreja: %{y:.1f} anos<extra></extra>',
    ))
    figure.update_yaxes(ticksuffix=' anos', gridcolor=GRID, zeroline=False, rangemode='tozero')
    figure.update_xaxes(showgrid=False)
    return _render(figure)


def reports_chart(members):
    labels = ['Base', 'Ativos', 'Liderança', 'Visitantes', 'Novos']
    values = [
        members.count(),
        members.filter(status='active').count(),
        members.filter(status='leadership').count(),
        members.filter(status='visitor').count(),
        members.filter(status='new').count(),
    ]
    figure = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker=dict(color=[BLUE, BLUE_LIGHT, GOLD, GOLD_LIGHT, '#8fa8dc'], line=dict(width=0)),
        text=values,
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>%{y} pessoas<extra></extra>',
    ))
    figure.update_yaxes(gridcolor=GRID, zeroline=False, rangemode='tozero')
    figure.update_xaxes(showgrid=False)
    return _render(figure)
