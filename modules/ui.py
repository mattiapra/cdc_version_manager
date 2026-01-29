import streamlit as st

def inject_table_css():
    # Definiamo i colori
    MAIN_BG = "rgb(14, 17, 23)"
    SECONDARY_BG = "#262730"
    TEXT_COLOR = "#FAFAFA"

    st.markdown(f"""
    <style>
        /* Contenitore Tabella Esterno */
        .cdc-table-container {{
            width: 100%;
            overflow-x: auto;
            max-height: 80vh;
            border: 1px solid {SECONDARY_BG};
            border-radius: 5px;
        }}

        /* Tabella */
        table.cdc-table {{
            width: 100%;
            border-collapse: separate; 
            border-spacing: 0;
            font-family: sans-serif;
            font-size: 14px;
            color: {TEXT_COLOR};
            background-color: {MAIN_BG};
            table-layout: auto;
        }}

        table.cdc-table td {{
            border-bottom: 1px solid {SECONDARY_BG};
            border-right: 1px solid {SECONDARY_BG};
            text-align: left;
            vertical-align: top;
            padding: 0;
            position: relative; 
        }}
        
        table.cdc-table th {{
            padding: 8px 12px;
            background-color: {SECONDARY_BG};
            color: {TEXT_COLOR};
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 1px solid #444;
            border-right: 1px solid #444;
            text-align: center;
        }}

        .no-select {{
            user-select: none;
            -webkit-user-select: none;
            cursor: default;
            margin-right: 4px;
        }}

        /* --- MAGIC CELL: ELLIPSIS + SCROLL --- */
        .inner-cell {{
            padding: 8px 12px;
            max-width: 140px;       /* Larghezza fissa */
            
            white-space: nowrap;    /* Tutto su una riga */
            display: block;
            
            /* STATO NORMALE: Mostra i puntini (...) */
            overflow: hidden; 
            text-overflow: ellipsis; 
            
            /* Transizione fluida opzionale */
            transition: all 0.2s ease;
        }}

        /* STATO HOVER: Abilita lo scroll */
        .inner-cell:hover, .inner-cell:focus, .inner-cell:focus-within, .inner-cell:active {{
            scrollbar-width: none;
            overflow-x: auto;       /* Compare la scrollbar */
            text-overflow: clip;    /* Rimuove i puntini per mostrare il testo reale */
            
            /* Opzionale: allarga leggermente la scrollbar hit-area */
            padding-bottom: 4px; 
        }}


        /* Scrollbar styling (sottile per non disturbare) */
        .inner-cell::-webkit-scrollbar {{ height: 0px; }}

        /* --- PRIMA COLONNA --- */
        table.cdc-table tr > *:first-child {{
            position: sticky;
            left: 0;
            background-color: {MAIN_BG} !important;
            z-index: 5;
            border-right: 2px solid {SECONDARY_BG};
        }}

        /* La prima colonna NON deve avere ellipsis, deve allargarsi sempre */
        table.cdc-table tr > *:first-child .inner-cell {{
            max-width: none !important;
            width: auto;
            overflow: visible;
            text-overflow: clip;
        }}
        
        table.cdc-table thead th:first-child {{
            z-index: 15;
            background-color: {SECONDARY_BG};
        }}

        table.cdc-table tbody tr:hover td {{
            background-color: {SECONDARY_BG};
        }}
        
        table.cdc-table tbody tr:hover td:first-child {{
            background-color: {MAIN_BG} !important;
            filter: brightness(130%);
        }}
    </style>
    """, unsafe_allow_html=True)