import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _future_x(last_date, first_date, fraction=.08):
    last = pd.Timestamp(last_date)
    first = pd.Timestamp(first_date)
    span = max(last - first, pd.Timedelta(minutes=30))
    return last + span * fraction


def price_chart(df, title="Price", guidance=None, compact=False):
    height = 540 if compact else 720
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.04, row_heights=[.77, .23])
    fig.add_trace(go.Candlestick(x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="OHLC"), row=1, col=1)
    for c in ["EMA20", "EMA50", "EMA200"]:
        fig.add_trace(go.Scatter(x=df["Date"], y=df[c], name=c, mode="lines", line={"width": 1.35}), row=1, col=1)
    for c, n in [("BB_UPPER", "BB Upper"), ("BB_LOWER", "BB Lower")]:
        fig.add_trace(go.Scatter(x=df["Date"], y=df[c], name=n, mode="lines", opacity=.26, line={"width": 1}), row=1, col=1)
    fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume", opacity=.62), row=2, col=1)

    if guidance is not None:
        levels = [
            (guidance.buy_trigger, "BUY TRIGGER", "#10b981", "dash"),
            (guidance.sell_tp1, "TP1", "#0ea5e9", "dash"),
            (guidance.sell_tp2, "TP2", "#2563eb", "dot"),
            (guidance.stop_loss, "STOP", "#ef4444", "dash"),
            (guidance.support, "SUPPORT", "#64748b", "dot"),
            (guidance.resistance, "RESISTANCE", "#f59e0b", "dot"),
        ]
        for y, label, color, dash in levels:
            fig.add_hline(y=float(y), row=1, col=1, line_width=1.15, line_dash=dash, line_color=color,
                          annotation_text=f"{label} {float(y):,.2f}", annotation_position="top right",
                          annotation_font_color=color)

        # V4: limit the highlighted trade boxes to the recent/right-hand portion of the chart.
        dates = pd.to_datetime(df["Date"])
        x0_idx = max(0, int(len(dates) * (0.72 if not compact else 0.62)))
        x0 = dates.iloc[x0_idx]
        x1 = _future_x(dates.iloc[-1], dates.iloc[0], .06 if not compact else .04)
        shapes = [
            (guidance.buy_zone_low, guidance.buy_zone_high, "rgba(16,185,129,.18)", "rgba(16,185,129,.75)", "BUY ZONE"),
            (guidance.tp1_zone_low, guidance.tp1_zone_high, "rgba(14,165,233,.16)", "rgba(14,165,233,.70)", "TAKE PROFIT 1"),
            (guidance.tp2_zone_low, guidance.tp2_zone_high, "rgba(37,99,235,.13)", "rgba(37,99,235,.65)", "TAKE PROFIT 2"),
            (guidance.stop_zone_low, guidance.stop_zone_high, "rgba(239,68,68,.16)", "rgba(239,68,68,.72)", "STOP / EXIT"),
        ]
        for y0, y1, fill, line, label in shapes:
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=float(y0), y1=float(y1), xref="x", yref="y",
                          fillcolor=fill, line={"color": line, "width": 1.15}, layer="below")
            fig.add_annotation(x=x1, y=(float(y0)+float(y1))/2, xref="x", yref="y", text=label,
                               showarrow=False, xanchor="right", font={"size": 9 if compact else 10, "color": line},
                               bgcolor="rgba(255,255,255,.80)")

    fig.update_layout(title=title, xaxis_rangeslider_visible=False, height=height, legend_orientation="h",
                      margin={"l": 10 if compact else 20, "r": 10 if compact else 20, "t": 55, "b": 20},
                      hovermode="x unified")
    if compact:
        fig.update_layout(legend={"font": {"size": 9}, "y": 1.02}, title_font={"size": 15})
    return fig
