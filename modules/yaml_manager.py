# modules/yaml_manager.py
import os
from ruamel.yaml import YAML

# Inizializzazione globale del parser
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

def read_kustomize_values(root_dir, project, env):
    base_path = os.path.join(root_dir, f"{project}-kustomization", env)
    overlay_path = os.path.join(base_path, "overlays", "kustomization.yaml")
    base_file_path = os.path.join(base_path, "base", "kustomization.yaml")
    
    tag_val = "-"
    chart_val = "-"

    if os.path.exists(overlay_path):
        try:
            with open(overlay_path, 'r') as f:
                data = yaml.load(f)
                if data and 'images' in data and len(data['images']) > 0:
                    tag_val = data['images'][0].get('newTag', 'N/A')
        except: pass

    if os.path.exists(base_file_path):
        try:
            with open(base_file_path, 'r') as f:
                data = yaml.load(f)
                if data and 'helmCharts' in data and len(data['helmCharts']) > 0:
                    chart_val = data['helmCharts'][0].get('version', 'N/A')
        except: pass

    return tag_val, chart_val

def get_file_content(filepath):
    """Legge il contenuto testuale di un file."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read()
    return ""

def save_file_content(filepath, content):
    """Sovrascrive il file con il nuovo contenuto testuale."""
    try:
        # FIX: Assicura che il file termini con una new line
        if content and not content.endswith('\n'):
            content += '\n'
            
        with open(filepath, 'w') as f:
            f.write(content)
        return True, "File salvato con successo!"
    except Exception as e:
        return False, f"Errore salvataggio: {str(e)}"

def get_chart_values_content(root_dir, project):
    """
    Cerca il values.yaml nel progetto chart.
    """
    chart_repo = f"{project}-chart"
    
    # Tentativo 1: root/project-chart/values.yaml
    path1 = os.path.join(root_dir, chart_repo, "values.yaml")
    if os.path.exists(path1):
        return get_file_content(path1), path1
        
    # Tentativo 2: root/project-chart/<project>/values.yaml (struttura Helm standard)
    path2 = os.path.join(root_dir, chart_repo, project, "values.yaml")
    if os.path.exists(path2):
        return get_file_content(path2), path2

    return None, f"File values.yaml non trovato in {chart_repo}"

def generate_completions_from_yaml(yaml_content):
    """
    Analizza una stringa YAML e restituisce suggerimenti con contesto (parent path).
    """
    if not yaml_content:
        return []

    completions = []
    
    try:
        data = yaml.load(yaml_content)
    except:
        return []

    def extract_keys(obj, prefix=""):
        # Calcola l'etichetta del genitore (es. "resources.limits" o "root")
        parent_label = prefix.rstrip(".") if prefix else "root"
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                
                # Aggiunge il suggerimento
                completions.append({
                    "caption": key,              # Cosa vedi nel menu a sinistra (es. "cpu")
                    "value": f"{key}: ",         # Cosa scrive quando premi Invio
                    "meta": parent_label,        # 🌟 CONTESTO: Cosa vedi a destra
                    "score": 1000 + len(prefix)  # Priorità
                })
                
                # Ricorsione: passa il nuovo prefisso
                extract_keys(value, prefix=f"{prefix}{key}.")
        
        # Gestione liste di oggetti
        elif isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
             extract_keys(obj[0], prefix)

    extract_keys(data)
    
    # Rimuovi duplicati ESATTI
    unique_map = {}
    for c in completions:
        unique_key = (c['caption'], c['meta'])
        unique_map[unique_key] = c
        
    return list(unique_map.values())