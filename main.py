# main.py
import streamlit as st
import pandas as pd
import os
from config import PRIORITY_ORDER
# Aggiungi get_git_diff agli import
from modules.git_manager import git_pull_all, git_commit_push, get_git_diff 
from modules.data_loader import load_data
from modules.yaml_manager import get_file_content, save_file_content, get_chart_values_content
from modules.ui import inject_table_css
from code_editor import code_editor

st.set_page_config(page_title="CDC Matrix", layout="wide")

# --- 1. SETUP ---
if 'root_dir' not in st.session_state:
    st.title("⚙️ Setup")
    path_input = st.text_input("Path Root Repositories", value="../cdc")
    if st.button("Conferma"):
        if os.path.exists(path_input):
            st.session_state['root_dir'] = path_input
            st.rerun()
    st.stop()

ROOT_DIR = st.session_state['root_dir']
inject_table_css()

if 'init' not in st.session_state:
    git_pull_all(ROOT_DIR)
    st.session_state['init'] = True

# --- 2. HEADER ---
col1, col2 = st.columns([3, 1])
with col1: st.title("📦 CDC Version Matrix")
with col2: 
    if st.button("🔄 Git Pull All"):
        st.session_state.pop('init', None)
        st.rerun()

# --- 3. DATA & TABLE ---
df = load_data(ROOT_DIR)

st.sidebar.title("🛠️ Contesto")
sel_proj = None
sel_env = None

if not df.empty:
    sel_proj = st.sidebar.selectbox("Progetto", df['Progetto'].unique())
    if sel_proj:
        valid_envs = sorted(df[df['Progetto'] == sel_proj]['Ambiente'].unique())
        sel_env = st.sidebar.selectbox("Ambiente", valid_envs)

    matrix = df.pivot(index="Progetto", columns="Ambiente", values="Info")
    found = list(matrix.columns)
    order = [c for c in PRIORITY_ORDER if c in found] + sorted([c for c in found if c not in PRIORITY_ORDER])
    st.table(matrix.reindex(columns=order).fillna("-"))
else:
    st.warning("Nessun dato trovato.")

# --- 4. EDITOR ---
st.divider()

editor_props = {"style": {"borderRadius": "5px", "fontSize": "14px"}, "wrapLines": True}
editor_options = {
    "showLineNumbers": True, "showGutter": True, "showPrintMargin": False, 
    "wrap": True, "tabSize": 2, "useSoftTabs": True
}
custom_buttons = [
    {"name": "Salva", "feather": "Save", "hasText": True, "commands": ["submit"], 
     "style": {"top": "0.25rem", "right": "6rem", "backgroundColor": "#28a745", "color": "white"}},
    {"name": "Copia", "feather": "Copy", "hasText": True, "alwaysOn": True, "commands": ["copyAll"],
     "style": {"top": "0.25rem", "right": "0.4rem"}}
]

if sel_proj and sel_env:
    st.subheader(f"📝 Editor Configurazione: {sel_proj} / {sel_env}")
    
    base_folder = os.path.join(ROOT_DIR, f"{sel_proj}-kustomization", sel_env)
    path_overlay = os.path.join(base_folder, "overlays", "kustomization.yaml")
    path_base = os.path.join(base_folder, "base", "kustomization.yaml")
    
    # Calcoliamo se ci sono differenze Git GLOBALI per questo progetto
    # Lo facciamo prima dei tab per decidere se mostrare l'alert
    current_diff = get_git_diff(ROOT_DIR, sel_proj)
    
    tab_overlay, tab_base, tab_ref = st.tabs(["Overlay (Ambiente)", "Base (Helm)", "🔍 Reference"])
    
    # Helper per salvare solo se cambiato
    def handle_save(filepath, new_content):
        old_content = get_file_content(filepath)
        # Normalizziamo le newlines per evitare falsi positivi
        if new_content.strip() == old_content.strip():
            st.toast("ℹ️ Nessuna modifica rilevata (file identico).")
            return
            
        ok, msg = save_file_content(filepath, new_content)
        if ok: 
            st.success(f"✅ {msg}")
            st.rerun() # Ricarica per aggiornare la Diff View
        else: st.error(f"❌ {msg}")

    # --- TAB OVERLAY ---
    with tab_overlay:
        content_overlay = get_file_content(path_overlay)
        res_overlay = code_editor(content_overlay, lang="yaml", height="400px", theme="default",
                                buttons=custom_buttons, props=editor_props, options=editor_options,
                                key=f"ed_ov_{sel_proj}_{sel_env}")
        if res_overlay['type'] == "submit" and res_overlay['text']:
            handle_save(path_overlay, res_overlay['text'])

    # --- TAB BASE ---
    with tab_base:
        content_base = get_file_content(path_base)
        res_base = code_editor(content_base, lang="yaml", height="400px", theme="default",
                             buttons=custom_buttons, props=editor_props, options=editor_options,
                             key=f"ed_ba_{sel_proj}_{sel_env}")
        if res_base['type'] == "submit" and res_base['text']:
            handle_save(path_base, res_base['text'])

    # --- TAB REFERENCE ---
    with tab_ref:
        val_cont, val_path = get_chart_values_content(ROOT_DIR, sel_proj)
        if val_cont:
            st.info(f"📖 `{val_path}`")
            code_editor(val_cont, lang="yaml", height="500px", theme="default",
                      options={**editor_options, "readOnly": True}, buttons=[custom_buttons[1]],
                      key=f"ed_ref_{sel_proj}")
        else:
            st.warning("Values.yaml non trovato.")

    # --- SEZIONE DIFF & COMMIT ---
    st.divider()
    
    # Mostriamo la Diff View se ci sono cambiamenti
    if current_diff:
        st.warning("⚠️ Ci sono modifiche salvate su disco ma non ancora committate!")
        with st.expander("🔍 Vedi Differenze (Git Diff)", expanded=True):
            st.code(current_diff, language="diff")
    else:
        st.info("✅ Nessuna modifica pendente (Working tree clean).")

    with st.expander("🚀 Invia Modifiche a Git", expanded=bool(current_diff)):
        c1, c2 = st.columns([4, 1])
        commit_msg = c1.text_input("Messaggio Commit", placeholder="Es. bump version...", label_visibility="collapsed")
        
        # Disabilita il pulsante se non c'è diff (opzionale, ma utile)
        if c2.button("Git Push", use_container_width=True, disabled=not current_diff):
            if commit_msg:
                with st.spinner("Push in corso..."):
                    ok, res = git_commit_push(os.path.join(ROOT_DIR, f"{sel_proj}-kustomization"), commit_msg)
                    if ok: 
                        st.success(res)
                        st.rerun()
                    else: st.error(res)
            else:
                st.warning("Inserisci un messaggio.")
else:
    st.info("👈 Seleziona progetto/ambiente.")