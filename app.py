import io
import os
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file

load_dotenv()

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'docx', 'doc'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
CLOUDCONVERT_API_KEY = os.environ['CLOUDCONVERT_API_KEY']
BASE_URL = 'https://api.cloudconvert.com/v2'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_with_cloudconvert(file_data, filename):
    headers = {'Authorization': f'Bearer {CLOUDCONVERT_API_KEY}'}
    ext = filename.rsplit('.', 1)[1].lower()

    # 1. Creer le job
    job_resp = requests.post(f'{BASE_URL}/jobs', headers=headers, json={
        'tasks': {
            'upload-file': {'operation': 'import/upload'},
            'convert-file': {
                'operation': 'convert',
                'input': 'upload-file',
                'input_format': ext,
                'output_format': 'pdf',
                'engine': 'office',
            },
            'export-file': {
                'operation': 'export/url',
                'input': 'convert-file',
            },
        }
    }, timeout=30)
    job_resp.raise_for_status()
    job = job_resp.json()['data']

    # 2. Trouver la tache d'upload
    upload_task = next(t for t in job['tasks'] if t['name'] == 'upload-file')
    form = upload_task['result']['form']

    # 3. Envoyer le fichier
    upload_resp = requests.post(
        form['url'],
        data=form['parameters'],
        files={'file': (filename, file_data, 'application/octet-stream')},
        timeout=60,
    )
    upload_resp.raise_for_status()

    # 4. Attendre la fin du job (poll toutes les 2 secondes, max 120s)
    job_id = job['id']
    for _ in range(60):
        status_resp = requests.get(f'{BASE_URL}/jobs/{job_id}', headers=headers, timeout=15)
        status_resp.raise_for_status()
        job_data = status_resp.json()['data']

        if job_data['status'] == 'finished':
            break
        if job_data['status'] == 'error':
            raise RuntimeError('CloudConvert: conversion echouee')
        time.sleep(2)
    else:
        raise RuntimeError('CloudConvert: timeout apres 120 secondes')

    # 5. Recuperer l'URL du PDF
    export_task = next(t for t in job_data['tasks'] if t['name'] == 'export-file')
    pdf_url = export_task['result']['files'][0]['url']

    # 6. Telecharger le PDF
    pdf_resp = requests.get(pdf_url, timeout=60)
    pdf_resp.raise_for_status()
    return pdf_resp.content


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier envoye'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporte. Utilisez .docx ou .doc'}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({'error': 'Fichier trop volumineux (max 50 MB)'}), 400

    file_data = file.read()

    try:
        pdf_bytes = convert_with_cloudconvert(file_data, file.filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=os.path.splitext(file.filename)[0] + '.pdf',
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
