# Basis-Image with Python
FROM python:3.11-slim

# OCI Labels
LABEL org.opencontainers.image.authors="Norbert Walter"
LABEL org.opencontainers.image.title="Map Converter"
LABEL org.opencontainers.image.description="Map server with image converter"
LABEL org.opencontainers.image.version="1.19.0"
LABEL org.opencontainers.image.revision="1234567890abcdef" 
LABEL org.opencontainers.image.created="2025-08-07T08:30:00Z"
LABEL org.opencontainers.image.url="https://open-boat-projects.org"
LABEL org.opencontainers.image.source="https://github.com/norbert-walter/map_converter"
LABEL org.opencontainers.image.documentation="https://github.com/norbert-walter/map_converter"
LABEL org.opencontainers.image.vendor="Open Boat Projects"
LABEL org.opencontainers.image.licenses="MIT"

# Create folder
WORKDIR /app

# Install sytem requirements (for Pillow and other)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libopenjp2-7 \
    libtiff-dev \
    libxml2-dev \
    libxslt1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ceate directorys
RUN mkdir /app/logs
RUN mkdir /app/static
RUN mkdir /app/tile_cache

# Copy project data
COPY Maps_Converter_V1_19.py .
COPY monitor.py .
COPY map_logic_6.js . /app/static

# Set port
EXPOSE 8080

# Start python script with Flask web server
CMD ["python", "Maps_Converter_V1_19.py"]
