"""Chart and graph generation utilities."""

from __future__ import annotations

import plotly.graph_objects as go


def create_eval_graph(evals: list[int], status: str) -> go.Figure | go.FigureWidget:
    """Create evaluation graph for chess position analysis.

    Args:
        evals: List of evaluations in centipawns
        status: Annotation status ("running", "idle", etc.)

    Returns:
        Plotly figure or FigureWidget
    """
    # Show evaluating message when annotation is running
    if status == "running":
        return _create_placeholder_graph("Evaluating...")

    # Show prompt message when no data
    if not evals or len(evals) <= 1:
        return _create_placeholder_graph(
            "Annotate the game to see the evaluation graph"
        )

    # Create x-axis (ply numbers starting from 0)
    plies = list(range(0, len(evals)))

    # Convert evaluations to pawns (divide by 100)
    eval_pawns = [e / 100 for e in evals]

    # Create the figure
    fig = go.Figure()

    # Add invisible hover-sensitive area
    fig.add_trace(
        go.Scatter(
            x=plies,
            y=eval_pawns,
            fill="tozeroy",
            fillcolor="rgba(0, 0, 0, 0)",  # Invisible
            line=dict(width=0),
            mode="none",
            showlegend=False,
            hovertemplate="Eval: %{y:.2f}<extra></extra>",
        )
    )

    # Add shaded area for positive values (white advantage)
    fig.add_trace(
        go.Scatter(
            x=plies,
            y=eval_pawns,
            fill="tozeroy",
            fillcolor="rgba(255, 255, 255, 0.7)",
            line=dict(width=0),
            mode="none",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Add shaded area for negative values (black advantage)
    fig.add_trace(
        go.Scatter(
            x=plies,
            y=[min(0, v) for v in eval_pawns],
            fill="tozeroy",
            fillcolor="rgba(0, 0, 0, 0.7)",
            line=dict(width=0),
            mode="none",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Add main trace line on top
    fig.add_trace(
        go.Scatter(
            x=plies,
            y=eval_pawns,
            mode="lines+markers",
            name="Evaluation",
            line=dict(color="rgba(100, 100, 100, 0.8)", width=1),
            marker=dict(size=2, color="rgba(100, 100, 100, 0.8)"),
            hoverinfo="skip",
        )
    )

    # Update layout
    fig.update_layout(
        xaxis_title="Ply",
        yaxis_title="Eval (pawns)",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=50, r=20, t=20, b=50),
        height=200,
        autosize=True,
        plot_bgcolor="rgba(128, 128, 128, 0.3)",
        xaxis=dict(
            range=[0.5, len(evals) + 0.5],
            gridcolor="rgba(255,255,255,0.3)",
            zeroline=True,
            zerolinecolor="rgba(0,0,0,0.5)",
            zerolinewidth=2,
        ),
        yaxis=dict(
            range=[-8, 8],
            gridcolor="rgba(255,255,255,0.3)",
            zeroline=True,
            zerolinecolor="rgba(0,0,0,0.5)",
            zerolinewidth=2,
        ),
    )

    return fig


def _create_placeholder_graph(message: str) -> go.Figure:
    """Create placeholder graph with message.

    Args:
        message: Message to display

    Returns:
        Plotly figure with annotation
    """
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="rgba(100, 100, 100, 0.8)"),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=200,
        margin=dict(l=50, r=20, t=20, b=50),
        plot_bgcolor="rgba(128, 128, 128, 0.3)",
        autosize=True,
    )
    return fig
