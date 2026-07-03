FROM python:3.12-slim

# Accepter la EULA Microsoft fonts sans interaction
RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections

RUN apt-get update && apt-get install -y \
    # LibreOffice complet
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    # Polices Microsoft (Arial, Times New Roman, Calibri, Verdana, Georgia...)
    ttf-mscorefonts-installer \
    fonts-liberation \
    fonts-liberation2 \
    # Polices generales
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-freefont-ttf \
    fonts-urw-base35 \
    # Polices Noto (couverture internationale)
    fonts-noto \
    fonts-noto-core \
    fonts-noto-extra \
    # Rendu graphique
    fontconfig \
    libgraphite2-3 \
    libharfbuzz0b \
    libharfbuzz-icu0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    # Gestion images
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    # Utilitaires
    wget \
    cabextract \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

# Configurer LibreOffice pour le mode headless
ENV HOME=/root
RUN mkdir -p /root/.config/libreoffice

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
