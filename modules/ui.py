# modules/ui.py
import streamlit as st

def inject_table_css():
    """
    Forza lo scroll orizzontale e impedisce che le colonne si schiaccino.
    """
    st.markdown("""
    <style>
        /* 1. Rende la tabella scrollabile orizzontalmente */
        [data-testid="stTable"] {
            overflow-x: auto !important;
            display: block !important;
        }

        /* 2. Impone una larghezza minima alle colonne */
        table td, table th {
            min-width: 180px !important; /* Allarga questo valore se serve più spazio */
            max-width: 300px !important;
            white-space: pre-wrap !important; /* Rispetta i "a capo" (\n) */
            vertical-align: top !important;
        }
        
        /* Opzionale: Colore header per leggibilità */
        thead tr th {
            position: sticky; 
            left: 0;
        }
    </style>
    """, unsafe_allow_html=True)

def format_cell_text(tag, chart):
    # \n manda a capo
    return f"🐳 App: {tag}\n📦 Chart: {chart}"