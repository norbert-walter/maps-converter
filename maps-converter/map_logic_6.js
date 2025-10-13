    import * as nmea from 'https://cdn.skypack.dev/nmea-simple';

    let wakeLock = null; // Lock the screen, no screen saver activation possible
    
    const ipInput = document.getElementById('ip');
    const portInput = document.getElementById('port');
	const startInput = document.getElementById('start');
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
	let heading = null;
	let lastHeading = null;
	let lastImageTime = 0;
	
	let useInternalGPS = false;
	const gpsSentenceIds = ["RMC", "GGA", "GLL", "GNS", "VTG", "HDT", "GSA"];
	
	const mapTypeSelect = document.getElementById('map-type');
    const imageTypeSelect = document.getElementById('image-type');
    const resolutionSelect = document.getElementById('map-resolution');
    const flipResolutionCheckbox = document.getElementById('flip-resolution');
    const flipStatusText = document.getElementById("flip-status-text");
    let width = 480;
    let height = 320;
    let lastMapUpdateTime = 0;  // Last map update time
    
    let zoomLevel = 15; // Start value
    const zoomDisplay = document.getElementById("zoom-display");
    const zoomInBtn = document.getElementById("zoom-in");
    const zoomOutBtn = document.getElementById("zoom-out");
    
    let totalBytes = 0;
    const trafficCounter = document.getElementById("traffic-counter");
    let lastTrafficBytes = 0;
    let lastTrafficTime = Date.now();
    const trafficRateHistory = []; // Max 10 Werte  
		
    // ==== Read base URL ====
    let baseURL;
    if (window.location.protocol === 'file:') {
      // If come back a file path as file://home/... then fallback URL
      baseURL = 'http://127.0.0.1:8080';
    } else {
      // Normal answare as URL https://123.45.67.89:8080
      baseURL = window.location.origin;
    }
    
    // ===== Cookie-Handling =====    
    // Set cookie
    function setCookie(name, value, days = 365) {
      const expires = new Date(Date.now() + days * 864e5).toUTCString();
      document.cookie = name + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=/';
    }

    // Load cookie
    function getCookie(name) {
      return document.cookie.split('; ').reduce((r, c) => {
        const [k, v] = c.split('=');
        return k === name ? decodeURIComponent(v) : r;
      }, null);
    }

    // Load saved IP connection from cookie
    function loadSavedConnection() {
      const savedIP = getCookie("nmea_ip");
      const savedPort = getCookie("nmea_port");
	  const savedStart = getCookie("nmea_start");
      if (savedIP) ipInput.value = savedIP;
      if (savedPort) portInput.value = savedPort;
	  if (savedStart) startInput.value = savedStart;
      
      if (savedIP && savedPort && savedStart) {
        wsUrl = `ws://${savedIP}:${savedPort}`;
        shouldReconnect = true;
        connect();
      }
    }
    
    // ===== Read HTTP GET parameter =====
    // If possible read ip and port for page with websocket connection
    // http://http://192.168.1.67:8080/map_servive?ip=192.168.1.80&port=3000 -> ip = 192.168.1.80 port = 3000
    // http://http://192.168.1.67:8080/map_service -> ip = 127.0.0.1 port = 3000
    function getQueryParam(param) {
      const urlParams = new URLSearchParams(window.location.search);
      return urlParams.get(param);
    }


    // Set defaults, GET parameter has priority
    function setInputDefaults() {
      const defaultIp = "127.0.0.1";
      const defaultPort = "8080";
	  const defaultStart = "0";

      const ipParam = getQueryParam('ip');
      const portParam = getQueryParam('port');
	  const startParam = getQueryParam('start');
      const hasGET = ipParam && portParam && startParam;

      const ipCookie = getCookie('ip');
      const portCookie = getCookie('port');
	  const startCookie = getCookie('start');

      const ip = ipParam || ipCookie || defaultIp;
      const port = portParam || portCookie || defaultPort;
	  const start = startParam || startCookie || defaultStart;

      if (ip) ipInput.value = ip;
	  if (port) portInput.value = port;
	  if (start === "1") {
		startInput.checked = true;
		// 100 ms Verzögerung, um sicherzustellen, dass alles gesetzt ist
		setTimeout(() => {
		  connectBtn.click();
		}, 100);
	  }
	  else {
		  startInput.checked = false;
      }

      if (ipParam) setCookie('ip', ipParam, 365);
      if (portParam) setCookie('port', portParam, 365);
	  if (startParam) setCookie('start', portParam, 365);

      // Has valid GET parameter then don't use cookie values for ip and port
      if (hasGET) {
        setCookie('nmea_ip', ipParam, 365);
        setCookie('nmea_port', portParam, 365);
		setCookie('nmea_start', startParam, 365);
      }
    }


    // ==== LED for GPS connection ====
    function setGpsStatus(active) {
      gpsLed.style.backgroundColor = active ? 'green' : 'red';
    }
    
    // ==== Handle for GPS connection ====
    gpsBtn.addEventListener('click', () => {
      if (!navigator.geolocation) {
        alert("Geolocation is not supported by this device.");
        return;
      }

      if (gpsWatcher !== null) {
        navigator.geolocation.clearWatch(gpsWatcher);
        gpsWatcher = null;
        useInternalGPS = false;
        setGpsStatus(false);
        logLine("📴 GPS connection stopped.");
        return;
      }

      gpsWatcher = navigator.geolocation.watchPosition(
        (position) => {
          useInternalGPS = true;
          setGpsStatus(true);
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          heading = position.coords.heading ?? lastHeading ?? 0;

          latitudeEl.textContent = lat.toFixed(6);
          longitudeEl.textContent = lon.toFixed(6);
          
          const speedMps = position.coords.speed;
            if (typeof speedMps === "number" && !isNaN(speedMps)) {
              const speedKnots = speedMps * 1.94384;
              speedEl.textContent = speedKnots.toFixed(1) + " kn";
            } else {
              speedEl.textContent = "–";
            }

          updateMap(lat, lon, heading, zoomLevel);
          logLine(`📍 GPS: ${lat.toFixed(6)}, ${lon.toFixed(6)}`);
        },
        (error) => {
          logLine("⚠️ GPS error: " + error.message);
          setGpsStatus(false);
        },
        {
          enableHighAccuracy: true,
          maximumAge: 5000,
          timeout: 10000
        }
      );

      logLine("🛰️ GPS connection started.");
    });
        
	
	// ==== Map handling ====
	// ======================
	
	// Calculate distance between two geolocation points
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

	// If the distance between the last and actual geolocation point grater than 30m or heading is changes then update the map
	function shouldUpdateMap(lat, lon, heading) {
      if (lastLat === null || lastLon === null || lastHeading === null) return true;

      const distance = haversine(lastLat, lastLon, lat, lon);
      const headingDiff = Math.abs(heading - lastHeading);

      return distance >= 30 || headingDiff >= 5;
    }

	// Update the map depends on distance between the actual and old geolocation points
	function updateMap(lat, lon, heading, zoom) {
      if (!shouldUpdateMap(lat, lon, heading)) return;
      
      lat = Math.round(lat * 1e6) / 1e6;    // Limiter for 6 decimal places
      lon = Math.round(lon * 1e6) / 1e6;    // Limiter for 6 decimal places

      const mtype = mapTypeSelect.value;
      const itype = imageTypeSelect.value;
      const timestamp = Date.now();

      let width, height;
      
      // If resolution select on auto (Use Display Size) then flip the map orientation
      if (resolutionSelect.value === "auto") {
        width = Math.floor(screen.width * window.devicePixelRatio * 0.7);
        height = Math.floor(screen.height * window.devicePixelRatio * 0.7);

        // Check device Orientation
        const isPortrait = window.innerHeight > window.innerWidth;
        flipResolutionCheckbox.checked = isPortrait;

        // Deaktivate checkbox for flip resolution and show auto
        flipResolutionCheckbox.disabled = true;
        flipStatusText.textContent = "auto";
      } else {
        [width, height] = resolutionSelect.value.split("x").map(Number);
        
        // If lip activ then flip the values
        if (flipResolutionCheckbox.checked) {
          [width, height] = [height, width];
        }

        // Activate checkbox for flip resolution
        flipResolutionCheckbox.disabled = false;
        flipStatusText.textContent = "";
      }
      
      const imageUrl = baseURL + `/get_image?zoom=${zoom}&lat=${lat}&lon=${lon}&mtype=${mtype}&mrot=${heading}&itype=${itype}&dtype=1&width=${width}&height=${height}&debug=1&t=${timestamp}`;

      // At first load HTTP header and read the exact content length
      fetch(imageUrl)
        .then(response => {
          const contentLength = response.headers.get("Content-Length");

          if (contentLength) {
            totalBytes += parseInt(contentLength);
            updateTrafficDisplay();
          }

          return response.blob(); // Read the picture data
        })
        .then(blob => {
          const imgURL = URL.createObjectURL(blob);
          mapImg.src = imgURL;

          // Save the actual values
          lastLat = lat;
          lastLon = lon;
          lastHeading = heading;
          lastImageTime = timestamp;
          lastMapUpdateTime = Date.now(); // Last map update time
        })
        .catch(error => {
          console.error("Could not load picture via HTTP request:", error);
        });
    }
    
    // Update the map direct
	function updateMapDirect(lat, lon, heading, zoom) {
	
	  lat = Math.round(lat * 1e6) / 1e6;    // Limiter for 6 decimal places
      lon = Math.round(lon * 1e6) / 1e6;    // Limiter for 6 decimal places
	
      const mtype = mapTypeSelect.value;
      const itype = imageTypeSelect.value;
      const timestamp2 = Date.now();
      
      let width, height;

      // If resolution select on auto (Use Display Size) then flip the map orientation
      if (resolutionSelect.value === "auto") {
        width = Math.floor(screen.width * window.devicePixelRatio * 0.7);
        height = Math.floor(screen.height * window.devicePixelRatio * 0.7);

        // Check device Orientation
        const isPortrait = window.innerHeight > window.innerWidth;
        flipResolutionCheckbox.checked = isPortrait;

        // Deaktivate checkbox for flip resolution and show auto
        flipResolutionCheckbox.disabled = true;
        flipStatusText.textContent = "auto";
      } else {
        [width, height] = resolutionSelect.value.split("x").map(Number);
        
        // If lip activ then flip the values
        if (flipResolutionCheckbox.checked) {
          [width, height] = [height, width];
        }

        // Activate checkbox for flip resolution
        flipResolutionCheckbox.disabled = false;
        flipStatusText.textContent = "";
      }
      
      const imageUrl = baseURL + `/get_image?zoom=${zoom}&lat=${lat}&lon=${lon}&mtype=${mtype}&mrot=${heading}&itype=${itype}&dtype=1&width=${width}&height=${height}&debug=1&t=${timestamp2}`;

      // At first load HTTP header and read the exact content length
      fetch(imageUrl)
        .then(response => {
          const contentLength = response.headers.get("Content-Length");

          if (contentLength) {
            totalBytes += parseInt(contentLength);
            updateTrafficDisplay();
          }

          return response.blob(); // Read the picture data
        })
        .then(blob => {
          const imgURL = URL.createObjectURL(blob);
          mapImg.src = imgURL;

          // Save the actual values
          lastLat = lat;
          lastLon = lon;
          lastHeading = heading;
          lastMapUpdateTime = Date.now(); // Last map update time
        })
        .catch(error => {
          console.error("Could not load picture via HTTP request:", error);
        });       
    }


    // ===== Display / Parse =====
    // ===========================
    
    // Calculate and show data transmission traffic 
    function updateTrafficDisplay() {
      const now = Date.now();
      const deltaBytes = totalBytes - lastTrafficBytes;
      const deltaTimeMs = now - lastTrafficTime;

      // If the time distance more than 1s then calculate the traffic rate
      if (deltaTimeMs > 1000 && deltaBytes > 0) {
        const deltaTimeHrs = deltaTimeMs / (1000 * 60 * 60);
        const rateMBperHour = (deltaBytes / (1024 * 1024)) / deltaTimeHrs;

        // Add traffic rate values in hitory buffer
        trafficRateHistory.push(rateMBperHour);
        if (trafficRateHistory.length > 10) {
          trafficRateHistory.shift(); // Delete oldest value
        }

        lastTrafficBytes = totalBytes;
        lastTrafficTime = now;
      }

      const currentMB = totalBytes / (1024 * 1024);

      // Calculate average traffic rate over history values
      let avgRate = 0;
      if (trafficRateHistory.length > 0) {
        const sum = trafficRateHistory.reduce((a, b) => a + b, 0);
        avgRate = sum / trafficRateHistory.length;
      }

      // Show traffic data
      trafficCounter.textContent = `${currentMB.toFixed(2)} MB (⌀ ${avgRate.toFixed(0)} MB/h)`;
    }

    
    // Connection status LED
    function setStatus(connected) {
      led.style.backgroundColor = connected ? 'green' : 'red';
    }

    // Display NMEA0183 values
    function displayPacket(packet) {
      try {
        // If internal GPS activ then ignore GPS data
        if (useInternalGPS && gpsSentenceIds.includes(packet.sentenceId)) {
          return;
        }

        // RMC – Position + Speed
        if (packet.sentenceId === "RMC" && packet.status === "valid") {
          latitudeEl.textContent = packet.latitude.toFixed(6);
          longitudeEl.textContent = packet.longitude.toFixed(6);
          speedEl.textContent = packet.speedKnots.toFixed(1) + " kn";
          updateMap(packet.latitude, packet.longitude, lastHeading ?? 0, zoomLevel);
        }

        // GGA – Position + Fix Type
        if (packet.sentenceId === "GGA" && packet.fixType !== "none") {
          latitudeEl.textContent = packet.latitude.toFixed(6);
          longitudeEl.textContent = packet.longitude.toFixed(6);
          fixTypeEl.textContent = packet.fixType;
        }

        // GSA – Number of satellites
        if (packet.sentenceId === "GSA") {
          satellitesEl.textContent = packet.satellites.length;
        }

        // HDT – Heading
        if (packet.sentenceId === "HDT" && typeof packet.heading === "number") {
          headingEl.textContent = packet.heading.toFixed(1) + "°";
          updateMap(lastLat ?? 0, lastLon ?? 0, packet.heading, zoomLevel);
        }

        // DBT – Depth
        if (packet.sentenceId === "DBT" && typeof packet.depthMeters === "number") {
          depthEl.textContent = packet.depthMeters.toFixed(1) + " m";
        }

      } catch (e) {
        console.warn("Error displaying packet:", e);
      }
    }    

	// Expand and collapse for raw data
    function updateOutput() {
      const linesToShow = expanded ? 20 : 3;
      const recent = logBuffer.slice(-linesToShow);
      output.textContent = recent.join('\n');
    }

    // Output for raw NMEA0183 data
    function logLine(line) {
      if (logBuffer.length >= 20) {
        logBuffer.shift();
      }
      logBuffer.push(line);
      updateOutput();
    }

    // Websocket connection and data parsing 
    function connect() {
      if (!wsUrl) return;

      logLine(`🔄 Attempting to connect to ${wsUrl}...`);
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setStatus(true);
        logLine(`✅ Connected to ${wsUrl}`);
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

      // Reconnect by lost of connection
      ws.onclose = () => {
        setStatus(false);
        logLine('🔌 Connection closed.');
        
        console.log("🔌 WebSocket closed");
        console.log("shouldReconnect =", shouldReconnect);
        console.log("reconnectInterval =", reconnectInterval);
        console.log("reconnectTimer =", reconnectTimer);

        attemptReconnect();

        console.log("🚀 attemptReconnect() aufgerufen");
      };

      // If a error then close connection
      ws.onerror = () => {
        setStatus(false);
        logLine('❌ WebSocket error.');
        ws.close();
      };
    }

    // Reconnect function with timeout limit
    function attemptReconnect() {
      if (shouldReconnect && !reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, reconnectInterval);
      }
    }

    // Wake lock for screen, screen saver aktivation not possible
    // The webpage displays allways on mobile devices
    // The function is only supported for Chrome and Edge web browser
    async function requestWakeLock() {
      try {
        wakeLock = await navigator.wakeLock.request('screen');
        console.log('Wake Lock aktivated');

        // If tab changed tehn activate again the wake lock
        wakeLock.addEventListener('release', () => {
          console.log('Wake Lock new activated');
        });
      } catch (err) {
        console.error(`${err.name}, ${err.message}`);
      }
    }

    
    // Handle for flipping auto resolution depends on device orientation (portrait or landscape)
    // It is usable only for mobile devices with interated orientation sensor
    function handleAutoResolutionFlip() {
      const isAuto = resolutionSelect.value === "auto";
      if (isAuto) {
        const isPortrait = window.innerHeight > window.innerWidth;
        flipResolutionCheckbox.checked = isPortrait;
        flipResolutionCheckbox.disabled = true; // Set checbox flip resolution
        flipStatusText.textContent = "auto";    // Message info after check box
      } else {
        flipResolutionCheckbox.disabled = false;
        flipStatusText.textContent = "";    // Message info after check box
      }
    }
  
    
    // ==== Evnent listener ====
    // ========================= 
    
    // If map size changed then update the map
    resolutionSelect.addEventListener('change', () => {
      handleAutoResolutionFlip();
      if (lastLat !== null && lastLon !== null && lastHeading !== null) {
        updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);
      }
    });
    
    // If change device orientation than flip the resolution (orientation)
    window.addEventListener('resize', () => {
      handleAutoResolutionFlip();
      if (resolutionSelect.value === "auto" && lastLat !== null && lastLon !== null && lastHeading !== null) {
        updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);
      }
    });

    // Button event for websocket connection
    connectBtn.addEventListener('click', () => {
      const ip = ipInput.value.trim();
      const port = portInput.value.trim();
	  const start = startInput.value.trim();

      if (!ip || !port || !start) {
        alert('Please enter IP, port and start option!');
        return;
      }

      // Set cookies with settings
      setCookie("nmea_ip", ip);
      setCookie("nmea_port", port);
	  setCookie("nmea_start", start);

      wsUrl = `ws://${ip}:${port}`;
      shouldReconnect = true;
     
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close(); // Close last connection
      } else {
        connect(); // New connection
      }
    });
    
    // Button for data output
    toggleOutputBtn.addEventListener('click', () => {
      expanded = !expanded;
      toggleOutputBtn.textContent = expanded ? 'Collapse raw data' : 'Show raw data';
      updateOutput();
    });
    
    // Button for zoom level plus
    zoomInBtn.addEventListener("click", () => {
    if (zoomLevel < 17) {
        zoomLevel++;
        zoomDisplay.textContent = `Zoom: ${zoomLevel}`;
        if (lastLat !== null && lastLon !== null && lastHeading !== null) {
          updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);    // Update map
        }
      }
    });

    // Button for zommlevel minus
    zoomOutBtn.addEventListener("click", () => {
      if (zoomLevel > 12) {
        zoomLevel--;
        zoomDisplay.textContent = `Zoom: ${zoomLevel}`;
        if (lastLat !== null && lastLon !== null && lastHeading !== null) {
          updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);    // Update map
        }
      }
    });
    
    // If flip map resolution actic then update the map
    flipResolutionCheckbox.addEventListener('change', () => {
      if (lastLat !== null && lastLon !== null && lastHeading !== null) {
        updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);
      }
    });
    
    // If change the map type then update the map
    mapTypeSelect.addEventListener('change', () => {
      if (lastLat !== null && lastLon !== null && lastHeading !== null) {
        updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);  // Update map
      }
    });
    
    // If change the image type then update the map
    imageTypeSelect.addEventListener('change', () => {
      if (lastLat !== null && lastLon !== null && lastHeading !== null) {
        updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);
      }
    });

    
    // Helper function for map refresh. Is the position not moved, then refrash the map all 60s
    function startMapRefreshInterval() {   
      setInterval(() => {
          const now = Date.now();

          // If the last update timestamp greater than 60s then update the map automatically 
          const secondsSinceLastUpdate = (now - lastMapUpdateTime) / 1000;

          if (secondsSinceLastUpdate >= 60 && lastLat !== null && lastLon !== null && lastHeading !== null) {
            updateMapDirect(lastLat, lastLon, lastHeading, zoomLevel);
          }
      }, 1000); // Check the update time stamp all 1s 

    }
    
    // If visibility changed, the activate wake lock. The dispay is allways on for mobile devices
    document.addEventListener('visibilitychange', () => {
      if (wakeLock !== null && document.visibilityState === 'visible') {
        requestWakeLock();
      }
    });
    
    // Start direct after HTML parser finished (at this time no picture and tyle sheets loaded)
    window.addEventListener('DOMContentLoaded', () => {
      setInputDefaults(); // schnell IP & Port setzen
    });
    
    // Start helper functions for website (all components are loaded) 
    window.addEventListener('load', () => {
      const hasGET = getQueryParam('ip') && getQueryParam('port');
      if (!hasGET) {
        loadSavedConnection(); // If no GET parameters received  then read cookies on start
        shouldReconnect = true;
        connect();
      }
      startMapRefreshInterval(); // Start automatic map update all 60s without position changes
      handleAutoResolutionFlip();   // Start automatic flip resolution for mobile devices with integrated orientation sensor
      requestWakeLock(); // Activate wake lock for screen an mobile devices
    });

