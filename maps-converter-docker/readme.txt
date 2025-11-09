#Info für Docker Container
This service converting nautical charts into various resolution and colors

# In Docker.Desktop im Treminal (Symbol unten rechts)das Verzeichnis mit dem Docker-Files auswählen
# Man muss sich in dem Verzeichnis befinden im dem sich das Dockerfile befindet
cd /Users/wt/Documents/maps-converter-docker

# Docker Image maps-converter erstellen !!!!Achtung!!! Den Punkt am Ende nicht vergessen!!!!
docker build -t maps-converter:1.20.0 .

# Docker Container maps-converter-container stoppen
docker rm -f maps-converter-container

# Docker Container maps-converter-container erstellen mit Hilfe des Docker Image maps-converter
docker run -d --name maps-converter-container -p 8080:8080 -v "$(pwd)/tile_cache:/app/tile_cache" -v "$(pwd)/logs:/app/logs" --restart unless-stopped maps-converter:1.20.0

# Lokales Docker Image in Remote Docker Image für Github umladen und Tag setzen
docker tag maps-converter:1.20.0 openboatprojects/maps_converter:1.20.0

# Docker Image nach DockerHub hochladen
# In Docker.Desktop die Push-Funktion (Push to Docker Hub) benutzen und Image 1.20.0 hochladen
docker push openboatprojects/maps-converter:1.20.0

# Idee für das Frontend: Tabler -> https://docs.tabler.io/
# Frontend-Toolkit mit vielen nützlichen Elementen
