# Open Boat Projects MBTiles-Server
#
# Norbert Walter (C) 2024
#
# Der Webserver wartet auf eine GET-Anfrage. Je nach Anfragetyp wird ein JASON-String oder ein Bild ausgegeben.
#
# Start des Servers mit: python MBTimes_ServerXX.py
#
# JSON-Ausgabe für ESP32-S3 OBP60, SW-Binärbild als Byte-Array
# http://localhost:8080/get_image_json?zoom=15&lat=53.9028&lon=11.4441&mrot=10&mtype=4&width=400&height=300&debug=0
#
# PNG-Bildausgabe für Webseite 
# http://localhost:8080/get_image?zoom=14&lat=53.9028&lon=11.4441&mrot=0&mtype=4&itype=4&width=400&height=300&debug=1
#
import math
import requests
from PIL import Image, ImageOps, ImageDraw
from io import BytesIO
from flask import Flask, request, jsonify, send_file
import io
from threading import Thread
import platform  # Importiere das platform-Modul
import diskcache as dc  # Importiere diskcache für den RAM-Cache

# Flask Webserver initialisieren
app = Flask(__name__)

# Festlegen der maximalen Größe des RAM-Caches (z. B. 512 MB)
RAM_CACHE_SIZE = 512 * 1024 * 1024  # 512 MB

# RAM-Cache für schnelle Zugriffe
ram_cache = dc.Cache(size_limit=RAM_CACHE_SIZE)  # RAM-Cache, keine Festplatten-Persistenz

# SVG für das Favicon
FAVICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <text x="0" y="12" font-family="Arial" font-size="16" fill="black">S</text>
</svg>'''

# Funktion zur Umwandlung von Latitude/Longitude in Web Mercator Tile X, Y und Pixel-Offset
def latlon_to_xyz(lat, lon, zoom):
    """
    Wandelt geografische Koordinaten (Lat, Lon) in X, Y-Koordinaten für das Tiling-System um
    und gibt den Pixel-Offset der genauen Position in der Kachel zurück.
    """
    # Berechnung der X-Tile-Koordinate
    x_tile = (lon + 180.0) / 360.0 * (2 ** zoom)
    
    # Berechnung der Y-Tile-Koordinate
    lat_rad = math.radians(lat)
    y_tile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * (2 ** zoom)
    
    # Ganzzahliger Teil sind die Kachelkoordinaten
    x = int(x_tile)
    y = int(y_tile)
    
    # Nachkommastellen bestimmen den Offset innerhalb der Kachel
    x_offset = int((x_tile - x) * 256)  # Jede Kachel hat 256x256 Pixel
    y_offset = int((y_tile - y) * 256)
    
    return x, y, x_offset, y_offset
    

# Funktion zum Abrufen der Kachel von OSM mit einem gefälschten User-Agent-Header
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

import os
import requests
from PIL import Image, ImageOps
from io import BytesIO

def fetch_osm_tile(x, y, zoom, map_type):
    # Cache-Schlüssel für RAM-Cache definieren
    cache_key = f"{map_type}/{zoom}/{x}/{y}.png"
    
    # Überprüfen, ob die Kachel bereits im RAM-Cache vorhanden ist
    cached_tile = ram_cache.get(cache_key)
    if cached_tile:
        print(f"Kachel {x}, {y} aus dem RAM-Cache geladen.")
        # Konvertiere die gecachten Binärdaten zurück zu einem Bild
        return Image.open(BytesIO(cached_tile))
        
    # Pfad für den Festplatten-Cache definieren
    cache_dir = os.path.join(os.getcwd(), "tile_cache", str(map_type), str(zoom), str(x))
    print("Cache Dir: ", cache_dir)
    os.makedirs(cache_dir, exist_ok=True)  # Erstellen des Verzeichnisses, falls es nicht existiert
    tile_path = os.path.join(cache_dir, f"{y}.png")
    
    # Überprüfen, ob die Kachel auf der Festplatte vorhanden ist
    if os.path.exists(tile_path):
        print(f"Kachel {x}, {y} vom Festplatten-Cache geladen.")
        with open(tile_path, 'rb') as f:
            tile_data = f.read()
            ram_cache.set(cache_key, tile_data)  # In den RAM-Cache laden
        return Image.open(tile_path)

    # Wähle den Basiskartentyp aus
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
    else:
        url1 = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"     # Open Street Map color

    # Overlays
    url2 = f"https://t1.openseamap.org/seamark/{zoom}/{x}/{y}.png"  # Open Sea Map Sea Marks (transparent overlay)

    headers = {
        'User-Agent': get_user_agent()  # Verwende die angepasste User-Agent-Funktion
    }

    # Hintergrundbild laden
    response = requests.get(url1, headers=headers)
    if response.status_code == 200:
        background = Image.open(BytesIO(response.content))
    else:
        print(f"Kachel {x}, {y} konnte nicht geladen werden. Fallback wird genutzt.")
        return Image.new('RGB', (256, 256), (200, 200, 200))  # Fallback-Bild erstellen

    # Hintergrundbild in den RGBA-Modus konvertieren
    background = background.convert("RGBA")

    # Seezeichen als Overlay laden
    response = requests.get(url2, headers=headers)
    if response.status_code == 200:
        overlay = Image.open(BytesIO(response.content))
    else:
        print(f"Kachel {x}, {y} konnte nicht geladen werden. Fallback wird genutzt.")
        overlay = Image.new('RGBA', (256, 256), (0, 0, 0, 0))  # Transparentes Overlay erstellen
        
    # Overlay anwenden
    combined_image = background.copy()
    combined_image.paste(overlay, (0, 0), overlay)

    # Bild in den RAM-Cache speichern
    buffer = BytesIO()
    combined_image.save(buffer, format="PNG")
    buffer.seek(0)
    tile_data = buffer.read()
    ram_cache.set(cache_key, tile_data)  # Speichern im RAM-Cache
    
    # Bild im File-Cache speichern
    combined_image.save(tile_path)
    print(f"Kachel {x}, {y} im File-Cache gespeichert.")

    return combined_image


#######################


# Funktion zum Zeichnen eines Kreuzes an der Pixel-Offset-Position in der Kachel
def draw_cross(image, x_offset, y_offset):
    """
    Zeichnet ein rotes Kreuz an der gegebenen Offset-Position in das Bild.
    """
    # Konvertiere das Bild in den RGB-Modus, um die Farbpalette zu umgehen
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    draw = ImageDraw.Draw(image)
    
    # Kreuzbreite und -höhe
    line_length = 10  # Länge der Linien des Kreuzes
    line_color = (255, 0, 0)  # Rot
    
    # Horizontale Linie des Kreuzes
    draw.line((x_offset - line_length, y_offset, x_offset + line_length, y_offset), fill=line_color, width=2)
    
    # Vertikale Linie des Kreuzes
    draw.line((x_offset, y_offset - line_length, x_offset, y_offset + line_length), fill=line_color, width=2)
    
    return image

# Funktion zum Zeichnen von Kachelumrandungen
def draw_tile_borders(image, tile_x, tile_y):
    """
    Zeichnet eine schwarze Linie um jede Kachel mit einer Pixelbreite.
    """
    draw = ImageDraw.Draw(image)
    # Berechne die Position der Kachel im Bild
    top_left_x = tile_x * 256
    top_left_y = tile_y * 256
    bottom_right_x = top_left_x + 256
    bottom_right_y = top_left_y + 256
    
    # Zeichne die Umrandungen der Kachel
    draw.rectangle([top_left_x, top_left_y, bottom_right_x - 1, bottom_right_y - 1], outline="black", width=1)

def rotate_image(image, angle, center_x, center_y):
    """
    Dreht das Bild um einen gegebenen Winkel mit dem Punkt (center_x, center_y) als Drehzentrum
    und gibt das neue Bild sowie die Verschiebung des Zentrums zurück.
    """
    # Berechne die neue Bildgröße nach der Rotation
    rotated_image = image.rotate(angle, center=(center_x, center_y), expand=True)
    
    # Berechne die Verschiebung des Zentrums aufgrund der erweiterten Bildgröße
    new_width, new_height = rotated_image.size
    old_width, old_height = image.size
    
    # Verschiebung des Kreuzes nach der Rotation aufgrund der neuen Bildgröße
    shift_x = (new_width - old_width) / 2
    shift_y = (new_height - old_height) / 2
    
    return rotated_image, shift_x, shift_y

def stitch_and_rotate_tiles(lat, lon, zoom, output_size_pixels, rotation_angle, map_type, debug):
    """
    Lädt die benötigten Kacheln herunter und fügt sie zu einem Bild zusammen,
    dreht es dann um das rote Kreuz und schneidet es so zu, dass das rote Kreuz in der Mitte liegt.
    """
    # Umwandlung der Geo-Koordinaten in Kachelkoordinaten und Offset
    x_tile, y_tile, x_offset, y_offset = latlon_to_xyz(lat, lon, zoom)
    
    # Anzahl der Kacheln, die benötigt werden, um das Bild zu füllen
    num_tiles_x = math.ceil(output_size_pixels[0] / 256) + 2  # +1, um genug Kacheln für den Offset zu haben
    num_tiles_y = math.ceil(output_size_pixels[1] / 256) + 2  # +1, um genug Kacheln für den Offset zu haben
    
    # Leeres Bild für das finale Mosaik erstellen
    total_width = num_tiles_x * 256
    total_height = num_tiles_y * 256
    combined_image = Image.new('RGB', (total_width, total_height))
    
    # Herunterladen und Zusammenfügen der Kacheln
    for i in range(num_tiles_x):
        for j in range(num_tiles_y):
            tile = fetch_osm_tile(x_tile + i - num_tiles_x//2, y_tile + j - num_tiles_y//2, zoom, map_type)
            combined_image.paste(tile, (i * 256, j * 256))
            
            # Zeichne die schwarze Linie um jede Kachel
            if debug == 1:
                draw_tile_borders(combined_image, i, j)
    
    # Zeichnen eines Kreuzes auf die zentrale Kachel an der Offset-Position
    central_tile_x = num_tiles_x // 2
    central_tile_y = num_tiles_y // 2
    cross_x = central_tile_x * 256 + x_offset
    cross_y = central_tile_y * 256 + y_offset
    if debug == 1:
        draw_cross(combined_image, cross_x, cross_y)
    
    # Drehe das Bild um das rote Kreuz
    rotated_image, shift_x, shift_y = rotate_image(combined_image, rotation_angle, cross_x, cross_y)
    
    # Berechne die neue Position des roten Kreuzes nach der Rotation
    new_cross_x = cross_x + shift_x
    new_cross_y = cross_y + shift_y
    
    # Bestimme den neuen Ausschnitt, der das rote Kreuz in der Mitte platziert
    new_left = int(new_cross_x - output_size_pixels[0] // 2)
    new_top = int(new_cross_y - output_size_pixels[1] // 2)
    new_right = new_left + output_size_pixels[0]
    new_bottom = new_top + output_size_pixels[1]
    
    # Schneide das Bild basierend auf dem neuen Ausschnitt zu
    cropped_image = rotated_image.crop((new_left, new_top, new_right, new_bottom))
    
    return cropped_image

    
 #############################   
    
    

# Konvertiere das Bild in Graustufen-Bild
def convert_to_grayscale(image):
    # Konvertiere das Bild zu einem Graustufenbild (L-Modus)
    grayscale_image = image.convert('L')
    return grayscale_image    

# Konvertiere das Bild in ein 4-Graustufen-Bild
def convert_to_4_grayscale(image):
    # Konvertiere das Bild zu einem Graustufenbild (L-Modus)
    grayscale_image = image.convert('L')
    # Reduziere die Helligkeitswerte auf 4 Graustufen (0 bis 255 in Schritten von 64)
    grayscale_image = grayscale_image.point(lambda p: (p // 64) * 64)
    return grayscale_image

# Konvertiere das Bild in Schwarz-Weiß mit Dithering
def convert_to_black_and_white(image):
    grayscale_image = image.convert('L')
    bw_image = grayscale_image.convert('1', dither=Image.FLOYDSTEINBERG)
    return bw_image

# Funktion zur Konvertierung eines Schwarz-Weiß-Bildes in eine Bit-Kette (0 für Weiß, 1 für Schwarz)
def image_to_bitstring_old(image):
    pixels = image.getdata()
    bits = []
    for pixel in pixels:
        bits.append('1' if pixel == 0 else '0')  # 0 = Schwarz, 255 = Weiß
    return ''.join(bits)

# Funktion zur Konvertierung eines Schwarz-Weiß-Bildes in eine Byte-Array
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
    
def limit_check(min, max, input, typ=int):
    """
    Begrenze die Eingabe des Benutzers auf einen bestimmten Bereich und Typ.
    
    :param min: Der kleinste erlaubte Wert
    :param max: Der größte erlaubte Wert
    :param input: Zu prüfender Eingabewert
    :param typ: Der erwartete Datentyp (standardmäßig int)
    :return: Der validierte und begrenzte Wert
    """
    try:
        # Wandelt die Eingabe in den gewünschten Typ um
        wert = typ(input)
        
        # Überprüfe, ob der Wert innerhalb des Bereichs liegt
        if min <= wert <= max:
            return wert  # Gibt den Wert zurück, wenn er g1: Farbe, 2: Graustufen, 3: 4-Graustufen, 4: SW gedithertültig ist
        else:
            # Wenn der Wert kleiner als min ist, setze ihn auf min
            if wert < min:
                return min
            # Wenn der Wert größer als max ist, setze ihn auf max
            if wert > max:
                return max
    except ValueError:
        # Fehlermeldung bei ungültigen Eingaben
        raise ValueError(f"Ungültige Eingabe: '{input}' kann nicht in {typ.__name__} konvertiert werden.")

# Antwort auf HTTP Anfrage für JSON-Antwort auf Port 8080
@app.route('/get_image_json', methods=['GET'])
def get_image_json():
    try:
        # Extrahiere Parameter aus der Anfrage
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        map_rotation = float(request.args.get('mrot', 0))
        map_type = int(request.args.get('mtype', 0))
        width = int(request.args.get('width', 400))
        height = int(request.args.get('height', 300))
        zoom_level = int(request.args.get('zoom', 15))  # Standard Zoom-Level 15
        debug = int(request.args.get('debug', 0))
        
        # Eingabewerte prüfen
        lat = limit_check(-90.0, 90.0, lat, float)
        lon = limit_check(-180.0, 180.0, lon, float)
        map_rotation = limit_check(-360.0, 360.0, map_rotation, float)
        map_type = limit_check(1, 9, map_type, int)
        width = limit_check(50, 800, width, int)
        height = limit_check(50, 600, height, int)
        zoom_level = limit_check(0, 18, zoom_level, int)
        debug = limit_check(0, 1, debug, int)      

        output_size_pixels = (width, height)  # Bildgröße in Pixel
        # Lade die Kacheln, füge sie zu einem Bild zusammen, drehe es und schneide es zu
        temp_image = stitch_and_rotate_tiles(lat, lon, zoom_level, output_size_pixels, map_rotation, map_type, debug)

        # Schwarz-Weiß-Bild mit Dithering erzeugen
        bw_image = convert_to_black_and_white(temp_image)

        # Bild in Byte-Array umwandeln (1 für Schwarz, 0 für Weiß)
        byte_array = image_to_bytearray(bw_image)

        # Erstelle die JSON-Antwort
        response = {
            'latitude': lat,
            'longitude': lon,
            'rotation_angle': map_rotation,
            'map_type': map_type,
            'width': width,
            'height': height,
            'bytes': byte_array  # Byte-Kette in der Antwort
        }

        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
# Antwort auf HTTP Anfrage für Bild auf Port 8080
@app.route('/get_image')
def get_image():
    try:
        # Extrahiere Parameter aus der Anfrage
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        map_rotation = float(request.args.get('mrot', 0))
        map_type = int(request.args.get('mtype', 0))
        image_type = int(request.args.get('itype', 1))  # 1: Farbe, 2: Graustufen, 3: 4-Graustufen, 4: SW gedithert
        width = int(request.args.get('width', 400))
        height = int(request.args.get('height', 300))
        zoom_level = int(request.args.get('zoom', 15))  # Standard Zoom-Level 15
        debug = int(request.args.get('debug', 0))
        
        # Eingabewerte prüfen
        lat = limit_check(-90.0, 90.0, lat, float)
        lon = limit_check(-180.0, 180.0, lon, float)
        map_rotation = limit_check(-360.0, 360.0, map_rotation, float)
        map_type = limit_check(1, 9, map_type, int)
        image_type = limit_check(1, 4, image_type, int)
        width = limit_check(50, 800, width, int)
        height = limit_check(50, 600, height, int)
        zoom_level = limit_check(0, 18, zoom_level, int)
        debug = limit_check(0, 1, debug, int)

        output_size_pixels = (width, height)  # Bildgröße in Pixel
        # Lade die Kacheln, füge sie zu einem Bild zusammen, drehe es und schneide es zu
        temp_image = stitch_and_rotate_tiles(lat, lon, zoom_level, output_size_pixels, map_rotation, map_type, debug)


        # Wähle den Bildausgabe-Typ basierend auf dem Parameter 'type'
        if image_type == 1:
            final_image = temp_image  # Farbbild
        elif image_type == 2:
            final_image = convert_to_grayscale(temp_image)  # Graustufen
        elif image_type == 3:
            final_image = convert_to_4_grayscale(temp_image)  # 4 Graustufen
        elif image_type == 4:
            final_image = convert_to_black_and_white(temp_image)  # Schwarz-Weiß mit Dithering
        else:
            return "Ungültiger Bildtyp!", 400
        
        # Das Bild in einen Byte-Stream konvertieren
        img_io = io.BytesIO()
        final_image.save(img_io, 'PNG')
        img_io.seek(0)

        # Bild als Antwort zurückgeben
        return send_file(img_io, mimetype='image/png')

    except Exception as e:
        return str(e), 500
        
# Antwort auf HTTP Anfrage für das Favicon
@app.route('/favicon.ico')
def favicon():
    # Erzeuge eine In-Memory-Datei aus dem SVG
    return send_file(io.BytesIO(FAVICON_SVG.encode('utf-8')), mimetype='image/svg+xml')

# Flask-Webserver starten
if __name__ == '__main__':
    from threading import Thread

    # Starte den Webserver auf Port 8080 für die JSON-Antwort und die Bild-Antwort
    serverport = 8080
    def run_json_server():
        app.run(host='0.0.0.0', port=serverport, threaded=True)

    # Starte den JSON-Server in einem separaten Thread
    Thread(target=run_json_server).start()

    print("Server läuft auf Port ", serverport, " für JSON-Antworten.")

