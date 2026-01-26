# modules/git_manager.py
import os
import subprocess
import streamlit as st

def git_update_self(repo_path):
    """
    Esegue git pull sulla cartella dell'applicazione stessa.
    """
    if not os.path.exists(repo_path):
        return False, "Cartella applicazione non trovata."
        
    try:
        # Esegue il pull
        result = subprocess.run(
            ["git", "-C", repo_path, "pull"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        output = result.stdout.strip()
        if "Already up to date" in output:
            return True, "L'app è già all'ultima versione."
        else:
            return True, f"Aggiornamento scaricato:\n{output}"
            
    except subprocess.CalledProcessError as e:
        return False, f"Errore Update: {e.stderr.strip()}"

def git_pull_all(root_dir):
    if not os.path.exists(root_dir): return
    repos = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    if not repos: return
    try:
        for repo in repos:
            subprocess.run(["git", "-C", os.path.join(root_dir, repo), "pull"], 
                            capture_output=True, timeout=10)
    except: pass 

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

# --- FUNZIONE AGGIORNATA ---
def git_clone_from_file(destination_dir, projects_file_path):
    """
    Legge progetti.txt e clona i repository.
    Supporta sintassi: "URL as NOME_CARTELLA"
    """
    
    if not os.path.exists(projects_file_path):
        return False, f"File {projects_file_path} non trovato."
    
    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir)
        except OSError as e:
            return False, f"Impossibile creare la cartella: {e}"

    with open(projects_file_path, 'r') as f:
        # Leggiamo le righe grezze, filtrando solo commenti e vuote
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not lines:
        return False, "Nessun URL trovato nel file progetti.txt"

    log_msgs = []
    
    progress_text = "Clonazione in corso..."
    my_bar = st.progress(0, text=progress_text)

    for i, line in enumerate(lines):
        # LOGICA PARSING "URL as NOME"
        if " as " in line:
            parts = line.split(" as ")
            url = parts[0].strip()
            repo_name = parts[1].strip() # Usa il nome personalizzato
        else:
            url = line
            # Estrae nome standard (es. .../repo.git -> repo)
            repo_name = url.split('/')[-1].replace('.git', '')

        target_path = os.path.join(destination_dir, repo_name)
        
        my_bar.progress((i + 1) / len(lines), text=f"Clonazione: {repo_name}...")

        if os.path.exists(target_path):
            log_msgs.append(f"⚠️ {repo_name}: Già esistente, salto.")
        else:
            try:
                # Esegue git clone URL NOME_CARTELLA
                # cwd=destination_dir assicura che venga creata dentro la root corretta
                cmd = ["git", "clone", url, repo_name]
                
                subprocess.run(
                    cmd, 
                    cwd=destination_dir, 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                log_msgs.append(f"✅ {repo_name}: Clonato con successo.")
            except subprocess.CalledProcessError as e:
                log_msgs.append(f"❌ {repo_name}: Errore - {e.stderr.strip()}")

    my_bar.empty()
    
    summary = "\n".join(log_msgs)
    return True, summary