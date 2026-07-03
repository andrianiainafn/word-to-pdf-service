import io
import os
import subprocess
import tempfile
import zipfile

from flask import Flask, jsonify, request, send_file
from PIL import Image, ImageOps

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'docx', 'doc'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Polices a remplacer directement dans le XML du docx
FONT_MAP = {
    'Calibri':            'Carlito',
    'Cambria':            'Caladea',
    'Cambria Math':       'Caladea',
    'Segoe UI':           'Liberation Sans',
    'Segoe UI Light':     'Liberation Sans',
    'Segoe UI Semibold':  'Liberation Sans',
    'Gill Sans MT':       'Liberation Sans',
    'Century Gothic':     'URW Gothic',
    'Garamond':           'TeX Gyre Pagella',
    'Palatino Linotype':  'TeX Gyre Pagella',
    'Book Antiqua':       'TeX Gyre Pagella',
}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def fix_image_orientation(data, filename):
    """Corrige l'orientation EXIF des images JPEG/PNG."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        buf = io.BytesIO()
        fmt = img.format if img.format else ('JPEG' if filename.lower().endswith(('.jpg', '.jpeg')) else 'PNG')
        img.save(buf, format=fmt)
        return buf.getvalue()
    except Exception:
        return data


def preprocess_docx(input_path, output_path):
    """
    Pre-traitement du docx :
    1. Remplace les noms de polices dans le XML pour correspondre aux polices installees
    2. Corrige l'orientation EXIF des images embarquees
    """
    with zipfile.ZipFile(input_path, 'r') as zin:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                ext = os.path.splitext(item.filename)[1].lower()

                if item.filename.startswith('word/media/') and ext in IMAGE_EXTENSIONS:
                    data = fix_image_orientation(data, item.filename)

                elif item.filename.endswith('.xml') or item.filename.endswith('.rels'):
                    try:
                        text = data.decode('utf-8')
                        for old_font, new_font in FONT_MAP.items():
                            text = text.replace(f'"{old_font}"', f'"{new_font}"')
                        data = text.encode('utf-8')
                    except UnicodeDecodeError:
                        pass

                zout.writestr(item, data)


def convert_to_pdf(input_path, output_dir):
    env = {**os.environ, 'HOME': '/root'}

    result = subprocess.run(
        [
            'libreoffice',
            '--headless',
            '--norestore',
            '--nofirststartwizard',
            '--nologo',
            '--convert-to',
            'pdf:writer_pdf_Export:EmbedStandardFonts=true,UseTaggedPDF=true',
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
        raw_path = os.path.join(tmpdir, 'original_' + file.filename)
        processed_path = os.path.join(tmpdir, file.filename)
        file.save(raw_path)

        try:
            preprocess_docx(raw_path, processed_path)
            pdf_path = convert_to_pdf(processed_path, tmpdir)
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
