import streamlit as st
import pandas as pd
import os
import json
import time
from config import PRIORITY_ORDER
# Assicurati che check_app_updates sia stato aggiunto a git_manager
from modules.git_manager import git_pull_all, git_commit_push, get_git_diff, git_clone_from_file, git_update_self, git_hard_reset, git_clone_related_chart, check_app_updates
from modules.data_loader import load_data
# Assicurati che is_valid_yaml sia stato aggiunto a yaml_manager
from modules.yaml_manager import get_file_content, save_file_content, get_chart_values_content, generate_completions_from_yaml, is_valid_yaml
# Assicurati che is_valid_terraform sia stato aggiunto a terraform_manager
from modules.terraform_manager import get_tf_version, is_valid_terraform
from modules.ecr_manager import get_ecr_versions
from modules.ui import inject_table_css
from code_editor import code_editor

# --- 1. CONFIGURAZIONE PAGINA RINOMINATA ---
st.set_page_config(page_title="CDC Version Manager", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, ".cdc_config", "settings.json")
PROJECTS_FILE = os.path.join(BASE_DIR, "progetti.txt")

# --- FUNZIONI DI UTILITÀ (SETTINGS) ---
def update_settings(new_data):
    current_data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f: current_data = json.load(f)
        except: pass
    current_data.update(new_data)
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump(current_data, f, indent=2)
    except Exception as e: print(f"Errore settings: {e}")

def load_settings():
    conf_dir = os.path.join(BASE_DIR, ".cdc_config")
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir, exist_ok=True)

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def reset_settings():
    if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
    if 'root_dir' in st.session_state: del st.session_state['root_dir']
    if 'init' in st.session_state: del st.session_state['init']
    st.rerun()

app_settings = load_settings()
root_dir_setting = app_settings.get("root_dir")

# --- WIZARD CONFIGURAZIONE INIZIALE ---
if 'root_dir' not in st.session_state:
    if root_dir_setting and os.path.exists(root_dir_setting):
        st.session_state['root_dir'] = root_dir_setting
    else:
        st.title("⚙️ Configurazione Iniziale")
        st.code(f"""echo "alias cdc='(cd {BASE_DIR} && streamlit run main.py)'" >> ~/.profile && source ~/.profile""", language="bash")
        c1, c2 = st.columns([2, 1])
        with c1:
            path_input = st.text_input("Percorso Root", value="../cdc")
            file_exists = os.path.exists(PROJECTS_FILE)
            col_a, col_b = st.columns(2)
            if col_a.button("📂 Usa Cartella", use_container_width=True):
                if os.path.exists(path_input):
                    st.session_state['root_dir'] = path_input
                    update_settings({"root_dir": path_input})
                    st.rerun()
                else: st.error("Cartella non trovata")
            btn_clone = col_b.button("⬇️ Clona da progetti.txt", use_container_width=True, disabled=not file_exists)
            if btn_clone:
                with st.spinner("Elaborazione..."):
                    ok, log = git_clone_from_file(path_input, PROJECTS_FILE)
                    if ok:
                        st.success("Fatto!")
                        if os.path.exists(path_input):
                            st.session_state['root_dir'] = path_input
                            update_settings({"root_dir": path_input})
                            st.rerun()
                    else: st.error(log)
        st.stop()

ROOT_DIR = st.session_state['root_dir']
inject_table_css()

# --- 2. INIZIALIZZAZIONE (PULL & UPDATE CHECK) ---
if 'init' not in st.session_state:
    with st.spinner("🔄 Inizializzazione: Pull progetti e check aggiornamenti App..."):
        # Esegue pull parallelo e salva lo stato (Successo/Fallimento)
        st.session_state['pull_status'] = git_pull_all(ROOT_DIR)
        
        # Controlla se ci sono aggiornamenti dell'app stessa
        st.session_state['app_update_available'] = check_app_updates(BASE_DIR)
        
    st.session_state['init'] = True

# --- HEADER E BOTTONI ---
col1, col2 = st.columns([2, 1])
with col1: st.title("📦 CDC Version Manager")
with col2:
    b1, b2, b3 = st.columns([1, 1, 0.5])
    
    # Bottone Force Pull
    if b1.button("🔄 Pull All"): 
        st.session_state.pop('init', None)
        st.rerun()

    # --- 4. BOTTONE AGGIORNAMENTO APP DINAMICO ---
    has_update = st.session_state.get('app_update_available', False)
    btn_label = "⬇️ Aggiorna!" if has_update else "✅ App OK"
    btn_type = "primary" if has_update else "secondary"
    help_txt = "Nuova versione disponibile!" if has_update else "Nessun aggiornamento rilevato"

    if b2.button(btn_label, type=btn_type, help=help_txt):
        with st.spinner("Scarico aggiornamento applicazione..."):
            ok, msg = git_update_self(BASE_DIR)
            st.toast(msg, icon="✅" if ok else "❌")
            if ok and "scaricato" in msg:
                time.sleep(1)
                st.rerun()
            else:
                # Se fallisce o era già pari, ricontrolla
                st.session_state['app_update_available'] = check_app_updates(BASE_DIR)
                st.rerun()
                
    # Bottone Reset Settings
    if b3.button("⚙️"): reset_settings()

df = load_data(ROOT_DIR)

# --- FILTRI E SIDEBAR ---
if not df.empty:
    repo_s = df['RepoFolder'].astype(str).str.strip().str.lower()
    env_s = df['Ambiente'].astype(str).str.strip().str.lower()
    mask_azure = repo_s.str.endswith('-az') | repo_s.str.contains('-az-') | env_s.str.endswith('-az')
else:
    mask_azure = pd.Series([False]*len(df))

st.sidebar.title("🛠️ Contesto")
last_provider = app_settings.get("last_provider", "☁️ AWS")
last_proj = app_settings.get("last_proj", None)
last_env = app_settings.get("last_env", None)

prov_options = ["☁️ AWS", "🔷 Azure"]
prov_idx = prov_options.index(last_provider) if last_provider in prov_options else 0
cloud_filter = st.sidebar.radio("Provider", prov_options, index=prov_idx, horizontal=True)

df_sidebar = pd.DataFrame()
if not df.empty:
    df_sidebar = df[~mask_azure] if cloud_filter == "☁️ AWS" else df[mask_azure]

sel_proj = None
sel_env_display = None
target_real_envs = []

if not df_sidebar.empty:
    proj_opts = sorted(df_sidebar['Progetto'].unique())
    proj_idx = 0
    if last_proj in proj_opts: proj_idx = proj_opts.index(last_proj)
    sel_proj = st.sidebar.selectbox("Progetto", proj_opts, index=proj_idx)
    
    if sel_proj:
        raw_envs = sorted(df_sidebar[df_sidebar['Progetto'] == sel_proj]['Ambiente'].unique())
        env_map = {}
        for r_env in raw_envs:
            c_env = r_env[:-3] if r_env.endswith('-az') else r_env
            if c_env not in env_map: env_map[c_env] = []
            env_map[c_env].append(r_env)
            
        env_opts = sorted(env_map.keys())
        env_idx = 0
        if last_env in env_opts: env_idx = env_opts.index(last_env)
        sel_env_display = st.sidebar.selectbox("Ambiente", env_opts, index=env_idx)
        if sel_env_display: target_real_envs = env_map[sel_env_display]

changes_to_save = {}
if cloud_filter != last_provider: changes_to_save["last_provider"] = cloud_filter
if sel_proj != last_proj: changes_to_save["last_proj"] = sel_proj
if sel_env_display != last_env: changes_to_save["last_env"] = sel_env_display
if changes_to_save:
    update_settings(changes_to_save)
    app_settings.update(changes_to_save)

if not df.empty:
    df_aws = df[~mask_azure].copy()
    df_az = df[mask_azure].copy()
    if not df_az.empty: df_az['Ambiente'] = df_az['Ambiente'].apply(lambda x: x[:-3] if str(x).endswith('-az') else x)

    # --- 3. RENDER TABLE AGGIORNATO (ICONE PROGETTO) ---
    def render_t(d, t):
        if d.empty: st.info(f"No data for {t}"); return
        
        # A. Recupera errori Pull (Triangolo)
        pull_status = st.session_state.get('pull_status', {})
        failed_repos = [r for r, ok in pull_status.items() if not ok]
        proj_with_errors = []
        if 'RepoFolder' in d.columns:
            proj_with_errors = d[d['RepoFolder'].isin(failed_repos)]['Progetto'].unique()

        # B. Recupera modifiche locali (Matita)
        proj_dirty_map = {}
        if 'IsChange' in d.columns:
            dirty_rows = d[d['IsChange'] == True]
            if not dirty_rows.empty:
                # Mappa Progetto -> Lista Ambienti
                proj_dirty_map = dirty_rows.groupby('Progetto')['Ambiente'].apply(lambda x: list(set(x))).to_dict()
        
        # C. Pivot Tabella
        g = d.groupby(['Progetto', 'Ambiente'], as_index=False).agg({
            'Info': lambda x: '<div class="inner-cell">' + 
                              '<br>'.join([str(val).replace('\n', '<br>') for val in x if str(val).strip() != ""]) + 
                              '</div>'
        })
        
        m = g.pivot(index="Progetto", columns="Ambiente", values="Info")
        m.columns.name = None 
        
        cols = [c for c in PRIORITY_ORDER if c in m.columns] + sorted([c for c in m.columns if c not in PRIORITY_ORDER])
        m = m.reindex(columns=cols).fillna("") 
        
        m_reset = m.reset_index()
        
        # D. Formattazione Colonna Progetto con Icone
        def format_project_cell(name):
            icons = ""
            
            # Icona Errore Pull
            if name in proj_with_errors:
                icons += '<span style="color:orange; cursor:help; margin-right:5px;" title="Git pull fallito">⚠️</span>'
            
            # Icona Modifiche Locali
            if name in proj_dirty_map:
                icons += f'<span style="cursor:help; margin-right:5px;" title="Modifiche non committate/pushate">✏️</span>'
            
            return f'<div class="inner-cell" style="font-weight:bold;">{icons}{name}</div>'
        
        m_reset["Progetto"] = m_reset["Progetto"].apply(format_project_cell)
        
        html_table = m_reset.to_html(classes="cdc-table", index=False, escape=False, border=0)
        st.markdown(f'<div class="cdc-table-container">{html_table}</div>', unsafe_allow_html=True)

    t1, t2 = st.tabs(["☁️ AWS", "🔷 Azure"])
    with t1: render_t(df_aws, "AWS")
    with t2: render_t(df_az, "Azure")

st.divider()

if st.button(f"🔍 Recupera versioni da ECR per {sel_proj}"):
    with st.spinner(f"Interrogando ECR per {sel_proj}..."):
        data, error = get_ecr_versions(sel_proj)
        
        if error:
            st.error(f"Errore nel recupero dati ECR: {error}")
            st.info("Nota: Assicurati che il repository esista su ECR e che il profilo 'saml' sia attivo.")
        else:
            repo_key = list(data.keys())[0]
            st.success(f"Trovate {len(data[repo_key])} versioni valide per '{repo_key}'")
            with st.expander("Vedi elenco versioni (Ordinate per data)"):
                st.table(data[repo_key])

st.divider()
ed_opts = {"showLineNumbers": True, "wrap": True, "enableBasicAutocompletion": True, "enableLiveAutocompletion": True}
# Configurazione bottone Salva "Floating"
btns = [
    {
        "name": "Salva",
        "feather": "Save",
        "hasText": True,
        "commands": ["submit"],  # Questo comando invia il form a Streamlit
        "bindKey": {"win": "Ctrl-s", "mac": "Cmd-s"}, # Tenta di bindare Ctrl+S
        "style": {
            "top": "0.4rem",        # Margine dall'alto (sempre visibile)
            "right": "0.4rem",      # Margine da destra
            "backgroundColor": "#28a745", # Verde successo
            "color": "white",
            "border": "1px solid #1e7e34",
            "borderRadius": "4px",  # Bordi arrotondati
            "padding": "0.2rem 0.5rem", # Padding ridotto per essere meno invasivo
            "fontSize": "0.85rem",  # Testo piccolo
            "opacity": "0.9",       # Leggera trasparenza
            "zIndex": "10"          # Assicura che stia sopra il testo
        }
    }
]
if sel_proj and target_real_envs:
    rows = df[(df['Progetto'] == sel_proj) & (df['Ambiente'].isin(target_real_envs))]
    rows = rows[~mask_azure.loc[rows.index]] if cloud_filter == "☁️ AWS" else rows[mask_azure.loc[rows.index]]

    if rows.empty: st.info("Nessuna riga trovata.")
    else:
        st.subheader(f"📝 Modifica: {sel_proj} / {sel_env_display}")
        for idx, row in rows.iterrows():
            ptype = row['Tipo']
            rfolder = row['RepoFolder']
            renv = row['Ambiente']
            
            comps = []
            ref_c, _ = get_chart_values_content(ROOT_DIR, sel_proj)
            if not ref_c: ref_c, _ = get_chart_values_content(ROOT_DIR, rfolder.replace("-kustomization",""))
            if ptype == "Kustomize" and ref_c: comps = generate_completions_from_yaml(ref_c)

            with st.container():
                st.markdown(f"#### 👉 {ptype} (`{rfolder}`) (Env: {renv})")
                
                # --- 5. EDITOR CON VALIDAZIONE ---
                if ptype == "Terraform":
                    tf_p = row['FilePath']
                    res = code_editor(get_file_content(tf_p), lang="terraform", height="300px", buttons=btns, options=ed_opts, key=f"tf_{idx}")
                    if res['type'] == "submit" and res['text']:
                        # Validazione
                        is_valid, err = is_valid_terraform(res['text'])
                        if is_valid:
                            save_file_content(tf_p, res['text'])
                            st.toast("✅ Salvato!", icon="💾")
                        else:
                            st.error(f"❌ Errore Sintassi Terraform: {err}")

                elif ptype == "Kustomize":
                    base_f = os.path.join(ROOT_DIR, rfolder, renv)
                    p_ov = os.path.join(base_f, "overlays", "kustomization.yaml")
                    p_ba = os.path.join(base_f, "base", "kustomization.yaml")
                    tb1, tb2, tb3 = st.tabs(["Overlay", "Base", "Chart Values"])
                    
                    with tb1:
                        r = code_editor(get_file_content(p_ov), lang="yaml", height="300px", buttons=btns, options=ed_opts, completions=comps, key=f"ov_{idx}")
                        if r['type'] == "submit" and r['text']: 
                            # Validazione
                            is_valid, err = is_valid_yaml(r['text'])
                            if is_valid:
                                save_file_content(p_ov, r['text'])
                                st.toast("✅ Overlay Salvato!", icon="💾")
                            else:
                                st.error(f"❌ Errore YAML: {err}")

                    with tb2:
                        r = code_editor(get_file_content(p_ba), lang="yaml", height="300px", buttons=btns, options=ed_opts, completions=comps, key=f"ba_{idx}")
                        if r['type'] == "submit" and r['text']: 
                            # Validazione
                            is_valid, err = is_valid_yaml(r['text'])
                            if is_valid:
                                save_file_content(p_ba, r['text'])
                                st.toast("✅ Base Salvato!", icon="💾")
                            else:
                                st.error(f"❌ Errore YAML: {err}")

                    with tb3:
                         if ref_c:
                             code_editor(ref_c, lang="yaml", height="300px", options={**ed_opts, "readOnly":True}, key=f"ref_{idx}")
                         else:
                             st.warning(f"File values.yaml non trovato per {sel_proj}.")
                             if st.button(f"⬇️ Scarica Chart ({sel_proj}-chart)", key=f"dl_chart_{idx}"):
                                 with st.spinner("Clonazione..."):
                                     ok, msg = git_clone_related_chart(ROOT_DIR, sel_proj, rfolder)
                                     if ok: st.success(msg); time.sleep(1); st.rerun()
                                     else: st.error(msg)
                
                diff = get_git_diff(ROOT_DIR, rfolder)
                if diff:
                    st.warning("⚠️ Modifiche non committate")
                    with st.expander("🔍 Vedi Git Diff", expanded=True): st.code(diff, language="diff")
                else: st.success("Working tree clean")

                with st.expander("🚀 Gestione Git"):
                    c1, c2 = st.columns([3, 1])
                    msg = c1.text_input("Messaggio", key=f"m_{idx}")
                    if c2.button("💾 Commit & Push", key=f"p_{idx}"):
                        if msg:
                            with st.spinner("Pushing..."):
                                ok, res = git_commit_push(os.path.join(ROOT_DIR, rfolder), msg)
                                if ok: st.success(res); time.sleep(1); st.rerun()
                                else: st.error(res)
                    st.divider()
                    cr1, cr2 = st.columns([3, 1])
                    cr1.caption("⚠️ Attenzione: Cancella modifiche locali.")
                    if cr2.button("🗑️ Ripristina", key=f"rst_{idx}", type="primary"):
                         with st.spinner("Reset..."):
                             ok, res = git_hard_reset(os.path.join(ROOT_DIR, rfolder))
                             st.toast(res); time.sleep(1); st.rerun()
                st.divider()