import io
import os

import cloudconvert
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file

load_dotenv()

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'docx', 'doc'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

cloudconvert.configure(api_key=os.environ['CLOUDCONVERT_API_KEY'], sandbox=False)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_with_cloudconvert(file_data, filename):
    job = cloudconvert.Job.create(payload={
        'tasks': {
            'upload-file': {
                'operation': 'import/upload',
            },
            'convert-file': {
                'operation': 'convert',
                'input': 'upload-file',
                'input_format': filename.rsplit('.', 1)[1].lower(),
                'output_format': 'pdf',
                'engine': 'office',
            },
            'export-file': {
                'operation': 'export/url',
                'input': 'convert-file',
            },
        }
    })

    upload_task = next(t for t in job['tasks'] if t['name'] == 'upload-file')
    cloudconvert.Task.upload(file_obj=io.BytesIO(file_data), task=upload_task)

    job = cloudconvert.Job.wait(id=job['id'])

    export_task = next(t for t in job['tasks'] if t['name'] == 'export-file')
    if export_task['status'] != 'finished':
        raise RuntimeError('Conversion CloudConvert echouee')

    pdf_url = export_task['result']['files'][0]['url']
    response = requests.get(pdf_url, timeout=60)
    response.raise_for_status()
    return response.content


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
