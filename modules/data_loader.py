# modules/data_loader.py
import os
import pandas as pd
from modules.yaml_manager import read_kustomize_values
from modules.terraform_manager import get_tf_version
from modules.ui import format_cell_text

def load_data(root_dir):
    rows = []
    if not os.path.exists(root_dir):
        return pd.DataFrame()

    for folder in sorted(os.listdir(root_dir)):
        folder_path = os.path.join(root_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        # --- LOGICA KUSTOMIZE ---
        if folder.endswith("-kustomization"):
            proj = folder.replace("-kustomization", "")
            for env in sorted(os.listdir(folder_path)):
                # Filtra solo le cartelle che sembrano ambienti validi (hanno overlays)
                if os.path.isdir(os.path.join(folder_path, env, "overlays")):
                    
                    full_tag, full_chart = read_kustomize_values(root_dir, proj, env)
                    disp_tag = full_tag[:15] if full_tag else "-"
                    disp_chart = full_chart[:15] if full_chart else "-"
                    
                    rows.append({
                        "Progetto": proj, 
                        "Ambiente": env, 
                        "Tipo": "Kustomize", 
                        "Info": format_cell_text(disp_tag, disp_chart),
                        "FullTag": full_tag,
                        "FullChart": full_chart,
                        "RepoFolder": folder,
                        "FilePath": None
                    })

        # --- LOGICA TERRAFORM ---
        elif "-config-" in folder:
            # Es: core-config-dev -> Progetto: core
            parts = folder.split("-config-")
            proj = parts[0]
            
            env_root = os.path.join(folder_path, "environments")
            if os.path.exists(env_root) and os.path.isdir(env_root):
                for env in sorted(os.listdir(env_root)):
                    main_tf_path = os.path.join(env_root, env, "main.tf")
                    
                    if os.path.exists(main_tf_path):
                        tf_ver = get_tf_version(main_tf_path)
                        disp_ver = tf_ver[:15] if tf_ver else "-"
                        
                        rows.append({
                            "Progetto": proj,
                            # FIX: Usa solo il nome cartella (es. "testinfra") per raggruppare con Kustomize
                            "Ambiente": env, 
                            "Tipo": "Terraform",
                            "Info": f"🏗️ TF: {disp_ver}",
                            "FullTag": tf_ver,
                            "FullChart": None,
                            "RepoFolder": folder,
                            "FilePath": main_tf_path
                        })
    
    return pd.DataFrame(rows)