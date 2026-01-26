# main.py
import streamlit as st
import pandas as pd
import os
import json
from config import PRIORITY_ORDER
from modules.git_manager import git_pull_all, git_commit_push, get_git_diff, git_clone_from_file, git_update_self
from modules.data_loader import load_data
from modules.yaml_manager import get_file_content, save_file_content, get_chart_values_content, generate_completions_from_yaml
from modules.ui import inject_table_css
from code_editor import code_editor

st.set_page_config(page_title="CDC Matrix", layout="wide")

# --- GESTIONE SALVATAGGIO CONFIGURAZIONE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
PROJECTS_FILE = os.path.join(BASE_DIR, "progetti.txt")

def save_settings(path):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"root_dir": path}, f)
    except Exception as e:
        st.error(f"Errore salvataggio settings: {e}")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                return data.get("root_dir")
        except:
            return None
    return None

def reset_settings():
    if os.path.exists(SETTINGS_FILE):
        os.remove(SETTINGS_FILE)
    if 'root_dir' in st.session_state:
        del st.session_state['root_dir']
    if 'init' in st.session_state:
        del st.session_state['init']
    st.rerun()

# --- CARICAMENTO AUTOMATICO PATH ---
if 'root_dir' not in st.session_state:
    saved_path = load_settings()
    if saved_path and os.path.exists(saved_path):
        st.session_state['root_dir'] = saved_path
    else:
        st.title("⚙️ Configurazione Iniziale")
        
        col_setup, col_info = st.columns([2, 1])
        with col_setup:
            st.subheader("Dove si trovano i progetti?")
            path_input = st.text_input("Percorso Cartella Root", value="../cdc")
            file_exists = os.path.exists(PROJECTS_FILE)

            c1, c2 = st.columns(2)
            if c1.button("📂 Usa Cartella Esistente", use_container_width=True):
                if os.path.exists(path_input):
                    st.session_state['root_dir'] = path_input
                    save_settings(path_input)
                    st.rerun()
                else:
                    st.error(f"Cartella non trovata: {path_input}")

            btn_clone = c2.button("⬇️ Clona da progetti.txt", use_container_width=True, disabled=not file_exists)
            if btn_clone:
                with st.spinner("⏳ Clonazione..."):
                    ok, log = git_clone_from_file(path_input, PROJECTS_FILE)
                    if ok:
                        st.success("Fatto!")
                        if os.path.exists(path_input):
                            st.session_state['root_dir'] = path_input
                            save_settings(path_input)
                            st.rerun()
                    else:
                        st.error(log)
        st.stop()

ROOT_DIR = st.session_state['root_dir']
inject_table_css()

if 'init' not in st.session_state:
    git_pull_all(ROOT_DIR)
    st.session_state['init'] = True

# HEADER
col1, col2 = st.columns([2, 1])
with col1: st.title("📦 CDC Version Manager")

with col2:
    bc1, bc2, bc3 = st.columns([1, 1, 0.5])
    if bc1.button("🔄 Pull Progetti", help="Aggiorna i repo gestiti"):
        st.session_state.pop('init', None)
        st.rerun()
    if bc2.button("⬆️ Update App", help="Aggiorna questo software da Git"):
        with st.spinner("Aggiornamento app in corso..."):
            ok, msg = git_update_self(BASE_DIR)
            if ok:
                st.toast(msg, icon="✅")
                if "scaricato" in msg:
                    import time
                    time.sleep(1)
                    st.rerun()
            else:
                st.error(msg)
    if bc3.button("⚙️", help="Cambia cartella root"):
        reset_settings()

# DATA LOAD
df = load_data(ROOT_DIR)

# --- CALCOLO MASCHERE CLOUD ---
if not df.empty:
    repo_series = df['RepoFolder'].astype(str).str.strip().str.lower()
    env_series = df['Ambiente'].astype(str).str.strip().str.lower()
    
    is_az_repo = repo_series.str.endswith('-az') | repo_series.str.contains('-az-')
    is_az_env = env_series.str.endswith('-az')
    mask_azure = is_az_repo | is_az_env
else:
    mask_azure = pd.Series([False] * len(df))

# --- SIDEBAR INTELLIGENTE ---
st.sidebar.title("🛠️ Contesto")

# 1. Selettore Cloud Provider (SENZA OPZIONE "TUTTI")
cloud_filter = st.sidebar.radio("Provider", ["☁️ AWS", "🔷 Azure"], horizontal=True)

# 2. Filtraggio DataFrame Sidebar
if df.empty:
    df_sidebar = pd.DataFrame()
else:
    if cloud_filter == "☁️ AWS":
        df_sidebar = df[~mask_azure]
    else: # Azure
        df_sidebar = df[mask_azure]

sel_proj = None
sel_env_display = None
target_real_envs = []

if not df_sidebar.empty:
    sel_proj = st.sidebar.selectbox("Progetto", df_sidebar['Progetto'].unique())
    
    if sel_proj:
        # Recupera ambienti dal DF filtrato
        raw_envs = sorted(df_sidebar[df_sidebar['Progetto'] == sel_proj]['Ambiente'].unique())
        
        # Mappa pulizia nomi (es. prod-az -> prod)
        env_map = {}
        for real_env in raw_envs:
            clean_env = real_env
            if clean_env.endswith('-az'):
                clean_env = clean_env[:-3]
            
            if clean_env not in env_map:
                env_map[clean_env] = []
            env_map[clean_env].append(real_env)
            
        sel_env_display = st.sidebar.selectbox("Ambiente", sorted(env_map.keys()))
        if sel_env_display:
            target_real_envs = env_map[sel_env_display]

# --- TABELLA ---
if not df.empty:
    # Dividiamo i dati
    df_aws_raw = df[~mask_azure].copy()
    df_azure_raw = df[mask_azure].copy()

    # Normalizzazione visuale Azure
    if not df_azure_raw.empty:
        df_azure_raw['Ambiente'] = df_azure_raw['Ambiente'].apply(
            lambda x: x[:-3] if str(x).strip().endswith('-az') else x
        )

    def render_matrix(dataframe, title):
        if dataframe.empty:
            st.info(f"Nessun progetto trovato per {title}.")
            return
            
        df_grouped = dataframe.groupby(['Progetto', 'Ambiente'], as_index=False).agg({
            'Info': lambda x: '\n\n'.join(x)
        })
        
        matrix = df_grouped.pivot(index="Progetto", columns="Ambiente", values="Info")
        found = list(matrix.columns)
        current_order = [c for c in PRIORITY_ORDER if c in found] + sorted([c for c in found if c not in PRIORITY_ORDER])
        st.table(matrix.reindex(columns=current_order).fillna("-"))

    t1, t2 = st.tabs(["☁️ AWS", "🔷 Azure"])
    with t1: render_matrix(df_aws_raw, "AWS")
    with t2: render_matrix(df_azure_raw, "Azure")
else:
    st.warning(f"Nessun dato in {ROOT_DIR}")

# --- EDITOR & PUSH ---
st.divider()

editor_props = {"style": {"borderRadius": "5px", "fontSize": "14px"}, "wrapLines": True}
editor_options = {
    "showLineNumbers": True, 
    "showGutter": True, 
    "showPrintMargin": False, 
    "wrap": True, 
    "tabSize": 2,
    "enableBasicAutocompletion": True,
    "enableLiveAutocompletion": True,
    "enableSnippets": True
}

custom_buttons = [
    {"name": "Salva", "feather": "Save", "hasText": True, "commands": ["submit"], "style": {"top": "0.25rem", "right": "6rem", "backgroundColor": "#28a745", "color": "white"}},
    {"name": "Copia", "feather": "Copy", "hasText": True, "alwaysOn": True, "commands": ["copyAll"], "style": {"top": "0.25rem", "right": "0.4rem"}}
]

if sel_proj and target_real_envs:
    # Filtriamo le righe: Progetto + Ambienti Reali Mappati
    rows = df[(df['Progetto'] == sel_proj) & (df['Ambiente'].isin(target_real_envs))]
    
    # Applicazione del filtro Cloud anche qui per sicurezza
    # (Esempio: se un progetto ha lo stesso nome su entrambi i cloud ma cartelle diverse)
    if cloud_filter == "☁️ AWS":
        rows = rows[~mask_azure.loc[rows.index]]
    else: # Azure
        rows = rows[mask_azure.loc[rows.index]]
    
    if rows.empty:
        st.info(f"Nessuna configurazione trovata per {sel_proj} su {cloud_filter}.")
    else:
        st.subheader(f"📝 Modifica: {sel_proj} / {sel_env_display}")
        
        for idx, row in rows.iterrows():
            proj_type = row['Tipo']
            repo_folder = row['RepoFolder']
            real_env_name = row['Ambiente']
            
            custom_completions = []
            if proj_type == "Kustomize":
                ref_content, _ = get_chart_values_content(ROOT_DIR, sel_proj)
                if ref_content:
                    custom_completions = generate_completions_from_yaml(ref_content)
            
            with st.container():
                # Dettagli visivi
                suffix = f" (Env: {real_env_name})" if real_env_name != sel_env_display else ""
                cloud_badge = "🔷" if mask_azure[idx] else "☁️"
                
                st.markdown(f"#### 👉 {cloud_badge} {proj_type} (`{repo_folder}`){suffix}")
                
                # EDITOR
                if proj_type == "Terraform":
                    tf_path = row['FilePath']
                    res_tf = code_editor(
                        get_file_content(tf_path), 
                        lang="terraform", 
                        height="400px", 
                        theme="default", 
                        buttons=custom_buttons, 
                        props=editor_props, 
                        options=editor_options, 
                        key=f"ed_tf_{sel_proj}_{real_env_name}_{idx}"
                    )
                    if res_tf['type'] == "submit" and res_tf['text']:
                        ok, msg = save_file_content(tf_path, res_tf['text'])
                        if ok: st.success(f"✅ TF: {msg}"); st.rerun()
                        else: st.error(msg)

                elif proj_type == "Kustomize":
                    base_folder = os.path.join(ROOT_DIR, repo_folder, real_env_name)
                    path_overlay = os.path.join(base_folder, "overlays", "kustomization.yaml")
                    path_base = os.path.join(base_folder, "base", "kustomization.yaml")
                    
                    tb1, tb2, tb3 = st.tabs(["Overlay", "Base", "Ref"])
                    with tb1:
                        res = code_editor(
                            get_file_content(path_overlay), 
                            lang="yaml", 
                            height="300px", 
                            theme="default", 
                            buttons=custom_buttons, 
                            props=editor_props, 
                            options=editor_options,
                            completions=custom_completions,
                            key=f"ed_ov_{sel_proj}_{real_env_name}_{idx}"
                        )
                        if res['type'] == "submit" and res['text']: save_file_content(path_overlay, res['text']); st.rerun()
                    with tb2:
                        res = code_editor(
                            get_file_content(path_base), 
                            lang="yaml", 
                            height="300px", 
                            theme="default", 
                            buttons=custom_buttons, 
                            props=editor_props, 
                            options=editor_options,
                            completions=custom_completions,
                            key=f"ed_ba_{sel_proj}_{real_env_name}_{idx}"
                        )
                        if res['type'] == "submit" and res['text']: save_file_content(path_base, res['text']); st.rerun()
                    with tb3:
                        val_cont, val_path = get_chart_values_content(ROOT_DIR, sel_proj)
                        if val_cont: 
                            code_editor(val_cont, lang="yaml", height="400px", theme="default", options={**editor_options, "readOnly":True}, buttons=[custom_buttons[1]], key=f"ed_ref_{sel_proj}_{idx}")

                # GIT SECTION
                st.write("") 
                diff_text = get_git_diff(ROOT_DIR, repo_folder)
                
                if diff_text:
                    st.warning(f"⚠️ Modifiche non committate in {repo_folder}")
                    with st.expander("🔍 Vedi Git Diff", expanded=False):
                        st.code(diff_text, language="diff")
                else:
                    st.success(f"✅ {repo_folder}: Working tree clean.")

                with st.expander(f"🚀 Git Commit & Push ({repo_folder})", expanded=True):
                    c1, c2 = st.columns([4, 1])
                    msg = c1.text_input("Messaggio Commit", key=f"msg_{repo_folder}")
                    
                    if c2.button("Push", key=f"btn_push_{repo_folder}", use_container_width=True):
                        if msg:
                            with st.spinner(f"Pushing {repo_folder}..."):
                                ok, res = git_commit_push(os.path.join(ROOT_DIR, repo_folder), msg)
                                if ok: st.success(res); st.rerun()
                                else: st.error(res)
                        else:
                            st.warning("Inserisci messaggio.")
                st.divider()

else:
    st.info("👈 Seleziona Provider, Progetto e Ambiente.")