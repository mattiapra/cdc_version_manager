import os
import subprocess
import streamlit as st
import json
import re
from concurrent.futures import ThreadPoolExecutor

def _pull_single_repo(repo_full_path):
    """Funzione helper per il pull parallelo"""
    try:
        # Timeout breve per non bloccare tutto se un repo è irraggiungibile
        subprocess.run(
            ["git", "-C", repo_full_path, "pull"], 
            capture_output=True, 
            timeout=15, 
            check=False
        )
        return True
    except: 
        return False

def git_pull_all(root_dir):
    """
    Esegue git pull su tutte le sottocartelle in PARALLELO.
    Molto più veloce dell'approccio sequenziale.
    """
    if not os.path.exists(root_dir): return
    
    repos = [os.path.join(root_dir, f) for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    if not repos: return

    # Usa 10 thread per fare pull contemporaneamente
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(_pull_single_repo, repos))

def git_clone_related_chart(root_dir, project_name, source_repo_folder):
    """
    Cerca di indovinare l'URL del repo Chart basandosi sul repo corrente e lo clona.
    Es: .../backend-kustomization.git -> .../backend-chart.git
    """
    source_path = os.path.join(root_dir, source_repo_folder)
    
    # 1. Recupera URL remoto del repo corrente
    try:
        res = subprocess.run(
            ["git", "-C", source_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        )
        origin_url = res.stdout.strip()
    except:
        return False, "Impossibile leggere remote origin del repo corrente."

    # 2. Calcola URL del Chart (euristica: sostituisce kustomization con chart)
    # Es: cdc-adapter-kustomization -> cdc-adapter-chart
    if "kustomization" in origin_url:
        chart_url = origin_url.replace("kustomization", "chart")
    elif "-config" in origin_url:
        chart_url = origin_url.replace("-config", "-chart")
    else:
        # Fallback brutale: aggiunge -chart alla fine se non trova pattern
        if origin_url.endswith(".git"):
            chart_url = origin_url.replace(".git", "-chart.git")
        else:
            chart_url = origin_url + "-chart"

    # 3. Nome cartella destinazione
    # Cerchiamo di mantenere lo standard: {project}-chart
    target_folder_name = f"{project_name}-chart"
    target_path = os.path.join(root_dir, target_folder_name)

    if os.path.exists(target_path):
        return True, "Repo Chart già esistente."

    # 4. Clona
    try:
        subprocess.run(["git", "clone", chart_url, target_folder_name], cwd=root_dir, capture_output=True, check=True)
        return True, f"Chart clonata con successo in {target_folder_name}!"
    except subprocess.CalledProcessError as e:
        return False, f"Fallito clone di {chart_url}.\nErrore: {e.stderr.strip()}"

# ... (Le altre funzioni: git_commit_push, get_git_diff, git_update_self, git_clone_from_file, get_repo_sync_status, git_hard_reset rimangono INVARIATE. Copiale dal vecchio file se serve) ...
# Assicurati di incollare qui sotto tutte le altre funzioni che c'erano prima!

def git_commit_push(repo_path, message):
    if not os.path.exists(repo_path): return False, "Repo non trovato"
    try:
        subprocess.run(["git", "-C", repo_path, "add", "."], check=True, capture_output=True)
        status = subprocess.run(["git", "-C", repo_path, "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip(): return True, "⚠️ Nessuna modifica (file identico)."
        subprocess.run(["git", "-C", repo_path, "commit", "-m", message], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_path, "push"], check=True, capture_output=True)
        return True, "✅ Push OK!"
    except subprocess.CalledProcessError as e:
        return False, f"❌ Git Error: {e.stderr.decode() if e.stderr else str(e)}"

def get_git_diff(root_dir, repo_folder_name):
    repo_path = os.path.join(root_dir, repo_folder_name)
    if not os.path.exists(repo_path): return None
    try:
        cmd = ["git", "-C", repo_path, "diff"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip(): return result.stdout
        return None
    except Exception: return None

def git_update_self(repo_path):
    if not os.path.exists(repo_path): return False, "Cartella applicazione non trovata."
    try:
        result = subprocess.run(["git", "-C", repo_path, "pull"], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        if "Already up to date" in output: return True, "L'app è già all'ultima versione."
        else: return True, f"Aggiornamento scaricato:\n{output}"
    except subprocess.CalledProcessError as e: return False, f"Errore Update: {e.stderr.strip()}"

def get_repo_sync_status(repo_path):
    if not os.path.exists(repo_path): return False, False
    is_dirty = False
    is_ahead = False
    try:
        res_status = subprocess.run(["git", "-C", repo_path, "status", "--porcelain"], capture_output=True, text=True)
        if res_status.stdout.strip(): is_dirty = True
        res_ahead = subprocess.run(["git", "-C", repo_path, "rev-list", "--count", "@{u}..HEAD"], capture_output=True, text=True)
        if res_ahead.returncode == 0 and res_ahead.stdout.strip().isdigit():
            if int(res_ahead.stdout.strip()) > 0: is_ahead = True
    except: pass
    return is_dirty, is_ahead

def git_hard_reset(repo_path):
    if not os.path.exists(repo_path): return False, "Repo non trovato"
    try:
        subprocess.run(["git", "-C", repo_path, "fetch"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_path, "reset", "--hard", "@{u}"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_path, "clean", "-fd"], check=True, capture_output=True)
        return True, "🗑️ Progetto ripristinato allo stato remoto!"
    except subprocess.CalledProcessError as e:
        return False, f"Errore Reset: {e.stderr.decode() if e.stderr else str(e)}"

def git_clone_from_file(destination_dir, projects_file_path):
    if not os.path.exists(projects_file_path): return False, f"File non trovato."
    if not os.path.exists(destination_dir): 
        try: os.makedirs(destination_dir)
        except OSError as e: return False, f"Errore dir: {e}"
    with open(projects_file_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    log_msgs = []
    config_path = os.path.join(destination_dir, "repo_config.json")
    repo_config = {"virtual": []}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                existing = json.load(f)
                if "virtual" in existing: repo_config["virtual"] = existing["virtual"]
        except: pass
    my_bar = st.progress(0, text="Analisi progetti...")
    for i, line in enumerate(lines):
        match_config = re.match(r"^CONFIG\s+(.+)\s+WITH\s+(.+)\s+AS\s+(.+)$", line, re.IGNORECASE)
        match_virt = re.match(r"^FROM\s+(.+)\s+IMPORT\s+(.+)\s+WITH\s+(.+)$", line, re.IGNORECASE)
        url = ""
        repo_name = ""
        is_virt = False
        if match_config:
            repo_name = match_config.group(1).strip()
            pass
        elif match_virt:
            source_folder = match_virt.group(1).strip()
            virtual_name = match_virt.group(2).strip()
            yaml_path = match_virt.group(3).strip()
            repo_config["virtual"] = [x for x in repo_config["virtual"] if x['name'] != virtual_name]
            repo_config["virtual"].append({"name": virtual_name, "source": source_folder, "path": yaml_path})
            log_msgs.append(f"👻 Virtual: '{virtual_name}' su '{source_folder}'")
            is_virt = True
        elif " as " in line:
            parts = line.split(" as ")
            url = parts[0].strip()
            repo_name = parts[1].strip()
        else:
            url = line
            repo_name = url.split('/')[-1].replace('.git', '') if '/' in url else url
        if not is_virt and url:
            target_path = os.path.join(destination_dir, repo_name)
            if os.path.exists(target_path):
                log_msgs.append(f"⚠️ {repo_name}: Esistente.")
            else:
                try:
                    subprocess.run(["git", "clone", url, repo_name], cwd=destination_dir, capture_output=True, check=True)
                    log_msgs.append(f"✅ {repo_name}: Clonato.")
                except Exception as e:
                    log_msgs.append(f"❌ {repo_name}: Errore Clone.")
        my_bar.progress((i + 1) / len(lines))
    try:
        with open(config_path, 'w') as f: json.dump(repo_config, f, indent=2)
        log_msgs.append("💾 Configurazione salvata in repo_config.json")
    except Exception as e: log_msgs.append(f"❌ Errore JSON: {e}")
    my_bar.empty()
    return True, "\n".join(log_msgs)