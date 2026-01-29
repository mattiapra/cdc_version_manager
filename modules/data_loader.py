import os
import pandas as pd
import json
from modules.yaml_manager import read_kustomize_values, get_yaml_value_by_path
from modules.terraform_manager import get_tf_version
from modules.git_manager import get_repo_sync_status

def load_data(root_dir):
    rows = []
    if not os.path.exists(root_dir): return pd.DataFrame()

    virtual_projects = []
    config_path = os.path.join(".cdc_config", "repo_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                if "virtual" in data: virtual_projects = data["virtual"]
        except: pass

    physical_folders = sorted(os.listdir(root_dir))
    git_status_cache = {}

    def get_cached_status(r_path):
        if r_path not in git_status_cache:
            git_status_cache[r_path] = get_repo_sync_status(r_path)
        return git_status_cache[r_path]

    def icon(char):
        return f'<span class="no-select">{char}</span>'

    for folder in physical_folders:
        folder_path = os.path.join(root_dir, folder)
        if not os.path.isdir(folder_path): continue

        is_dirty, is_ahead = get_cached_status(folder_path)
        git_badge = ""
        if is_dirty: git_badge += f" {icon('✏️')}"
        if is_ahead: git_badge += f" {icon('⬆️')}"

        if folder.endswith("-kustomization"):
            proj = folder.replace("-kustomization", "")
            for env in sorted(os.listdir(folder_path)):
                if os.path.isdir(os.path.join(folder_path, env, "overlays")):
                    tag, chart = read_kustomize_values(root_dir, proj, env)
                    info_text = ""
                    
                    # --- CHECK PIÙ RIGOROSI: Se nullo o trattino, ignora ---
                    if tag and tag not in ["-", "N/A"]: 
                        info_text += f"{icon('🐬 ')}{tag}\n"
                    
                    if chart and chart not in ["-", "N/A"]: 
                        info_text += f"{icon('☸️ ')}{chart}"
                    
                    if git_badge: info_text += f"\n{git_badge}"
                    
                    # Aggiunge riga anche se info_text è vuoto (così esiste, ma è blank)
                    rows.append({
                        "Progetto": proj, "Ambiente": env, "Tipo": "Kustomize",
                        "Info": info_text.strip(), "RepoFolder": folder, "FilePath": None
                    })

        elif "-config-" in folder:
            parts = folder.split("-config-")
            proj = parts[0]
            env_root = os.path.join(folder_path, "environments")
            if os.path.exists(env_root) and os.path.isdir(env_root):
                for env in sorted(os.listdir(env_root)):
                    main_tf_path = os.path.join(env_root, env, "main.tf")
                    if os.path.exists(main_tf_path):
                        tf_ver = get_tf_version(main_tf_path)
                        info_text = ""
                        
                        if tf_ver and tf_ver not in ["-", "N/A"]:
                            info_text = f"{icon('🏗️ TF: ')}{tf_ver}"
                            
                        if git_badge: info_text += f"\n{git_badge}"
                        
                        rows.append({
                            "Progetto": proj, "Ambiente": env, "Tipo": "Terraform",
                            "Info": info_text.strip(), "RepoFolder": folder, "FilePath": main_tf_path
                        })

    for vp in virtual_projects:
        virt_name = vp['name']
        source_folder = vp['source']
        yaml_key_path = vp['path']
        
        proj_display = virt_name.replace("-kustomization", "") if virt_name.endswith("-kustomization") else virt_name
        source_abs_path = os.path.join(root_dir, source_folder)
        
        is_dirty, is_ahead = get_cached_status(source_abs_path)
        git_badge = ""
        if is_dirty: git_badge += f" {icon('✏️')}"
        if is_ahead: git_badge += f" {icon('⬆️')}"

        if os.path.exists(source_abs_path):
            for env in sorted(os.listdir(source_abs_path)):
                base_dir = os.path.join(source_abs_path, env)
                if os.path.isdir(os.path.join(base_dir, "overlays")):
                    target_file = os.path.join(base_dir, "base", "kustomization.yaml")
                    val = get_yaml_value_by_path(target_file, yaml_key_path)
                    
                    info_text = ""
                    if val and val not in ["-", "N/A"]:
                        info_text = f"{icon('📦')} {val}"
                        
                    if git_badge: info_text += f"\n{git_badge}"

                    rows.append({
                        "Progetto": proj_display, "Ambiente": env, "Tipo": "Kustomize",
                        "Info": info_text.strip(), "RepoFolder": source_folder, "FilePath": None
                    })

    return pd.DataFrame(rows)