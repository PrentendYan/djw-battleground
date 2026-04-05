# -*- coding: utf-8 -*-
"""Simulation results display component."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

from battleground.types import SimulationResult


def render_results(result: SimulationResult) -> None:
    """Display simulation results with charts."""
    st.subheader("Simulation Results")
    st.text(result.summary())

    # Win/Tie/Loss bar
    col1, col2, col3 = st.columns(3)
    col1.metric("Win", f"{result.win_rate:.1%}")
    col2.metric("Tie", f"{result.tie_rate:.1%}")
    col3.metric("Loss", f"{result.loss_rate:.1%}")

    # Pie chart
    fig_pie = go.Figure(data=[go.Pie(
        labels=["Win", "Tie", "Loss"],
        values=[result.wins, result.ties, result.losses],
        marker_colors=["#4CAF50", "#FFC107", "#F44336"],
        textinfo="percent+label",
    )])
    fig_pie.update_layout(
        title="Outcome Distribution",
        height=300,
        margin=dict(t=40, b=20, l=20, r=20),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    # Damage distribution histograms
    col_win, col_loss = st.columns(2)

    with col_win:
        if result.win_damages:
            fig_win = go.Figure(data=[go.Histogram(
                x=result.win_damages,
                marker_color="#4CAF50",
                name="Win Damage",
            )])
            fig_win.update_layout(
                title=f"Win Damage (avg: {result.avg_win_damage:.1f})",
                xaxis_title="Damage",
                yaxis_title="Count",
                height=250,
                margin=dict(t=40, b=30, l=40, r=20),
            )
            st.plotly_chart(fig_win, use_container_width=True)
        else:
            st.info(f"Avg win damage: {result.avg_win_damage:.1f}")

    with col_loss:
        if result.loss_damages:
            fig_loss = go.Figure(data=[go.Histogram(
                x=result.loss_damages,
                marker_color="#F44336",
                name="Loss Damage",
            )])
            fig_loss.update_layout(
                title=f"Loss Damage (avg: {result.avg_loss_damage:.1f})",
                xaxis_title="Damage",
                yaxis_title="Count",
                height=250,
                margin=dict(t=40, b=30, l=40, r=20),
            )
            st.plotly_chart(fig_loss, use_container_width=True)
        else:
            st.info(f"Avg loss damage: {result.avg_loss_damage:.1f}")
