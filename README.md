# Maps Converter

![Converted Map](/pictures/motion_map.gif)

The Maps Converter is a server service from **Open Boat Projects** for converting nautical charts into various resolutions and image formats. This allows for the creation of relatively simple navigation devices based on a microcontroller with various display types. Both color and black-and-white displays are supported.

[Demo Server](https://norbert-walter.dnshome.de//get_image?zoom=13&lat=54.5649&lon=13.1434&mtype=9&mrot=10&itype=1&dtype=2&width=800&height=600&debug=1)

The microcontroller sends a HTTP GET request to the server specifying the geocoordinates, direction of travel, image size, and image type, and the server transmits the finished rendered image to the microcontroller. The server queries various map services and combines the individual tiles and navigation mark layers into an image, rotates the image in the desired direction, and outputs it in the desired size and color. The image is output as a PNG image or as a black-and-white binary image in JSON. The microcontroller then only needs to display the received image on the display and is freed from all image processing functions.

[![Action Video](/pictures/Youtube_Video.png)](https://www.youtube.com/watch?v=S9TVrxNERRY)
  
Video.: [OBP60](https://obp60-v2-docu.readthedocs.io/en/latest/) with ESP32-S3 and nautical chart (Data source Maps Converter)

The server service is free and can be used by anyone. It is hosted by Open Boat Projects. If you like to help or consider this project useful, please donate. Thanks for your support!

[![Donate](/pictures/Donate.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=5QZJZBM252F2L)

The server acts as a map proxy with file and RAM cache to improve performance and can be accessed via various URLs:

# Nautical chart as png picture 

http://ip-address:8080/get_image?zoom=15&lat=51.3343488&lon=7.0025216&mtype=8&mrot=10&itype=4&dtype=3&width=400&height=300&cutout=6&tab=100&border=2&alpha=40&symbol=2&srot=20&ssize=15&grid=1
  
**zoom:** Zoom level 1...17
  
**lat:** Latitude
  
**lon:** Longitude
  
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
* 2 Floyd-Steinberg dithering
* 3 Ordered dithering
* 4 Atkinson dithering
  
**width:** Image width in pixels
  
**height:** Image height in pixels
  
**cutout:** Image cutouts

* 0 No cutout
* 1 Elliptical cutout
* 2 Square cutout left
* 3 Square cutout right
* 4 Square cutout top
* 5 Square cutout bottom
* 6 Square cutout left + right
* 7 Square cutout top + bottom
* 8 Circle cutout (only for 1bit pbm format)

**tab:** Tab width in pixels (only for square cutouts)

**border:** Border width in pixel 0...6

**alpha:** Transparency value for cutouts 0...100%

**symbol:** Symbol for center marking

* 0 No symbol
* 1 Cross
* 2 Triangle

**srot:** Symbol rotation 0...360°

**ssize:** Symbol size in pixels 0...100

**grid:** Show tile grid overlay

* 0 off
* 1 on

# Nautical Chart as JSON

http://ip-address:8080/get_image_json?oformat=3&zoom=15&lat=51.3343488&lon=7.0025216&mtype=8&mrot=10&itype=4&dtype=3&width=400&height=300&cutout=6&tab=100&border=2&alpha=40&symbol=2&srot=20&ssize=15&grid=1

All parameters are identical to the previous section, plus the new parameter **oformat**.

**oformat:** Output format 1...4

* 1 RGB888 (3 bytes per pixel: R, G, B)
* 2 RGB666 (3 bytes per pixel, 6-bit precision per channel, stored in 8-bit bytes)
* 3 RGB565 (2 bytes per pixel, high byte first, then low byte)
* 4 Black-and-white 1-bit packed format (MSB first, white = 0, black = 1)

The image data is returned in Base64 as a binary byte stream. Pixel data is serialized row by row from left to right and top to bottom, with the origin at the upper-left corner.

![JSON result](/pictures/json.png)

Pic.: JSON result

The nautical chart can be decorated as an image and copied into the display framebuffer. The output is compatible with common microcontroller display pipelines (including ESP32-S3 use cases) and with the Adafruit GFX library. Sample code for OBP60 and OBP40 can be found here: https://github.com/norbert-walter/obp60-navigation-map

# Nautical chart as pbm picture

http://ip-address:8080/get_image_pbm?zoom=15&lat=51.3343488&lon=7.0025216&mtype=8&mrot=10&dtype=3&width=400&height=300&cutout=6&tab=100&border=2&symbol=2&srot=20&ssize=15&grid=1

For the smallest data footprint, 1-bit black-and-white PBM format is available.

The `alpha` and `itype` parameters are not required for this format.

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
  
Pic.: Map Service

# Help

http://ip-address:8080/help

This page is an online help page for the Map Service.

# Docker Configuration

The Docker container is listed in the public repository on Docker Hub. It can be found at:

**openboatprojects/maps_converter**

https://hub.docker.com/r/openboatprojects/maps_converter

The container contains a main directory for the application software and two additional external persistent drives are mounted for log files and the cache map directory.

**/app** - Application folder

**/app/logs** - Log folder

**/app/tile_cache** - Cache folder for maps

The dashboard accesses the log file and displays the values in charts. The log file is designed as a rotating file that cannot exceed a specified size. The cache map directory is organized and stored as MBTiles. It can also be used for an MBTiles server. Depending on the use of different geographical regions, the Map Converter's cache map directory grows over time. A distinction is made between the respective map sources, which are stored in separate subfolders.

**/app/tile_cache/1** - Open Street Map Cache

**/app/tile_cache/2** - Google Hybrid Cache

...

etc.

Currently accessed map areas are stored in a RAM cache for subsequent access. The RAM cache size is 512 MB. This allows approximately 10,000 tiles to be stored in the RAM cache and allows approximately 50 devices to be served simultaneously. Older saved map areas are automatically deleted when the cache is full.

# Docker setup

Use the provided `Dockerfile` and `deploy.sh` in this repository.

Build and run manually:

```bash
docker build -t maps-converter-monitored .
docker rm -f maps-server 2>/dev/null || true
docker run -d \
	--name maps-server \
	-p 8080:8080 \
	-v "$(pwd)/tile_cache:/app/tile_cache" \
	-v "$(pwd)/logs:/app/logs" \
	--restart unless-stopped \
	maps-converter-monitored
```

Or use:

```bash
./deploy.sh
```

Server URL:

http://localhost:8080
