# Maps Converter

![Converted Map](/pictures/get_image.png)

The Maps Converter is a server service from **Open Boat Projects** for converting nautical charts into various resolutions and image formats. This allows for the creation of relatively simple navigation devices based on a microcontroller with various display types. Both color and black-and-white displays are supported.

[Demo Server](https://norbert-walter.dnshome.de//get_image?zoom=15&lat=52.84279&lon=5.68436&mtype=8&mrot=10&itype=1&dtype=3&width=800&height=600&debug=1)

The mikrocontroller sends a HTTP GET request to the server specifying the geocoordinates, direction of travel, image size, and image type, and the server transmits the finished rendered image to the microcontroller. The server queries various map services and combines the individual tiles and navigation mark layers into an image, rotates the image in the desired direction, and outputs it in the desired size and color. The image is output as a PNG image or as a black-and-white binary image in JSON. The microcontroller then only needs to display the received image on the display and is freed from all image processing functions.

[![Action Video](/pictures/Youtube_Video.png)](https://www.youtube.com/watch?v=S9TVrxNERRY)
  
Video.: [OBP60](https://obp60-v2-docu.readthedocs.io/en/latest/) with ESP32-S3 and nautical chart (Data source Maps Converter)

The server service is free and can be used by anyone. It is hosted by Open Boat Projects. If you like to help or consider this project useful, please donate. Thanks for your support!

[![Donate](/pictures/Donate.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=5QZJZBM252F2L)

The server acts as a map proxy with file and RAM cache to improve performance and can be accessed via various URLs:

# Nautical chart as png picture 

http://ip-address:8080/get_image?zoom=15&lat=51.3343488&lon=7.0025216&mtype=8&mrot=10&itype=4&dtype=3&width=400&height=300&debug=1
  
**zoom:** Zoom level 1...17
  
**lat:** Latitude
  
**lon:** Latitude
  
**mtype:** Map type 1...9
  
* 1 Open Street Map
* 2 Google Hybrid
* 3 Google Street
* 4 Google Terrain Street Hybrid
* 5 Open Topo Map
* 6 Esri Base Map
* 7 Stadimaps Toner SW
* 8 Stadimaps Terrain
* 9 Free Nautical Charts (limited to German coastal waters)
  
**mrot:** Map rotation in degrees 0...360°, +/- 360°
  
**itype:** Image types 1...4
  
* 1 Color
* 2 Grayscale 256-bit
* 3 Grayscale 4-bit
* 4 Black and white image 1-bit, dithered
  
**dtype:** Dithering types 1...4 for black and white images
  
* 1 Threshold dithering
* 2 Flow Steinberg dithering
* 3 Ordered dithering
* 4 Atkinson dithering
  
**width:** Image width in pixels
  
**eight:** Image height in pixels
  
**debug:** Additional information 0/1, tile cut, and georeference

# Nautical Chart as JSON
  
http://ip-address:8080/get_image_json?zoom=15&lat=51.3343488&lon=7.0025216&mtype=8&mrot=10&dtype=3&width=400&height=300&debug=1

The parameters are identical to the previous descriptions. The image is output as JSON in black and white and is Base64 encoded. The image data is binary. The pixels are encoded as bits in the bytes (MSB first). The image information is output line by line from left to right and top to bottom. The zero coordinate is located in the upper left corner of the image.

![JSON result](/pictures/json.png)

Pic.: JSON result

The nautical chart can be decorated as picture and copied into the display's framebuffer and is compatible with the Adafruit GFX library. Sample code can be found here.

# Server Dashboard

http://ip-address:8080/dashboard

Displays a dashboard with information about server utilization:
* Response time
* CPU utilization
* RAM cache utilization
* Number of users

![Converted Map](/pictures/Dashboard.png)
  
Pic.: Dashboard

# Map Service

http://ip-address:8080/map_service

The map service displays a web page that allows for simple navigation. The map center is your current location. Various NMEA 0183 sources can be transmitted and displayed to transmit geocoordinates and some boat information. On mobile phones and laptops with a built-in GPS receiver, this can be used for navigation. The device's own GPS receiver takes priority.

![Converted Map](/pictures/Map_Service.png)
  
Pic.: Dashboard

# Help

http://ip-address:8080/map_help⁠

This page is a online help for the Map Service.

# Docker Configuration

The Docker container is listed in the public repository on Docker Hub. It can be found at:

**openboatprojects/maps_converter**

https://hub.docker.com/r/openboatprojects/maps_converter

The container contains a main directory for the application software and two additional external persistent drives are mounted for log files and the cache map directory.

**/app** - Application folder

**/app/logs** - Log foulder

**/app/tile_cache** - Cache folder for maps

The dashboard accesses the log file and displays the values in charts. The log file is designed as a rotating file that cannot exceed a specified size. The cache map directory is organized and stored as MB Tiles. It can also be used for an MB Tiles server. Depending on the use of different geographical regions, the Map Converter's cache map directory grows over time. A distinction is made between the respective map sources, which are stored in separate subfolders.

**/app/tile_cache/1** - Open Street Map Cache

**/app/tile_cache/2** - Google Hybrid Cache

...

etc.

Currently accessed map areas are stored in a RAM cache for subsequent access. The RAM cache size is 512 MB. This allows approximately 10,000 tiles to be stored in the RAM cache and allows approximately 50 devices to be served simultaneously. Older saved map areas are automatically deleted when the cache is full.

# Basis-Image with Python

FROM python:3.11-slim

# Create folder

WORKDIR /app

# Install sytem requirements (for Pillow and other)

RUN apt-get update && apt-get install -y --no-install-recommends
build-essential
libjpeg-dev
zlib1g-dev
libfreetype6-dev
liblcms2-dev
libwebp-dev
libopenjp2-7
libtiff-dev
libxml2-dev
libxslt1-dev
libharfbuzz-dev
libfribidi-dev
libxcb1
&& rm -rf /var/lib/apt/lists/*

*Copy and install requirements.txt*

*COPY requirements.txt . RUN pip install --no-cache-dir -r requirements.txt*

# Copy project data

*COPY Maps_Converter_V1_13.py . COPY monitor.py .*

# Set port

*EXPOSE 8080 requirements.txt*

# Deployment

*deploy.sh*

```
#!/bin/bash set -e

echo "Create Docker Image..." docker build -t maps-converter-monitored .

echo "Delete old docker container (when necessary)..." docker rm -f maps-server 2>/dev/null || true

echo "Start Docker Container..." docker run -d
--name maps-server
-p 8080:8080
-v "$(pwd)/tile_cache:/app/tile_cache"
-v "$(pwd)/logs:/app/logs"
--restart unless-stopped
maps-converter-monitored

echo "Server runs on: http://localhost:8080⁠"
```