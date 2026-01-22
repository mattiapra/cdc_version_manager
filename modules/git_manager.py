# modules/git_manager.py
import os
import subprocess
import streamlit as st

def git_pull_all(root_dir):
    """Esegue git pull su tutti i repo nella root."""
    if not os.path.exists(root_dir): return
    repos = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    if not repos: return
    
    # Usiamo uno spinner vuoto per evitare spam visivo se è veloce
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

# --- NUOVA FUNZIONE PER CLONARE ---
def git_clone_from_file(destination_dir, projects_file_path):
    """Legge progetti.txt e clona i repository mancanti nella destination_dir."""
    
    if not os.path.exists(projects_file_path):
        return False, f"File {projects_file_path} non trovato."
    
    # Crea la cartella di destinazione se non esiste
    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir)
        except OSError as e:
            return False, f"Impossibile creare la cartella: {e}"

    with open(projects_file_path, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        return False, "Nessun URL trovato nel file progetti.txt"

    log_msgs = []
    errors = 0
    
    progress_text = "Clonazione in corso..."
    my_bar = st.progress(0, text=progress_text)

    for i, url in enumerate(urls):
        # Estrai nome cartella dall'URL (es. .../repo.git -> repo)
        repo_name = url.split('/')[-1].replace('.git', '')
        target_path = os.path.join(destination_dir, repo_name)
        
        my_bar.progress((i + 1) / len(urls), text=f"Clonazione: {repo_name}...")

        if os.path.exists(target_path):
            log_msgs.append(f"⚠️ {repo_name}: Già esistente, salto.")
        else:
            try:
                # Esegue git clone
                result = subprocess.run(
                    ["git", "clone", url], 
                    cwd=destination_dir, # Esegui il comando DENTRO la cartella root
                    capture_output=True, 
                    text=True,
                    check=True
                )
                log_msgs.append(f"✅ {repo_name}: Clonato con successo.")
            except subprocess.CalledProcessError as e:
                errors += 1
                log_msgs.append(f"❌ {repo_name}: Errore - {e.stderr.strip()}")

    my_bar.empty()
    
    summary = "\n".join(log_msgs)
    return True, summary