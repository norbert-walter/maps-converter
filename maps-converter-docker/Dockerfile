# Basis-Image with Python
FROM python:3.11-slim

# OCI Labels
LABEL org.opencontainers.image.authors="Norbert Walter"
LABEL org.opencontainers.image.title="Map Converter"
LABEL org.opencontainers.image.description="Map server with image converter"
LABEL org.opencontainers.image.version="1.20.0"
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
COPY Maps_Converter_V1_20.py .
COPY monitor.py .
COPY map_logic_7.js . /app/static

# Set port
EXPOSE 8080

# Option A: Production with Gunicorn (recommended)
# -w: Number of workers (e.g., 2 or 4 depending on the CPU)
# -b: Bind address
# --threads: Simple parallelism alongside worker processes
# --timeout. Automatic restart of hanging requests
# Note: The Flask app is called "app" in Maps_Converter_V1_20.py
# CMD ["gunicorn", "-w", "4", "--threads", "4", "--timeout", "60", "-b", "0.0.0.0:8080", "Maps_Converter_V1_20:app"]
CMD ["sh", "-c", "gunicorn -w ${WORKERS:-4} --threads ${THREADS:-4} --timeout ${TIMEOUT:-60} -b 0.0.0.0:8080 Maps_Converter_V1_20:app"]


# Option B: Development mode (use instead)
# CMD ["python", "Maps_Converter_V1_20.py"]

# Healthcheck checks if the Python script is still running otherwise restart
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD ["python","-c","import sys,urllib.request; \
r=urllib.request.urlopen('http://127.0.0.1:8080/', timeout=2); \
sys.exit(0 if r.getcode()==200 else 1)"]

