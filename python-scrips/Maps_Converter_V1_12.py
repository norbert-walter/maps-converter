#########################################################################################################################
#
# Maps-Converter
#
# Open Boat Projects, Norbert Walter (C) 2025
#
# The web server waits for a GET request. Depending on the request type, it returns a JSON string or an image.
#
# Start the server with: python Maps_Converter_V1_X.py
#
# Directory structure
#
# /-+ Maps_Converter_V1_X.py
#   | monitor.py
#   |
#   +-logs/metrics.log
#   |    
#   +-tile_cache/mtype/ZZZ/XXX/YYY.pgn
#          
#
# JSON output for ESP32-S3 OBP60, SW binary image as Base64 data (Byte stream)
# http://localhost:8080/get_image_json?zoom=15&lat=53.9028&lon=11.4441&mrot=10&mtype=4&width=400&height=300&debug=1
#
# PNG image output for website 
# http://localhost:8080/get_image?zoom=14&lat=53.9028&lon=11.4441&mrot=0&mtype=4&itype=4&width=400&height=300&debug=1
#
# Output of the website metrics (last 100 readings)
# http://localhost:8080/metrics
#
# Output of a dashboard with charts for the metrics
# http://localhost:8080/dashboard
#
#########################################################################################################################

import io
import platform  # Import the platform module
import diskcache as dc  # Import diskcache for RAM cache
import base64
import os
import math
import numpy as np
import requests
import csv
from PIL import Image, ImageOps, ImageDraw, ImageFont
from io import BytesIO
from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
from flask_compress import Compress
from collections import defaultdict
from collections import deque
from datetime import datetime, timedelta
from threading import Thread
from monitor import init_monitoring


###################################################################################
# MB-Tiles Proxy with File and RAM Cache                                         #
###################################################################################

# Initialize Flask web server
app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_SOMETHING_SECURE"
Compress(app)  # Enable GZIP compression automatically if supported by the client
CORS(app)  # Enable CORS

# Set maximum RAM cache size (e.g., 512 MB)
RAM_CACHE_SIZE = 512 * 1024 * 1024  # 512 MB

# RAM cache for fast access
ram_cache = dc.Cache(size_limit=RAM_CACHE_SIZE)  # RAM cache, no disk persistence

# Function to convert Latitude/Longitude to Web Mercator Tile X, Y, and pixel offset
def latlon_to_xyz(lat, lon, zoom):
    """
    Converts geographic coordinates (Lat, Lon) to X, Y coordinates for the tiling system
    and returns the pixel offset of the exact position in the tile.
    """
    # Calculate the X tile coordinate
    x_tile = (lon + 180.0) / 360.0 * (2 ** zoom)
    
    # Calculate the Y tile coordinate
    lat_rad = math.radians(lat)
    y_tile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * (2 ** zoom)
    
    # Integer part is the tile coordinates
    x = int(x_tile)
    y = int(y_tile)
    
    # Decimal part determines the offset within the tile
    x_offset = int((x_tile - x) * 256)  # Each tile is 256x256 pixels
    y_offset = int((y_tile - y) * 256)
    
    return x, y, x_offset, y_offset
    

# Function to fetch the tile from OSM with a fake User-Agent header (depending on the OS)
def get_user_agent():
    os_name = platform.system()
    if os_name == "Windows":
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0"
    elif os_name == "Linux":
        return "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
    elif os_name == "Darwin":  # MacOS
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:92.0) Gecko/20100101 Firefox/92.0"
    else:
        return "Mozilla/5.0 (compatible; Unknown OS; rv:92.0) Gecko/20100101 Firefox/92.0"

# Function to fetch MB-Tiles tiles
def fetch_osm_tile(x, y, zoom, map_type):
    # Define cache key for RAM cache
    cache_key = f"{map_type}/{zoom}/{x}/{y}.png"
    
    # Check if the tile is already in RAM cache
    cached_tile = ram_cache.get(cache_key)
    if cached_tile:
        print(f"Tile {x}, {y} loaded from RAM cache.")
        # Convert cached binary data back to an image
        return Image.open(BytesIO(cached_tile))
        
    # Define path for disk cache
    cache_dir = os.path.join(os.getcwd(), "tile_cache", str(map_type), str(zoom), str(x))
    print("Cache Dir: ", cache_dir)
    os.makedirs(cache_dir, exist_ok=True)  # Create the directory if it doesn't exist
    tile_path = os.path.join(cache_dir, f"{y}.png")
    
    # Check if the tile exists in the disk cache
    if os.path.exists(tile_path):
        print(f"Tile {x}, {y} loaded from disk cache.")
        with open(tile_path, 'rb') as f:
            tile_data = f.read()
            ram_cache.set(cache_key, tile_data)  # Load into RAM cache
        return Image.open(tile_path)

    # Choose the base map type
    if map_type == 1:
        url1 = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"      # Open Street Map color
    elif map_type == 2:
        url1 = f"https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={zoom}"  # Google Hybrid
    elif map_type == 3:
        url1 = f"https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={zoom}"  # Google Street
    elif map_type == 4:
        url1 = f"https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={zoom}"  # Google Terrain Street Hybrid
    elif map_type == 5:
        url1 = f"https://tile.opentopomap.org/{zoom}/{x}/{y}.png"        # Open Topo Map
    elif map_type == 6:
        url1 = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"  # Esri Base Map
    elif map_type == 7:
        url1 = f"https://tiles.stadiamaps.com/tiles/stamen_toner/{zoom}/{x}/{y}.png?api_key=2ab75b65-06ac-4c54-b041-bf1a65d3a2ab" # Stadimaps toner sw
    elif map_type == 8:
        url1 = f"https://tiles.stadiamaps.com/tiles/stamen_terrain/{zoom}/{x}/{y}.png?api_key=2ab75b65-06ac-4c54-b041-bf1a65d3a2ab" # Stadimaps terrain
    elif map_type == 9:
        url1 = f"https://freenauticalchart.net/qmap-de/{zoom}/{x}/{y}.png" # Free Nautical Chart (Quantenschaum)
    elif map_type == 10:
        url1 = f"https://tiles.c-map.com/wmts/maxnp_noaa/webmercator/{zoom}/{x}/{y}.png" # C-Map        
    else:
        url1 = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"     # Open Street Map color

    # Overlays
    url2 = f"https://t1.openseamap.org/seamark/{zoom}/{x}/{y}.png"  # Open Sea Map Sea Marks (transparent overlay)

    headers = {
        'User-Agent': get_user_agent()  # Use the custom User-Agent function
    }

    # Load background image
    response = requests.get(url1, headers=headers)
    if response.status_code == 200 or response.status_code == 304:
        background = Image.open(BytesIO(response.content))
    else:
        print(f"Status Code {response.status_code}")
        print(f"Tile {x}, {y} could not be loaded. Using fallback.")
        return Image.new('RGB', (256, 256), (200, 200, 200))  # Create fallback image

    # Convert background image to RGBA mode
    background = background.convert("RGBA")

    # Load sea marks overlay
    response = requests.get(url2, headers=headers)
    if response.status_code == 200:
        overlay = Image.open(BytesIO(response.content))
    else:
        print(f"Status Code {response.status_code}")
        print(f"Tile {x}, {y} could not be loaded. Using fallback.")
        overlay = Image.new('RGBA', (256, 256), (0, 0, 0, 0))  # Create transparent overlay
        
    # Apply overlay
    combined_image = background.copy()
    combined_image.paste(overlay, (0, 0), overlay)

    # Save image to RAM cache
    buffer = BytesIO()
    combined_image.save(buffer, format="PNG")
    buffer.seek(0)
    tile_data = buffer.read()
    ram_cache.set(cache_key, tile_data)  # Save in RAM cache
    
    # Save image to disk cache
    combined_image.save(tile_path)
    print(f"Tile {x}, {y} saved in disk cache.")

    return combined_image


###################################################################################
# Additional Image Content and Modification Functions                            #
###################################################################################

# Function to draw a cross at the pixel offset position in the tile
def draw_cross(image, x_offset, y_offset):
    """
    Draws a red cross at the given offset position in the image.
    """
    # Convert the image to RGB mode to bypass the color palette
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    draw = ImageDraw.Draw(image)
    
    # Cross width and height
    line_length = 10  # Length of cross lines
    line_color = (255, 0, 0)  # Red
    
    # Horizontal line of the cross
    draw.line((x_offset - line_length, y_offset, x_offset + line_length, y_offset), fill=line_color, width=2)
    
    # Vertical line of the cross
    draw.line((x_offset, y_offset - line_length, x_offset, y_offset + line_length), fill=line_color, width=2)
    
    return image

# Function to draw tile borders
def draw_tile_borders(image, tile_x, tile_y):
    """
    Draws a black line around each tile with a pixel width.
    """
    draw = ImageDraw.Draw(image)
    # Calculate the position of the tile in the image
    top_left_x = tile_x * 256
    top_left_y = tile_y * 256
    bottom_right_x = top_left_x + 256
    bottom_right_y = top_left_y + 256
    
    # Draw the tile borders
    draw.rectangle([top_left_x, top_left_y, bottom_right_x - 1, bottom_right_y - 1], outline="black", width=1)

# Function to rotate an image
def rotate_image(image, angle, center_x, center_y):
    """
    Rotates the image by a given angle with the point (center_x, center_y) as the center of rotation
    and returns the new image along with the shift of the center.
    """
    # Calculate the new image size after rotation
    rotated_image = image.rotate(angle, center=(center_x, center_y), expand=True)
    
    # Calculate the center shift due to the expanded image size
    new_width, new_height = rotated_image.size
    old_width, old_height = image.size
    
    # Shift the cross after rotation due to the new image size
    shift_x = (new_width - old_width) / 2
    shift_y = (new_height - old_height) / 2
    
    return rotated_image, shift_x, shift_y

# Function to stitch and rotate tiles
def stitch_and_rotate_tiles(lat, lon, zoom, output_size_pixels, rotation_angle, map_type, debug):
    """
    Loads the required tiles, stitches them into one image,
    then rotates it around the red cross and crops it so that the red cross is centered.
    """
    # Convert geo-coordinates to tile coordinates and offset
    x_tile, y_tile, x_offset, y_offset = latlon_to_xyz(lat, lon, zoom)
    
    # Number of tiles required to fill the image
    num_tiles_x = math.ceil(output_size_pixels[0] / 256) + 2  # +1 to ensure enough tiles for the offset
    num_tiles_y = math.ceil(output_size_pixels[1] / 256) + 2  # +1 to ensure enough tiles for the offset
    
    # Create an empty image for the final mosaic
    total_width = num_tiles_x * 256
    total_height = num_tiles_y * 256
    combined_image = Image.new('RGB', (total_width, total_height))
    
    # Download and stitch the tiles
    for i in range(num_tiles_x):
        for j in range(num_tiles_y):
            tile = fetch_osm_tile(x_tile + i - num_tiles_x//2, y_tile + j - num_tiles_y//2, zoom, map_type)
            combined_image.paste(tile, (i * 256, j * 256))
            
            # Draw the black line around each tile
            if debug == 1:
                draw_tile_borders(combined_image, i, j)
    
    # Draw a cross on the central tile at the offset position
    central_tile_x = num_tiles_x // 2
    central_tile_y = num_tiles_y // 2
    cross_x = central_tile_x * 256 + x_offset
    cross_y = central_tile_y * 256 + y_offset
    if debug == 1:
        draw_cross(combined_image, cross_x, cross_y)
    
    # Rotate the image around the red cross
    rotated_image, shift_x, shift_y = rotate_image(combined_image, rotation_angle, cross_x, cross_y)
    
    # Calculate the new position of the red cross after rotation
    new_cross_x = cross_x + shift_x
    new_cross_y = cross_y + shift_y
    
    # Determine the new crop area to place the red cross in the center
    new_left = int(new_cross_x - output_size_pixels[0] // 2)
    new_top = int(new_cross_y - output_size_pixels[1] // 2)
    new_right = new_left + output_size_pixels[0]
    new_bottom = new_top + output_size_pixels[1]
    
    # Crop the image based on the new area
    cropped_image = rotated_image.crop((new_left, new_top, new_right, new_bottom))
    
    return cropped_image

###################################################################################
# Image conversion to different formats                                           #
################################################################################### 
    
   
# Convert the image to grayscale
def convert_to_grayscale(image):
    # Convert the image to a grayscale image (L mode)
    grayscale_image = image.convert('L')
    return grayscale_image    

# Convert the image to 4-level grayscale
def convert_to_4_grayscale(image):
    # Convert the image to a grayscale image (L mode)
    grayscale_image = image.convert('L')
    # Reduce the brightness values to 4 grayscale levels (0 to 255 in steps of 64)
    grayscale_image = grayscale_image.point(lambda p: (p // 64) * 64)
    return grayscale_image
    
# Threshold Dithering
def threshold_dither(image):
    bw = image.point(lambda x: 0 if x < 189 else 255)
    return bw.convert('1')

# Floyd Steinberg Dithering
def floyd_steinberg_dither(image):
    return image.convert('1', dither=Image.FLOYDSTEINBERG)

# Ordered Dithering
def ordered_dither(image):
    return image.convert('1', dither=Image.ORDERED)

# Atkinson Dithering
def atkinson_dither(image):
    img = np.array(image.convert("L"), dtype=np.float32)
    h, w = img.shape

    for y in range(h):
        for x in range(w):
            old = img[y, x]
            new = 0 if old < 128 else 255
            error = (old - new) / 8.0
            img[y, x] = new
            if x + 1 < w:
                img[y, x+1] += error
            if x + 2 < w:
                img[y, x+2] += error
            if y + 1 < h:
                if x - 1 >= 0:
                    img[y+1, x-1] += error
                img[y+1, x] += error
                if x + 1 < w:
                    img[y+1, x+1] += error
            if y + 2 < h:
                img[y+2, x] += error

    return Image.fromarray(np.where(img < 128, 0, 255).astype(np.uint8), mode='L').convert('1') 

# Convert the image to black and white with dithering
def convert_to_black_and_white(image, d_type):
    grayscale_image = image.convert('L')
    if d_type == 1:
        bw_image = threshold_dither(image)          # Threshold Dithering
    elif d_type == 2:
        bw_image = floyd_steinberg_dither(image)    # Floyd Steinberg Dithering
    elif d_type == 3:
        bw_image = ordered_dither(image)            # Ordered Dithering
    elif d_type == 4:
        bw_image = atkinson_dither(image)           # Atkinson Dithering
    else:
        bw_image = floyd_steinberg_dither(image)    # Floyd Steinberg Dithering
    return bw_image

# Function to convert a black-and-white image to a bit string (0 for white, 1 for black)
def image_to_bitstring_old(image):
    pixels = image.getdata()
    bits = []
    for pixel in pixels:
        bits.append('1' if pixel == 0 else '0')  # 0 = Black, 255 = White
    return ''.join(bits)

# Function to convert a black-and-white image to a byte array
def image_to_bytearray(image):
    width, height = image.size
    print(f"Dimension X:{width}, Y:{height}")
    padded_width = ((width + 7) // 8) * 8
    bytes_per_row = padded_width // 8
    byte_array = []
    for y in range(height):
        for byte_index in range(bytes_per_row):
            byte = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                if x < width:
                    pixel = image.getpixel((x, y))
                    bit_value = 0 if pixel == 255 else 1  # white = 0, black = 1
                else:
                    bit_value = 0  # padding: white pixel
#                byte |= (bit_value << bit)  # LSB-first
                byte = (byte << 1) | bit_value  # MSB first
            byte_array.append(byte)
    return byte_array

    
###################################################################################
# Handling with Websites                                                         #
###################################################################################
    
# Check user input against boundary values
def limit_check(min, max, input, typ=int):
    """
    Limit the user's input to a specific range and type.
    
    :param min: The smallest allowed value
    :param max: The largest allowed value
    :param input: The value to be checked
    :param typ: The expected data type (default is int)
    :return: The validated and limited value
    """
    try:
        # Convert the input to the desired type
        value = typ(input)
        
        # Check if the value is within the range
        if min <= value <= max:
            return value  # Return the value if it is valid
        else:
            # If the value is smaller than min, set it to min
            if value < min:
                return min
            # If the value is larger than max, set it to max
            if value > max:
                return max
    except ValueError:
        # Error message for invalid inputs
        raise ValueError(f"Invalid input: '{input}' cannot be converted to {typ.__name__}.")
        
        
# Request timestamps for calculating requests per second
request_timestamps = deque(maxlen=1000)  # limited to save memory

# Session tracking
session_times = {}

def update_sessions():
    now = datetime.utcnow()
    sid = session.get("sid")
    if not sid:
        sid = request.remote_addr + "_" + str(now.timestamp())
        session["sid"] = sid
    session_times[sid] = now

    # Remove old sessions (e.g., older than 10 minutes)
    expire_time = now - timedelta(minutes=10)
    for s in list(session_times):
        if session_times[s] < expire_time:
            del session_times[s]

# Active IPs in the last 60 seconds
active_ips = defaultdict(list)

def update_active_ips(ip):
    now = datetime.utcnow()
    active_ips[ip].append(now)

    # Clean up old entries
    for ip_addr in list(active_ips.keys()):
        active_ips[ip_addr] = [t for t in active_ips[ip_addr] if now - t < timedelta(seconds=60)]
        if not active_ips[ip_addr]:
            del active_ips[ip_addr]        



###################################################################################
# Generate website content                                                       #
###################################################################################
# Version with dynamically gzip-compressed JSON output if supported by client  #
###################################################################################

# Respond to HTTP request for JSON response
###########################################
@app.route('/get_image_json', methods=['GET'])
def get_image_json():
    try:
        # Extract parameters from the request
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        map_rotation = float(request.args.get('mrot', 0))
        map_type = int(request.args.get('mtype', 0))
        dither_type = int(request.args.get('dtype', 2)) # 1: Threshold 2: Floyd Steinberg 3: Ordered 4: Atkinson (slow)
        width = int(request.args.get('width', 400))
        height = int(request.args.get('height', 300))
        zoom_level = int(request.args.get('zoom', 15))  # Standard zoom level 15
        debug = int(request.args.get('debug', 0))
        
        # Validate input values
        lat = limit_check(-90.0, 90.0, lat, float)
        lon = limit_check(-180.0, 180.0, lon, float)
        map_rotation = limit_check(-360.0, 360.0, map_rotation, float)
        map_type = limit_check(1, 10, map_type, int)
        dither_type = limit_check(1, 4, dither_type, int)
        width = limit_check(50, 800, width, int)
        height = limit_check(50, 600, height, int)
        zoom_level = limit_check(0, 18, zoom_level, int)
        debug = limit_check(0, 1, debug, int)      

        output_size_pixels = (width, height)  # Image size in pixels
        # Load tiles, stitch them together, rotate, and crop
        temp_image = stitch_and_rotate_tiles(lat, lon, zoom_level, output_size_pixels, map_rotation, map_type, debug)

        # Create black and white image with dithering
        bw_image = convert_to_black_and_white(temp_image, dither_type)

        # Convert the image to a byte array (1 for black, 0 for white)
        byte_array = image_to_bytearray(bw_image)
        
        # Encode to Base64
        base64_bytes = base64.b64encode(bytearray(byte_array))

        # Convert to string (UTF-8)
        base64_string = base64_bytes.decode('utf-8')
        
        # Number of pixels
        number_pixels = len(byte_array)

        # Create the JSON response
        response = {
            'latitude': lat,
            'longitude': lon,
            'rotation_angle': map_rotation,
            'map_type': map_type,
            'width': width,
            'height': height,
            'number_pixels': number_pixels,
            'picture_base64': base64_string  # Return image as Base64 data
        }

        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500    

        
# Respond to HTTP request for image
###################################
@app.route('/get_image')
def get_image():
    try:
        # Extract parameters from the request
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        map_rotation = float(request.args.get('mrot', 0))
        dither_type = int(request.args.get('dtype', 2)) # 1: Threshold 2: Floyd Steinberg 3: Ordered 4: Atkinson (slow)
        map_type = int(request.args.get('mtype', 0))
        image_type = int(request.args.get('itype', 1))  # 1: Color, 2: Grayscale, 3: 4-Level Grayscale, 4: BW with Dithering
        width = int(request.args.get('width', 400))
        height = int(request.args.get('height', 300))
        zoom_level = int(request.args.get('zoom', 15))  # Standard zoom level 15
        debug = int(request.args.get('debug', 0))
        
        # Validate input values
        lat = limit_check(-90.0, 90.0, lat, float)
        lon = limit_check(-180.0, 180.0, lon, float)
        map_rotation = limit_check(-360.0, 360.0, map_rotation, float)
        map_type = limit_check(1, 10, map_type, int)
        dither_type = limit_check(1, 4, dither_type, int)
        image_type = limit_check(1, 4, image_type, int)
        width = limit_check(50, 800, width, int)
        height = limit_check(50, 600, height, int)
        zoom_level = limit_check(0, 18, zoom_level, int)
        debug = limit_check(0, 1, debug, int)

        output_size_pixels = (width, height)  # Image size in pixels
        # Load tiles, stitch them together, rotate, and crop
        temp_image = stitch_and_rotate_tiles(lat, lon, zoom_level, output_size_pixels, map_rotation, map_type, debug)


        # Select the image output type based on the 'type' parameter
        if image_type == 1:
            final_image = temp_image  # Color image
        elif image_type == 2:
            final_image = convert_to_grayscale(temp_image)  # Grayscale
        elif image_type == 3:
            final_image = convert_to_4_grayscale(temp_image)  # 4-level grayscale
        elif image_type == 4:
            final_image = convert_to_black_and_white(temp_image, dither_type)  # Black and white with dithering
        else:
            return "Invalid image type!", 400
        
        # Convert the image to a byte stream
        img_io = io.BytesIO()
        final_image.save(img_io, 'PNG')
        img_io.seek(0)

        # Return the image as a response
        return send_file(img_io, mimetype='image/png')

    except Exception as e:
        return str(e), 500
        

# SVG for the favicon
FAVICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <text x="0" y="12" font-family="Arial" font-size="16" fill="black">S</text>
</svg>'''

# Respond to HTTP request for favicon
##########################################
@app.route('/favicon.ico')
def favicon():
    # Create an in-memory file from the SVG
    return send_file(io.BytesIO(FAVICON_SVG.encode('utf-8')), mimetype='image/svg+xml')

# Initialize monitoring
init_monitoring(app, ram_cache)

# Output metrics for the charts
####################################
@app.route("/metrics")
def get_metrics():
    data = []
    try:
        with open("logs/metrics.log", "r") as f:
            reader = csv.reader(f)
            for row in list(reader)[-100:]:
                try:
                    timestamp = float(row[0])
                    duration = float(row[1])
                    cpu = float(row[2])
                    mem = float(row[3])
                    cache = float(row[4])
                    rps = float(row[5]) if len(row) > 5 else 0.0
                    sessions = int(row[6]) if len(row) > 6 else 0

                    data.append({
                        "timestamp": timestamp,
                        "duration": duration,
                        "cpu": cpu,
                        "mem": mem,
                        "cache": cache,
                        "rps": rps,
                        "sessions": sessions
                    })
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return jsonify(data)


# Display dashboard as an HTML page
###################################
@app.route("/dashboard")
def dashboard():
    return '''
    <html>
    <head>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
      <h1>OBP Maps Converter</h1>
      <h2>Response time [s]</h2>
      <canvas id="chart1" width="600" height="300"></canvas>
      <h2>CPU Usage [%]</h2>
      <canvas id="chart2" width="600" height="300"></canvas>
      <h2>RAM Cache Size [MB]</h2>
      <canvas id="chart3" width="600" height="300"></canvas>
      <h2>Requests per second (10s average)</h2>
      <canvas id="chart4" width="600" height="300"></canvas>
      <h2>Real Users (Session-based, 10 min.)</h2>
      <canvas id="chart5" width="600" height="300"></canvas>

      <script>
        let chart1, chart2, chart3, chart4, chart5;

        function movingAverage(data, windowSize) {
            const result = [];
            for (let i = 0; i < data.length; i++) {
                const start = Math.max(0, i - windowSize + 1);
                const window = data.slice(start, i + 1);
                const avg = window.reduce((a, b) => a + b, 0) / window.length;
                result.push(avg);
            }
            return result;
        }

        function createChart(ctx, label1, data1, label2, data2, color1, color2) {
            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data1.map((_, i) => i.toString()), // dummy labels
                    datasets: [
                        { label: label1, data: data1, borderColor: color1, fill: false },
                        { label: label2, data: data2, borderColor: color2, borderDash: [5, 5], fill: false }
                    ]
                },
                options: {
                    responsive: false,
                    animation: false
                }
            });
        }

        async function fetchMetrics() {
            const res = await fetch('/metrics');
            const data = await res.json();

            if (!data.length) return;

            const labels = data.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());

            const times = data.map(d => d.duration);
            const avgTimes = movingAverage(times, 60);
            const cpu = data.map(d => d.cpu);
            const avgCpu = movingAverage(cpu, 60);
            const cache = data.map(d => d.cache);
            const avgCache = movingAverage(cache, 60);
            const rps = data.map(d => d.rps || 0);
            const avgRps = movingAverage(rps, 60);
            const sessions = data.map(d => d.sessions || 0);
            const avgSessions = movingAverage(sessions, 60);

            if (!chart1) chart1 = createChart(document.getElementById("chart1"), "Response Time", times, "Average", avgTimes, "blue", "orange");
            else {
                chart1.data.labels = labels;
                chart1.data.datasets[0].data = times;
                chart1.data.datasets[1].data = avgTimes;
                chart1.update();
            }

            if (!chart2) chart2 = createChart(document.getElementById("chart2"), "CPU", cpu, "Average", avgCpu, "red", "orange");
            else {
                chart2.data.labels = labels;
                chart2.data.datasets[0].data = cpu;
                chart2.data.datasets[1].data = avgCpu;
                chart2.update();
            }

            if (!chart3) chart3 = createChart(document.getElementById("chart3"), "Cache MB", cache, "Average", avgCache, "green", "orange");
            else {
                chart3.data.labels = labels;
                chart3.data.datasets[0].data = cache;
                chart3.data.datasets[1].data = avgCache;
                chart3.update();
            }

            if (!chart4) chart4 = createChart(document.getElementById("chart4"), "RPS", rps, "Average", avgRps, "teal", "orange");
            else {
                chart4.data.labels = labels;
                chart4.data.datasets[0].data = rps;
                chart4.data.datasets[1].data = avgRps;
                chart4.update();
            }

            if (!chart5) chart5 = createChart(document.getElementById("chart5"), "Sessions", sessions, "Average", avgSessions, "brown", "orange");
            else {
                chart5.data.labels = labels;
                chart5.data.datasets[0].data = sessions;
                chart5.data.datasets[1].data = avgSessions;
                chart5.update();
            }
        }

        fetchMetrics();
        setInterval(fetchMetrics, 10000);
      </script>
    </body>
    </html>
    '''
    
# Display dashboard as an HTML page
###################################
@app.route("/map_service")
def map_demo():
    return '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>NMEA WebSocket-Client</title>
  <style>
    #status-led {
      width: 15px;
      height: 15px;
      border-radius: 50%;
      background-color: red;
      display: inline-block;
      margin-left: 10px;
    }
    body {
      font-family: sans-serif;
      padding: 20px;
    }
    .field {
      margin: 5px 0;
    }
    .label {
      font-weight: bold;
    }
    #output-container {
      margin-top: 15px;
    }
    #output {
      background: #eee;
      padding: 10px;
      max-height: 200px;
      overflow-y: auto;
      white-space: pre-wrap;
      font-family: monospace;
    }
  </style>
</head>
<body>
  <h1>NMEA WebSocket-Client</h1>

  <h2>NMEA0183 TCP socket connection</h2>
  <label>WebSocket IP-Adresse: <input type="text" id="ip"></label><br>
  <label>WebSocket Port: <input type="number" id="port"></label><br>
  <br>
  <button id="connect-btn">Verbinden</button>
  <div id="status-led"></div>
  
  <h2>Local GPS connection</h2>
  <button id="gps-btn">Verbinden (GPS)</button>
  <div id="gps-led" style="display:inline-block; margin-left: 10px; width:15px; height:15px; background:red; border-radius:50%;"></div>


  <h2>Statusdaten</h2>
  <div class="field"><span class="label">Latitude:</span> <span id="latitude">–</span></div>
  <div class="field"><span class="label">Longitude:</span> <span id="longitude">–</span></div>
  <div class="field"><span class="label">Fix Typ (GGA):</span> <span id="fix-type">–</span></div>
  <div class="field"><span class="label">Satelliten (GSA):</span> <span id="satellites">–</span></div>
  <div class="field"><span class="label">Heading (HDT):</span> <span id="heading">–</span></div>
  <div class="field"><span class="label">Speed (RMC):</span> <span id="speed">–</span></div>
  <div class="field"><span class="label">Wassertiefe (DBT):</span> <span id="depth">–</span></div>
  
  <h2>Karteneinstellungen</h2>
    <label>Kartentyp:
      <select id="map-type">
        <option value="1">Open Street Map</option>
        <option value="2">Google Hybrid</option>
        <option value="3">Google Street</option>
        <option value="4">Google Tarrain</option>
        <option value="5" selected>Open Topo Map</option>
        <option value="6">Esri Base Map</option>
        <option value="7">Stadimaps Toner</option>
        <option value="8">Sradimaps Tarrain</option>
        <option value="9">Free Nautical Chart</option>
        <option value="10">C-Map Light</option>
      </select>
    </label>
    <br>

    <label>Bildtyp:
      <select id="image-type">
        <option value="1" selected>Color</option>
        <option value="2">Gray Scale 265</option>
        <option value="3">Gray Scale 4</option>
        <option value="4">Dither B&W</option>
      </select>
    </label>


  
  <h2>Kartenausschnitt</h2>
  <img id="map-image" src="" style="border: 1px solid #ccc;" />

  <div id="output-container">
    <button id="toggle-output">Rohdaten anzeigen</button>
    <pre id="output"></pre>
  </div>

  <script type="module">
    import * as nmea from 'https://cdn.skypack.dev/nmea-simple';

    const ipInput = document.getElementById('ip');
    const portInput = document.getElementById('port');
    const connectBtn = document.getElementById('connect-btn');
    const output = document.getElementById('output');
    const toggleOutputBtn = document.getElementById('toggle-output');
    const led = document.getElementById('status-led');
    
    const gpsBtn = document.getElementById('gps-btn');
    const gpsLed = document.getElementById('gps-led');
    let gpsWatcher = null;


    const latitudeEl = document.getElementById('latitude');
    const longitudeEl = document.getElementById('longitude');
    const fixTypeEl = document.getElementById('fix-type');
    const satellitesEl = document.getElementById('satellites');
	const headingEl = document.getElementById('heading');
	const speedEl = document.getElementById('speed');
    const depthEl = document.getElementById('depth');


    let ws = null;
    let reconnectInterval = 3000;
    let shouldReconnect = false;
    let reconnectTimer = null;
    let wsUrl = '';
    let expanded = false;

    const logBuffer = [];
	
	const mapImg = document.getElementById('map-image');
	let lastLat = null;
	let lastLon = null;
	let lastHeading = null;
	let lastImageTime = 0;
	
	let useInternalGPS = false;
	const gpsSentenceIds = ["RMC", "GGA", "GLL", "GNS", "VTG", "HDT", "GSA"];
	
	const mapTypeSelect = document.getElementById('map-type');
    const imageTypeSelect = document.getElementById('image-type');

		

    // ===== Cookie-Handling =====
    function setCookie(name, value, days = 365) {
      const expires = new Date(Date.now() + days * 864e5).toUTCString();
      document.cookie = name + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=/';
    }

    function getCookie(name) {
      return document.cookie.split('; ').reduce((r, c) => {
        const [k, v] = c.split('=');
        return k === name ? decodeURIComponent(v) : r;
      }, null);
    }

    function loadSavedConnection() {
      const savedIP = getCookie("nmea_ip");
      const savedPort = getCookie("nmea_port");
      if (savedIP) ipInput.value = savedIP;
      if (savedPort) portInput.value = savedPort;
    }
    
    // ==== LED for GPS connection ====
    function setGpsStatus(active) {
      gpsLed.style.backgroundColor = active ? 'green' : 'red';
    }
    
    // ==== Handle for GPS connection ====
    gpsBtn.addEventListener('click', () => {
      if (!navigator.geolocation) {
        alert("Geolocation wird von diesem Gerät nicht unterstützt.");
        return;
      }

      if (gpsWatcher !== null) {
        navigator.geolocation.clearWatch(gpsWatcher);
        gpsWatcher = null;
        useInternalGPS = false;
        setGpsStatus(false);
        logLine("📴 GPS-Verbindung beendet.");
        return;
      }

      gpsWatcher = navigator.geolocation.watchPosition(
        (position) => {
          useInternalGPS = true;
          setGpsStatus(true);
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          const heading = position.coords.heading ?? lastHeading ?? 0;

          latitudeEl.textContent = lat.toFixed(6);
          longitudeEl.textContent = lon.toFixed(6);
          
          const speedMps = position.coords.speed;
            if (typeof speedMps === "number" && !isNaN(speedMps)) {
              const speedKnots = speedMps * 1.94384;
              speedEl.textContent = speedKnots.toFixed(1) + " kn";
            } else {
              speedEl.textContent = "–";
            }

          updateMap(lat, lon, heading);
          logLine(`📍 GPS: ${lat.toFixed(6)}, ${lon.toFixed(6)}`);
        },
        (error) => {
          logLine("⚠️ GPS-Fehler: " + error.message);
          setGpsStatus(false);
        },
        {
          enableHighAccuracy: true,
          maximumAge: 5000,
          timeout: 10000
        }
      );

      logLine("🛰️ GPS-Verbindung gestartet.");
    });
    
    
	
	// ==== Map handling ====
	function haversine(lat1, lon1, lat2, lon2) {
	  const R = 6371000; // Erdradius in m
	  const toRad = x => x * Math.PI / 180;
	  const dLat = toRad(lat2 - lat1);
	  const dLon = toRad(lon2 - lon1);
	  const a =
		Math.sin(dLat / 2) * Math.sin(dLat / 2) +
		Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
		Math.sin(dLon / 2) * Math.sin(dLon / 2);
	  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	  return R * c;
	}

	function shouldUpdateMap(lat, lon, heading) {
	  if (lastLat === null || lastLon === null || lastHeading === null) return true;

	  const distance = haversine(lastLat, lastLon, lat, lon);
	  const headingChanged = heading !== lastHeading;

	  return distance >= 30 || headingChanged;
	}

	function updateMap(lat, lon, heading) {
      if (!shouldUpdateMap(lat, lon, heading)) return;

      const mtype = mapTypeSelect.value;
      const itype = imageTypeSelect.value;
      const timestamp = Date.now();

      const imageUrl = `http://norbert-walter.dnshome.de:8001/get_image?zoom=15&lat=${lat}&lon=${lon}&mtype=${mtype}&mrot=${heading}&itype=${itype}&dtype=1&width=400&height=800&debug=1&t=${timestamp}`;
      mapImg.src = imageUrl;

      lastLat = lat;
      lastLon = lon;
      lastHeading = heading;
      lastImageTime = timestamp;
    }


    // ===== Anzeige / Parser =====
    function setStatus(connected) {
      led.style.backgroundColor = connected ? 'green' : 'red';
    }

    function displayPacket(packet) {
      try {
        // GPS-Daten ignorieren, wenn internes GPS aktiv ist
        if (useInternalGPS && gpsSentenceIds.includes(packet.sentenceId)) {
          return;
        }

        // RMC – Position + Geschwindigkeit
        if (packet.sentenceId === "RMC" && packet.status === "valid") {
          latitudeEl.textContent = packet.latitude.toFixed(6);
          longitudeEl.textContent = packet.longitude.toFixed(6);
          speedEl.textContent = packet.speedKnots.toFixed(1) + " kn";
          updateMap(packet.latitude, packet.longitude, lastHeading ?? 0);
        }

        // GGA – Position + Fix Type
        if (packet.sentenceId === "GGA" && packet.fixType !== "none") {
          latitudeEl.textContent = packet.latitude.toFixed(6);
          longitudeEl.textContent = packet.longitude.toFixed(6);
          fixTypeEl.textContent = packet.fixType;
          updateMap(packet.latitude, packet.longitude, lastHeading ?? 0);
        }

        // GSA – Satellitenanzahl
        if (packet.sentenceId === "GSA") {
          satellitesEl.textContent = packet.satellites.length;
        }

        // HDT – Heading
        if (packet.sentenceId === "HDT" && typeof packet.heading === "number") {
          headingEl.textContent = packet.heading.toFixed(1) + "°";
          updateMap(lastLat ?? 0, lastLon ?? 0, packet.heading);
        }

        // DBT – Wassertiefe
        if (packet.sentenceId === "DBT" && typeof packet.depthMeters === "number") {
          depthEl.textContent = packet.depthMeters.toFixed(1) + " m";
        }
      } catch (e) {
        console.warn("Fehler beim Anzeigen des Pakets:", e);
      }
    }

	
    function updateOutput() {
      const linesToShow = expanded ? 20 : 3;
      const recent = logBuffer.slice(-linesToShow);
      output.textContent = recent.join('\n');
    }

    function logLine(line) {
      if (logBuffer.length >= 20) {
        logBuffer.shift();
      }
      logBuffer.push(line);
      updateOutput();
    }

    function connect() {
      if (!wsUrl) return;

      logLine(`🔄 Versuche Verbindung zu ${wsUrl}...`);
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setStatus(true);
        logLine(`✅ Verbunden mit ${wsUrl}`);
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
      };

      ws.onmessage = (event) => {
        const lines = event.data.split('\n');
        for (let line of lines) {
          line = line.trim();
          if (!line.startsWith('$')) continue;

          try {
            const packet = nmea.parseNmeaSentence(line);
            displayPacket(packet);
            logLine(line);
          } catch (e) {
//            logLine('⚠️ Ungültig: ' + line);
          }
        }
      };

      ws.onclose = () => {
        setStatus(false);
        logLine('🔌 Verbindung geschlossen.');
        attemptReconnect();
      };

      ws.onerror = () => {
        setStatus(false);
        logLine('❌ WebSocket-Fehler.');
        ws.close();
      };
    }

    function attemptReconnect() {
      if (shouldReconnect && !reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, reconnectInterval);
      }
    }

    connectBtn.addEventListener('click', () => {
      const ip = ipInput.value.trim();
      const port = portInput.value.trim();

      if (!ip || !port) {
        alert('Bitte IP und Port eingeben!');
        return;
      }

      // Cookies setzen
      setCookie("nmea_ip", ip);
      setCookie("nmea_port", port);

      wsUrl = `ws://${ip}:${port}`;
      shouldReconnect = true;

      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close(); // Vorherige Verbindung schließen
      } else {
        connect(); // Neue Verbindung
      }
    });

    toggleOutputBtn.addEventListener('click', () => {
      expanded = !expanded;
      toggleOutputBtn.textContent = expanded ? 'Rohdaten verbergen' : 'Rohdaten anzeigen';
      updateOutput();
    });

    // Beim Start Cookies lesen
    window.addEventListener('load', loadSavedConnection);
  </script>
</body>
</html>
    '''

# Start Flask web server
if __name__ == '__main__':

    # Start the web server on port 8080 for JSON responses and image responses
    serverport = 8080
    def run_json_server():
        app.run(host='0.0.0.0', port=serverport, threaded=True)

    # Start the JSON server in a separate thread
    Thread(target=run_json_server).start()

    print("Server running on port ", serverport, " for JSON responses.")

