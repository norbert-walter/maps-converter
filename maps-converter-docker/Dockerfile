# Basis-Image with Python
FROM python:3.11-slim

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

# Copy project data
COPY Maps_Converter_V1_13.py .
COPY monitor.py .

# Set port
EXPOSE 8080

# Start python script with Flask web server
CMD ["python", "Maps_Converter_V1_13.py"]
