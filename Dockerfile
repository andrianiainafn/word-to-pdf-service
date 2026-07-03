FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/root

# Activer les depots contrib et non-free pour les polices Microsoft
RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list \
    && echo "deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/*.sources

# Accepter la EULA Microsoft fonts avant l'installation
RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections

RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    libreoffice-java-common \
    default-jre-headless \
    ttf-mscorefonts-installer \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-freefont-ttf \
    fonts-urw-base35 \
    fonts-noto \
    fonts-noto-core \
    fontconfig \
    libgraphite2-3 \
    libharfbuzz0b \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    cabextract \
    wget \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

# Pre-configurer le profil LibreOffice avec les substitutions de polices
RUN mkdir -p /root/.config/libreoffice/4/user
COPY libreoffice-fonts.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "180", "--workers", "2", "app:app"]
