# modules/data_loader.py
import os
import pandas as pd
from modules.yaml_manager import read_kustomize_values
from modules.ui import format_cell_text

def load_data(root_dir):
    rows = []
    if not os.path.exists(root_dir):
        return pd.DataFrame()

    for folder in sorted(os.listdir(root_dir)):
        if folder.endswith("-kustomization"):
            proj = folder.replace("-kustomization", "")
            path = os.path.join(root_dir, folder)
            
            if os.path.isdir(path):
                for env in sorted(os.listdir(path)):
                    if os.path.isdir(os.path.join(path, env, "overlays")):
                        
                        full_tag, full_chart = read_kustomize_values(root_dir, proj, env)
                        
                        # Tronchiamo SOLO per l'estetica della tabella
                        disp_tag = full_tag[:15] if full_tag else "-"
                        disp_chart = full_chart[:15] if full_chart else "-"
                        
                        content = format_cell_text(disp_tag, disp_chart)
                        
                        rows.append({
                            "Progetto": proj, 
                            "Ambiente": env, 
                            "Info": content,
                            "FullTag": full_tag,     # Dati reali nascosti
                            "FullChart": full_chart  # Dati reali nascosti
                        })
    
    return pd.DataFrame(rows)