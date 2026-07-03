import os
import subprocess
import tempfile
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'docx', 'doc'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_to_pdf(input_path, output_dir):
    env = {
        **os.environ,
        'HOME': '/root',
        'PYTHONPATH': '',
    }

    result = subprocess.run(
        [
            'libreoffice',
            '--headless',
            '--norestore',
            '--nofirststartwizard',
            '--nologo',
            '--convert-to',
            'pdf:writer_pdf_Export:EmbedStandardFonts=true,UseTaggedPDF=true,ExportBookmarksToPDFDestination=true',
            '--outdir', output_dir,
            input_path,
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f'Conversion echouee: {result.stderr}')

    basename = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, f'{basename}.pdf')

    if not os.path.exists(pdf_path):
        raise RuntimeError('PDF non genere par LibreOffice')

    return pdf_path


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

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, file.filename)
        file.save(input_path)

        try:
            pdf_path = convert_to_pdf(input_path, tmpdir)
        except RuntimeError as e:
            return jsonify({'error': str(e)}), 500

        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=os.path.splitext(file.filename)[0] + '.pdf',
        )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
