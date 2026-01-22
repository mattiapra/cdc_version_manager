import streamlit as st
import pandas as pd
import os
import subprocess
from ruamel.yaml import YAML

# --- CONFIGURAZIONE ---
ROOT_DIR = "./cdc"  # La cartella corrente (workspace/cdc)
st.set_page_config(page_title="Kustomize Dashboard", layout="wide")

# Setup YAML
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# --- FUNZIONI GIT ---
def git_pull_all():
    """Esegue git pull su tutte le cartelle -kustomization"""
    logs = []
    
    if not os.path.exists(ROOT_DIR):
        return ["❌ Root dir non trovata"]

    # Scansiona le cartelle
    repos = [f for f in os.listdir(ROOT_DIR) 
             if f.endswith("-kustomization") and os.path.isdir(os.path.join(ROOT_DIR, f))]

    progress_text = "Sincronizzazione repository Git in corso..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(repos)
    for i, repo in enumerate(repos):
        repo_path = os.path.join(ROOT_DIR, repo)
        
        # Aggiorna barra progresso
        my_bar.progress((i + 1) / total, text=f"Pulling {repo}...")
        
        # Esegui Git Pull
        try:
            # -C dice a git di eseguire il comando in quella cartella specifica
            result = subprocess.run(
                ["git", "-C", repo_path, "pull"], 
                capture_output=True, 
                text=True, 
                timeout=15 # Timeout per evitare blocchi infiniti
            )
            
            if result.returncode == 0:
                if "Already up to date" in result.stdout:
                    logs.append(f"✅ {repo}: Già aggiornato")
                else:
                    logs.append(f"⬇️ {repo}: Aggiornato con successo")
            else:
                logs.append(f"⚠️ {repo}: Errore - {result.stderr.strip()}")
                
        except Exception as e:
            logs.append(f"❌ {repo}: Eccezione - {str(e)}")

    my_bar.empty() # Rimuove la barra alla fine
    return logs

# --- FUNZIONI BACKEND YAML ---
def get_yaml_value(filepath, keys_path):
    if not os.path.exists(filepath): return None
    try:
        with open(filepath, 'r') as f:
            data = yaml.load(f)
            temp = data
            for key in keys_path:
                if isinstance(temp, list):
                    temp = temp[0] if len(temp) > 0 else None
                elif isinstance(temp, dict) and key in temp:
                    temp = temp[key]
                else:
                    return None
            return temp
    except Exception: return None

def update_yaml_file(project, env, type_, value):
    folder_name = f"{project}-kustomization"
    base_path = os.path.join(ROOT_DIR, folder_name, env)
    
    target_file = ""
    if type_ == 'image':
        target_file = os.path.join(base_path, "overlays", "kustomization.yaml")
    elif type_ == 'chart':
        target_file = os.path.join(base_path, "base", "kustomization.yaml")
        
    if not os.path.exists(target_file):
        return False, f"File non trovato: {target_file}"
        
    try:
        with open(target_file, 'r') as f:
            data = yaml.load(f)
            
        if type_ == 'image' and 'images' in data:
            data['images'][0]['newTag'] = value
        elif type_ == 'chart' and 'helmCharts' in data:
            data['helmCharts'][0]['version'] = value
        else:
            return False, "Struttura YAML non valida (chiave mancante)"
            
        with open(target_file, 'w') as f:
            yaml.dump(data, f)
        return True, "Aggiornamento riuscito!"
    except Exception as e:
        return False, str(e)

def load_data():
    data = []
    if not os.path.exists(ROOT_DIR): return pd.DataFrame()

    for folder in os.listdir(ROOT_DIR):
        if folder.endswith("-kustomization"):
            project_name = folder.replace("-kustomization", "")
            folder_path = os.path.join(ROOT_DIR, folder)
            
            if os.path.isdir(folder_path):
                for env in os.listdir(folder_path):
                    env_path = os.path.join(folder_path, env)
                    overlay_file = os.path.join(env_path, "overlays", "kustomization.yaml")
                    base_file = os.path.join(env_path, "base", "kustomization.yaml")
                    
                    if os.path.exists(overlay_file):
                        tag = get_yaml_value(overlay_file, ['images', 'newTag']) or "N/D"
                        chart = get_yaml_value(base_file, ['helmCharts', 'version']) or "N/D"

                        tag = tag["newTag"][:15] if isinstance(tag, dict) else tag
                        chart = chart["version"][:15] if isinstance(chart, dict) else chart
                        
                        data.append({
                            "Progetto": project_name,
                            "Ambiente": env,
                            "Display": f"🖼️ {tag} | 📦 {chart}"
                        })
    return pd.DataFrame(data)

# --- STARTUP LOGIC (GIT PULL) ---
# Usiamo st.session_state per assicurarci che giri SOLO la prima volta che apri la pagina
if 'initial_sync_done' not in st.session_state:
    with st.spinner('🚀 Avvio Dashboard: Sincronizzazione Git in corso...'):
        pull_logs = git_pull_all()
        st.session_state['initial_sync_done'] = True
        st.session_state['pull_logs'] = pull_logs
        # Toast notification (appare a destra in alto)
        st.toast("Repository aggiornati con successo!", icon="✅")

# --- INTERFACCIA ---
st.title("🚀 Kustomize Version Manager")

# Expander per vedere i log del pull (utile per debug)
with st.expander("📜 Log Sincronizzazione Git (Ultimo aggiornamento)"):
    if 'pull_logs' in st.session_state:
        for log in st.session_state['pull_logs']:
            st.text(log)

df = load_data()

if not df.empty:
    matrix = df.pivot(index="Progetto", columns="Ambiente", values="Display")
    st.dataframe(matrix.fillna("-"), use_container_width=True, height=500)
else:
    st.warning("Nessun progetto trovato.")

# --- SIDEBAR ---
st.sidebar.header("🛠️ Gestione")

# Bottone manuale per ri-sincronizzare
if st.sidebar.button("🔄 Forza Git Pull"):
    st.session_state.pop('initial_sync_done', None) # Resetta lo stato
    st.rerun() # Ricarica la pagina (che scatenerà il pull all'inizio)

st.sidebar.divider()
st.sidebar.subheader("Aggiorna Versione")

if not df.empty:
    projects_list = sorted(df['Progetto'].unique())
    selected_project = st.sidebar.selectbox("Progetto", projects_list)
    available_envs = sorted(df[df['Progetto'] == selected_project]['Ambiente'].unique())
    selected_env = st.sidebar.selectbox("Ambiente", available_envs)
    update_type = st.sidebar.radio("Tipo", ["image", "chart"], horizontal=True)
    new_value = st.sidebar.text_input("Nuovo Valore")
    
    if st.sidebar.button("Salva Modifica", type="primary"):
        if new_value:
            success, msg = update_yaml_file(selected_project, selected_env, update_type, new_value)
            if success:
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)