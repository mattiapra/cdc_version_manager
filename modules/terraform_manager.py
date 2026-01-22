# modules/terraform_manager.py
import os
import re

def get_tf_version(file_path):
    """
    Legge il file main.tf e cerca la versione nel blocco source.
    Pattern atteso: source = "...?ref=tags/<versione>"
    """
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Regex: cerca 'source = "URL?ref=tags/VERSIONE"'
        # Cattura il gruppo 2 come versione
        pattern = r'(source\s*=\s*".*\?ref=tags\/)([^"]*)(")'
        match = re.search(pattern, content)
        
        if match:
            return match.group(2) # Restituisce solo la versione (es. 1.0.0)
        return "Not Found"
    except Exception:
        return "Err"

def update_tf_version(file_path, new_version):
    """
    Aggiorna la versione nel file main.tf usando regex.
    """
    if not os.path.exists(file_path):
        return False, "File non trovato"

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Regex per la sostituzione
        pattern = r'(source\s*=\s*".*\?ref=tags\/)([^"]*)(")'
        
        # Verifica se il pattern esiste prima di provare a sostituire
        if not re.search(pattern, content):
            return False, "Pattern 'source ... ?ref=tags/...' non trovato nel file."

        # Sostituisce il gruppo 2 (vecchia versione) con new_version
        # \1 è la prima parte (source = "...tags/), \3 è la virgoletta finale
        new_content = re.sub(pattern, fr'\g<1>{new_version}\g<3>', content)
        
        # Aggiunge newline finale se manca (best practice)
        if not new_content.endswith('\n'):
            new_content += '\n'

        with open(file_path, 'w') as f:
            f.write(new_content)
            
        return True, "File Terraform aggiornato!"
    except Exception as e:
        return False, str(e)