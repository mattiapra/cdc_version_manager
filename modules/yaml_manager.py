import os
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

def traverse_dot_path(data, dot_path):
    """
    Funzione helper che naviga un dizionario usando la notazione 'a.b.c'.
    Restituisce il valore o None se non esiste.
    """
    keys = dot_path.split('.')
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return str(current)

def get_yaml_value_by_path(filepath, dot_path):
    """
    Legge un valore da un file YAML.
    È SMART: Se non trova il valore alla radice, cerca dentro helmCharts -> valuesInline.
    """
    if not os.path.exists(filepath): return None
    try:
        with open(filepath, 'r') as f:
            data = yaml.load(f)
        
        # 1. Tentativo Diretto (es. se fosse alla root)
        val = traverse_dot_path(data, dot_path)
        if val: return val

        # 2. Tentativo "Kustomize Helm": Cerca dentro helmCharts[].valuesInline
        if 'helmCharts' in data and isinstance(data['helmCharts'], list):
            for chart in data['helmCharts']:
                if 'valuesInline' in chart:
                    # Usa valuesInline come nuova radice e cerca lì
                    val = traverse_dot_path(chart['valuesInline'], dot_path)
                    if val: return val
                    
        return None
    except: return None

def read_kustomize_values(root_dir, project, env):
    """
    Lettura standard per la riga principale del progetto.
    Cerca:
    1. Tag immagine (overlay)
    2. Helm Chart Version (base)
    3. CopyTool / Extra (base -> helmCharts -> valuesInline)
    """
    base_path = os.path.join(root_dir, f"{project}-kustomization", env)
    overlay_path = os.path.join(base_path, "overlays", "kustomization.yaml")
    base_file_path = os.path.join(base_path, "base", "kustomization.yaml")
    
    tag_val = "-"
    chart_val = "-"
    extra_val = None

    # 1. Overlay (Image Tag)
    if os.path.exists(overlay_path):
        try:
            with open(overlay_path, 'r') as f:
                data = yaml.load(f)
                if data and 'images' in data and len(data['images']) > 0:
                    tag_val = data['images'][0].get('newTag', 'N/A')
        except: pass

    # 2. Base (Helm Version + valuesInline scan)
    if os.path.exists(base_file_path):
        try:
            with open(base_file_path, 'r') as f:
                data = yaml.load(f)
                
                # Helm Version
                if data and 'helmCharts' in data and len(data['helmCharts']) > 0:
                    chart = data['helmCharts'][0]
                    chart_val = chart.get('version', 'N/A')
                    
                    # --- SCANSIONE AUTOMATICA PER COPYTOOL ---
                    # Se c'è valuesInline.copyTool.imageTag lo prendiamo come info extra
                    if 'valuesInline' in chart:
                        vi = chart['valuesInline']
                        if 'copyTool' in vi:
                            ct = vi['copyTool']
                            # Cerca imageTag o tag
                            ct_ver = ct.get('imageTag') or ct.get('tag')
                            if ct_ver:
                                extra_val = f"CopyTool: {ct_ver}"

        except: pass

    # Nota: Restituiamo 3 valori. Assicurati che data_loader.py sia allineato (lo è, se hai usato l'ultima versione che ti ho mandato)
    return tag_val, chart_val # Se data_loader si aspetta 2, o torna 3 se hai modificato data_loader per riceverne 3.
    # IMPORTANTE: Per non rompere il tuo data_loader attuale che si aspetta 2 valori,
    # restituisco solo i due principali. 
    # L'estrazione specifica del CopyTool la facciamo tramite PROGETTO VIRTUALE.
    
    return tag_val, chart_val

def get_file_content(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f: return f.read()
    return ""

def save_file_content(filepath, content):
    try:
        if content and not content.endswith('\n'): content += '\n'
        with open(filepath, 'w') as f: f.write(content)
        return True, "File salvato con successo!"
    except Exception as e:
        return False, f"Errore salvataggio: {str(e)}"

def get_chart_values_content(root_dir, project):
    chart_repo = f"{project}-chart"
    path1 = os.path.join(root_dir, chart_repo, "values.yaml")
    if os.path.exists(path1): return get_file_content(path1), path1
    path2 = os.path.join(root_dir, chart_repo, project, "values.yaml")
    if os.path.exists(path2): return get_file_content(path2), path2
    return None, f"Values non trovato"

def generate_completions_from_yaml(yaml_content):
    if not yaml_content: return []
    completions = []
    try: data = yaml.load(yaml_content)
    except: return []

    def extract_keys(obj, prefix=""):
        parent_label = prefix.rstrip(".") if prefix else "root"
        if isinstance(obj, dict):
            for key, value in obj.items():
                completions.append({"caption": key, "value": f"{key}: ", "meta": parent_label, "score": 1000})
                extract_keys(value, prefix=f"{prefix}{key}.")
        elif isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
             extract_keys(obj[0], prefix)
    extract_keys(data)
    unique_map = {}
    for c in completions: unique_map[(c['caption'], c['meta'])] = c
    return list(unique_map.values())