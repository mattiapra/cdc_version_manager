import streamlit as st
import boto3
import re
from config import ECR_ROOT

def get_ecr_versions(project_name):
    """
    Recupera le versioni da ECR mappando il nome del progetto kustomization.
    """
    # 1. Logica di mappatura nome: progetto-kustomization -> tgk-cdc/progetto
    repo_name = project_name.replace("-kustomization", "")
    full_repo_path = f"{ECR_ROOT}{repo_name}"
    
    try:
        # Inizializza sessione AWS
        session = boto3.Session(profile_name='saml', region_name='eu-central-1')
        ecr = session.client('ecr')
        
        # Recupera dettagli immagini
        response = ecr.describe_images(repositoryName=full_repo_path)
        
        # Regex per filtrare (inizia con N.N.N)
        pattern = re.compile(r'^\d+\.\d+\.\d+.*')
        
        versions = []
        for img in response['imageDetails']:
            if 'imageTags' in img:
                for tag in img['imageTags']:
                    if pattern.match(tag):
                        versions.append({
                            "versione": tag,
                            "data_aggiunta": img['imagePushedAt']
                        })
        
        # Ordina per data decrescente
        versions.sort(key=lambda x: x['data_aggiunta'], reverse=True)
        
        # Formatta la data per la visualizzazione
        for v in versions:
            v['data_aggiunta'] = v['data_aggiunta'].strftime('%Y-%m-%d %H:%M:%S')
            
        return {repo_name: versions}, None
    
    except Exception as e:
        return None, str(e)