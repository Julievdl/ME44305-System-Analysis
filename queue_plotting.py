import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.colors as pc

def plot_queue(queue_name, times, values):
    jobpd = pd.DataFrame({"times" : [], "values" : []})
    jobpd["times"] = times
    jobpd["values"] = values
    
    fig = px.line(jobpd, x="times", y="values")
    fig.update_layout(title=f"{queue_name} length",
                      xaxis_title="Simulation Time (s)",
                        yaxis_title="Queue Length")
    fig.show()
    fig.write_image(f"{queue_name}_figure.png")
    
def plot_queue_lines(queue_names = [], times = [], values = [], line_values=[], line_names=[]):
    fig = go.Figure()
    title = ""
    save = ""
    for v in range(len(values)):
        title += queue_names[v]
        save += queue_names[v]
        if v != (len(values)-1):
            title += " and "
            save += "_"
        # Queue length over time
        fig.add_trace(go.Scatter(
            x=times[v], y=values[v],
            mode="lines", name=f"{queue_names[v]} Length"
        ))

    # Pick a colour palette
    colours = pc.qualitative.Plotly  # 10 distinct colours

    for p in range(len(line_values)):
        colour = colours[p % len(colours)]
        name   = line_names[p] if p < len(line_names) else f"Event {p}"

        # Add a dummy scatter trace just for the legend entry
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(color=colour, dash="dash"),
            name=name
        ))

        for t in line_values[p]:
            fig.add_vline(x=t, line_dash="dash", line_color=colour, opacity=0.4)

    fig.update_layout(
    title=f"{title} length",
    xaxis_title="Simulation Time (s)",
    yaxis_title="Queue Length",
    font=dict(size=14),  # global font size
    legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255,255,255,0.7)",  # semi-transparent background
            bordercolor="lightgrey",
            borderwidth=1
        )
    )
    fig.show()
    fig.write_image(f"{save}_lines_figure.png", width = 1200, height=600, scale = 3)