# main.py
import streamlit as st
import pandas as pd
import os
from config import PRIORITY_ORDER
from modules.git_manager import git_pull_all, git_commit_push, get_git_diff, git_clone_from_file
from modules.data_loader import load_data
from modules.yaml_manager import get_file_content, save_file_content, get_chart_values_content
from modules.ui import inject_table_css
from code_editor import code_editor

st.set_page_config(page_title="CDC Matrix", layout="wide")

# --- SETUP INIZIALE ---
if 'root_dir' not in st.session_state:
    st.title("⚙️ Configurazione Iniziale")
    
    col_setup, col_info = st.columns([2, 1])
    
    with col_setup:
        st.subheader("Dove si trovano (o dove vuoi scaricare) i progetti?")
        path_input = st.text_input("Percorso Cartella Root", value="../cdc")
        
        projects_file = os.path.join(os.path.dirname(__file__), "progetti.txt")
        file_exists = os.path.exists(projects_file)

        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("📂 Usa Cartella Esistente", use_container_width=True):
            if os.path.exists(path_input):
                st.session_state['root_dir'] = path_input
                st.rerun()
            else:
                st.error(f"La cartella {path_input} non esiste. Vuoi clonare i progetti?")

        btn_clone = col_btn2.button("⬇️ Clona da progetti.txt", 
                                   use_container_width=True, 
                                   disabled=not file_exists,
                                   help="Richiede file 'progetti.txt' nella root dell'app")
        
        if btn_clone:
            with st.spinner("⏳ Clonazione repository in corso..."):
                ok, log = git_clone_from_file(path_input, projects_file)
                if ok:
                    st.success("Operazione completata!")
                    with st.expander("Dettagli Clonazione"):
                        st.text(log)
                    if os.path.exists(path_input):
                        st.session_state['root_dir'] = path_input
                        if st.button("🚀 Avvia Dashboard"):
                            st.rerun()
                else:
                    st.error(log)

    with col_info:
        st.info("""
        **Primo Avvio?**
        1. Crea una cartella vuota (es. `cdc`).
        2. Inserisci il percorso a sinistra.
        3. Assicurati di avere `progetti.txt` con la lista dei repo.
        4. Clicca **Clona**.
        """)
    st.stop()

ROOT_DIR = st.session_state['root_dir']
inject_table_css()

if 'init' not in st.session_state:
    git_pull_all(ROOT_DIR)
    st.session_state['init'] = True

# HEADER
col1, col2 = st.columns([3, 1])
with col1: st.title("📦 CDC Version Manager")
with col2: 
    if st.button("🔄 Git Pull All"):
        st.session_state.pop('init', None)
        st.rerun()

# DATA LOAD
df = load_data(ROOT_DIR)

# SIDEBAR
st.sidebar.title("🛠️ Contesto")
sel_proj = None
sel_env = None

if not df.empty:
    sel_proj = st.sidebar.selectbox("Progetto", df['Progetto'].unique())
    if sel_proj:
        valid_envs = sorted(df[df['Progetto'] == sel_proj]['Ambiente'].unique())
        sel_env = st.sidebar.selectbox("Ambiente", valid_envs)

# --- TABELLE DIVISE PER CLOUD ---
if not df.empty:
    # 1. Raggruppamento dati (unisce Kustomize e Terraform)
    df_display = df.copy()
    df_grouped = df_display.groupby(['Progetto', 'Ambiente'], as_index=False).agg({
        'Info': lambda x: '\n\n'.join(x) 
    })
    
    # 2. Split AWS / Azure
    mask_azure = df_grouped['Ambiente'].str.endswith('-az')
    df_azure = df_grouped[mask_azure]
    df_aws = df_grouped[~mask_azure]

    # Funzione helper per renderizzare
    def render_matrix(dataframe):
        if dataframe.empty:
            st.info("Nessun ambiente trovato per questo cloud provider.")
            return
        
        matrix = dataframe.pivot(index="Progetto", columns="Ambiente", values="Info")
        found = list(matrix.columns)
        current_order = [c for c in PRIORITY_ORDER if c in found] + sorted([c for c in found if c not in PRIORITY_ORDER])
        st.table(matrix.reindex(columns=current_order).fillna("-"))

    # 3. Visualizzazione a Tab
    tab_aws, tab_azure = st.tabs(["☁️ AWS", "🔷 Azure"])
    
    with tab_aws:
        render_matrix(df_aws)
        
    with tab_azure:
        render_matrix(df_azure)

else:
    st.warning("Nessun dato trovato.")

# --- EDITOR (Invariato) ---
st.divider()

editor_props = {"style": {"borderRadius": "5px", "fontSize": "14px"}, "wrapLines": True}
editor_options = {"showLineNumbers": True, "showGutter": True, "showPrintMargin": False, "wrap": True, "tabSize": 2}
custom_buttons = [
    {"name": "Salva", "feather": "Save", "hasText": True, "commands": ["submit"], "style": {"top": "0.25rem", "right": "6rem", "backgroundColor": "#28a745", "color": "white"}},
    {"name": "Copia", "feather": "Copy", "hasText": True, "alwaysOn": True, "commands": ["copyAll"], "style": {"top": "0.25rem", "right": "0.4rem"}}
]

if sel_proj and sel_env:
    rows = df[(df['Progetto'] == sel_proj) & (df['Ambiente'] == sel_env)]
    
    if rows.empty:
        st.info("Nessuna configurazione trovata per questa selezione.")
    else:
        st.subheader(f"📝 Modifica: {sel_proj} / {sel_env}")
        
        for idx, row in rows.iterrows():
            proj_type = row['Tipo']
            repo_folder = row['RepoFolder']
            
            with st.container():
                st.markdown(f"#### 👉 {proj_type} Config (`{repo_folder}`)")
                
                if proj_type == "Terraform":
                    tf_path = row['FilePath']
                    content = get_file_content(tf_path)
                    res_tf = code_editor(content, lang="terraform", height="400px", theme="default",
                                       buttons=custom_buttons, props=editor_props, options=editor_options,
                                       key=f"ed_tf_{sel_proj}_{sel_env}_{idx}")
                    if res_tf['type'] == "submit" and res_tf['text']:
                        ok, msg = save_file_content(tf_path, res_tf['text'])
                        if ok: st.success(f"✅ TF: {msg}"); st.rerun()
                        else: st.error(msg)

                elif proj_type == "Kustomize":
                    base_folder = os.path.join(ROOT_DIR, repo_folder, sel_env)
                    path_overlay = os.path.join(base_folder, "overlays", "kustomization.yaml")
                    path_base = os.path.join(base_folder, "base", "kustomization.yaml")
                    
                    t1, t2, t3 = st.tabs(["Overlay", "Base", "Reference"])
                    
                    with t1:
                        cnt = get_file_content(path_overlay)
                        res = code_editor(cnt, lang="yaml", height="300px", theme="default", buttons=custom_buttons, props=editor_props, options=editor_options, key=f"ed_ov_{sel_proj}_{sel_env}_{idx}")
                        if res['type'] == "submit" and res['text']: save_file_content(path_overlay, res['text']); st.rerun()
                    
                    with t2:
                        cnt = get_file_content(path_base)
                        res = code_editor(cnt, lang="yaml", height="300px", theme="default", buttons=custom_buttons, props=editor_props, options=editor_options, key=f"ed_ba_{sel_proj}_{sel_env}_{idx}")
                        if res['type'] == "submit" and res['text']: save_file_content(path_base, res['text']); st.rerun()
                        
                    with t3:
                        val_cont, val_path = get_chart_values_content(ROOT_DIR, sel_proj)
                        if val_cont: code_editor(val_cont, lang="yaml", height="400px", theme="default", options={**editor_options, "readOnly":True}, buttons=[custom_buttons[1]], key=f"ed_ref_{sel_proj}_{idx}")

                diff_text = get_git_diff(ROOT_DIR, repo_folder)
                if diff_text:
                    st.warning(f"⚠️ Modifiche pendenti in {repo_folder}")
                    with st.expander("🔍 Git Diff", expanded=False):
                        st.code(diff_text, language="diff")
                    
                    c1, c2 = st.columns([4, 1])
                    msg = c1.text_input("Messaggio Commit", key=f"msg_{repo_folder}")
                    if c2.button(f"Push {proj_type}", key=f"btn_push_{repo_folder}"):
                        if msg:
                            with st.spinner("Push..."):
                                ok, res = git_commit_push(os.path.join(ROOT_DIR, repo_folder), msg)
                                if ok: st.success(res); st.rerun()
                                else: st.error(res)
                        else: st.warning("Messaggio mancante")
                st.divider()

else:
    st.info("👈 Seleziona un progetto.")