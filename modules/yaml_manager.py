# modules/yaml_manager.py
import os
from ruamel.yaml import YAML

# Inizializzazione globale del parser
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# --- FUNZIONI ESISTENTI (Parsing Kustomize) ---
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

def update_file(root_dir, project, env, type_, value):
    """Aggiornamento puntuale tramite sidebar (legacy)"""
    path = os.path.join(root_dir, f"{project}-kustomization", env)
    target = os.path.join(path, "overlays" if type_ == 'image' else "base", "kustomization.yaml")
    
    if not os.path.exists(target): return False, f"File non trovato: {target}"
    
    try:
        with open(target, 'r') as f: data = yaml.load(f)
        
        if type_ == 'image':
            if 'images' in data: data['images'][0]['newTag'] = value
        elif type_ == 'chart':
            if 'helmCharts' in data: data['helmCharts'][0]['version'] = value
            
        with open(target, 'w') as f: yaml.dump(data, f)
        return True, "Aggiornato!"
    except Exception as e: return False, str(e)

# --- NUOVE FUNZIONI (Editor Raw) ---

def get_file_content(filepath):
    """Legge il contenuto testuale di un file."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read()
    return ""

def save_file_content(filepath, content):
    """Sovrascrive il file con il nuovo contenuto testuale."""
    try:
        # FIX: Assicura che il file termini con una new line (Best Practice POSIX)
        # Questo rimuove il fastidioso '%' alla fine dell'output del terminale
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
    Nome repo atteso: <project>-chart
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