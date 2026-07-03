FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/root

# Accepter la EULA Microsoft fonts
RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections

RUN apt-get update && apt-get install -y \
    # LibreOffice complet
    libreoffice \
    libreoffice-writer \
    libreoffice-java-common \
    # Java pour meilleure compatibilite LibreOffice
    default-jre-headless \
    # Polices Microsoft via installer (Arial, Times New Roman, Verdana, Georgia, Courier...)
    ttf-mscorefonts-installer \
    # Polices Liberation (substituts open-source Microsoft)
    fonts-liberation \
    fonts-liberation2 \
    # Carlito = Calibri open-source / Caladea = Cambria open-source
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    # Polices generales
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-freefont-ttf \
    fonts-urw-base35 \
    fonts-open-sans \
    # Polices Noto (couverture internationale complete)
    fonts-noto \
    fonts-noto-core \
    fonts-noto-extra \
    fonts-noto-mono \
    # Moteur de rendu graphique
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
    libwebp7 \
    # Outils
    wget \
    cabextract \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

# Pre-configurer le profil LibreOffice
RUN mkdir -p /root/.config/libreoffice/4/user

# Substitution de polices : Calibri -> Carlito, Cambria -> Caladea, etc.
COPY libreoffice-fonts.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "180", "--workers", "2", "app:app"]
