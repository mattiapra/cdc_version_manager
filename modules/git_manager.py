# modules/git_manager.py
import os
import subprocess
import streamlit as st

def git_pull_all(root_dir):
    """Esegue git pull su tutti i repo nella root."""
    if not os.path.exists(root_dir): return
    repos = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    if not repos: return
    
    with st.spinner(f"📡 Sincronizzazione Git di {len(repos)} repository..."):
        for repo in repos:
            try:
                subprocess.run(["git", "-C", os.path.join(root_dir, repo), "pull"], 
                             capture_output=True, timeout=5)
            except: pass 

def git_commit_push(repo_path, message):
    """Commit e Push sul repo."""
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

def get_app_commit_info(root_dir, project, tag):
    """Cerca info sul commit applicativo (codice precedente...)"""
    app_repo_name = project.replace("-kustomization", "")
    repo_path = os.path.join(root_dir, app_repo_name)
    if not os.path.exists(repo_path): return None, f"Repo {app_repo_name} non trovato"
    if not tag or tag in ["-", "N/A", "Err"]: return None, "Tag non valido"

    try:
        cmd = ["git", "-C", repo_path, "show", "-s", "--format=%h|%cd|%an|%s", tag]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0: return None, "Tag non trovato"
        parts = result.stdout.strip().split('|', 3)
        if len(parts) == 4:
            return {"Hash": parts[0], "Data": parts[1], "Autore": parts[2], "Messaggio": parts[3]}, None
        return None, "Errore format"
    except Exception as e: return None, str(e)

# --- NUOVA FUNZIONE ---
def get_git_diff(root_dir, project):
    """
    Esegue 'git diff' sul repository di configurazione del progetto.
    Mostra le differenze tra il file su disco (appena salvato) e l'ultimo commit (HEAD).
    """
    repo_name = f"{project}-kustomization"
    repo_path = os.path.join(root_dir, repo_name)
    
    if not os.path.exists(repo_path):
        return None
        
    try:
        # git diff mostra le modifiche non ancora nell'area di staging (quindi quelle salvate su disco)
        # --color=always crea problemi con st.code, meglio testo puro
        cmd = ["git", "-C", repo_path, "diff"]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Se c'è output, ci sono differenze
        if result.stdout.strip():
            return result.stdout
        return None
    except Exception:
        return None