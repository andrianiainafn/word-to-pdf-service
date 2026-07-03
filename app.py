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

FONT_MAP = {
    'Calibri':              'Carlito',
    'Calibri Light':        'Carlito',
    'Calibri Bold':         'Carlito',
    'Cambria':              'Caladea',
    'Cambria Math':         'Caladea',
    'Segoe UI':             'Liberation Sans',
    'Segoe UI Light':       'Liberation Sans',
    'Segoe UI Semibold':    'Liberation Sans',
    'Segoe UI Bold':        'Liberation Sans',
    'Segoe UI Italic':      'Liberation Sans',
    'Gill Sans MT':         'Liberation Sans',
    'Century Gothic':       'URW Gothic',
    'Garamond':             'TeX Gyre Pagella',
    'Palatino Linotype':    'TeX Gyre Pagella',
    'Book Antiqua':         'TeX Gyre Pagella',
    'Franklin Gothic Medium': 'Liberation Sans',
    'Franklin Gothic Book': 'Liberation Sans',
}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def fix_image_orientation(data, filename):
    """Corrige l'orientation EXIF — preserve la qualite JPEG a 95%."""
    try:
        img = Image.open(io.BytesIO(data))
        original_format = img.format
        img = ImageOps.exif_transpose(img)
        buf = io.BytesIO()
        ext = os.path.splitext(filename)[1].lower()
        if ext in ('.jpg', '.jpeg') or original_format == 'JPEG':
            img.save(buf, format='JPEG', quality=95, subsampling=0)
        elif ext == '.png' or original_format == 'PNG':
            img.save(buf, format='PNG', optimize=False)
        else:
            img.save(buf, format=original_format or 'PNG')
        return buf.getvalue()
    except Exception:
        return data


def preprocess_docx(input_path, output_path):
    """
    Corrige les images (EXIF) et remplace les noms de polices dans le XML.
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


def convert_to_pdf(input_path, output_dir, profile_dir):
    """
    Chaque conversion utilise un profil LibreOffice isole pour eviter
    les conflits de lock entre workers Gunicorn concurrents.
    """
    env = {
        **os.environ,
        'HOME': profile_dir,
    }

    result = subprocess.run(
        [
            'libreoffice',
            f'-env:UserInstallation=file://{profile_dir}',
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
        profile_dir = os.path.join(tmpdir, 'lo-profile')
        os.makedirs(profile_dir, exist_ok=True)

        raw_path = os.path.join(tmpdir, 'original_' + file.filename)
        processed_path = os.path.join(tmpdir, file.filename)
        file.save(raw_path)

        try:
            preprocess_docx(raw_path, processed_path)
            pdf_path = convert_to_pdf(processed_path, tmpdir, profile_dir)
        except RuntimeError as e:
            return jsonify({'error': str(e)}), 500

        # Lire le PDF en memoire avant que le tempdir soit supprime
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=os.path.splitext(file.filename)[0] + '.pdf',
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
