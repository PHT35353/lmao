import streamlit as st
import streamlit_javascript as stjs
import pandas as pd
import math
import requests
import json
import io
import os
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript as stjs 
import time
from fastapi import FastAPI
from pydantic import BaseModel
import threading
import uvicorn

# Set page layout to wide
st.set_page_config(layout='wide')

# Set up a title for the app
st.title("Piping tool")

# Add instructions and explain color options
st.markdown("""
This tool allows you to:
1. Draw rectangles (polygons), lines, and markers (landmarks) on the map.
2. Assign names and choose specific colors for each feature individually upon creation.
3. Display distances for lines and dimensions for polygons both on the map and in the sidebar.
4. Show relationships between landmarks and lines (e.g., a line belongs to two landmarks).

**Available Colors**:
- Named colors: red, blue, green, yellow, purple, cyan, pink, orange, black, white, gray
- Hex colors: #FF0000 (red), #00FF00 (green), #0000FF (blue), #FFFF00 (yellow), #800080 (purple), #00FFFF (cyan), #FFC0CB (pink), #FFA500 (orange), #000000 (black), #FFFFFF (white), #808080 (gray)
""")

# Sidebar to manage the map interactions
st.sidebar.title("Map Controls")

# Default location set to Amsterdam, Netherlands
default_location = [52.3676, 4.9041]

# Input fields for latitude and longitude with unique keys
latitude = st.sidebar.number_input("Latitude", value=default_location[0], key="latitude_input")
longitude = st.sidebar.number_input("Longitude", value=default_location[1], key="longitude_input")

# Mapbox GL JS API token
mapbox_access_token = "pk.eyJ1IjoicGFyc2ExMzgzIiwiYSI6ImNtMWRqZmZreDB6MHMyaXNianJpYWNhcGQifQ.hot5D26TtggHFx9IFM-9Vw"


# Function to search for an address and automatically fill in the coordinates
def search_address_and_fill_coordinates():
    # Input for the address search with a unique key
    address_search = st.sidebar.text_input("Search for address (requires internet connection)", key="address_search_fill")

    # If the user searches for an address
    if address_search:
        geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address_search}.json?access_token={mapbox_access_token}"

        try:
            # Request the geocoded location from Mapbox API
            response = requests.get(geocode_url)
            if response.status_code == 200:
                geo_data = response.json()
                if len(geo_data['features']) > 0:
                    # Extract coordinates of the first result
                    coordinates = geo_data['features'][0]['center']
                    place_name = geo_data['features'][0]['place_name']
                    
                    # Auto-fill the latitude and longitude fields
                    latitude = coordinates[1]
                    longitude = coordinates[0]

                    # Notify user and auto-fill the coordinates in the Streamlit sidebar
                    st.sidebar.success(f"Address found: {place_name}")
                    st.sidebar.write(f"Coordinates: Latitude {latitude}, Longitude {longitude}")
                    return latitude, longitude  # Return the found coordinates
                else:
                    st.sidebar.error("Address not found.")
                    return None, None
            else:
                st.sidebar.error("Error connecting to the Mapbox API.")
                return None, None
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
            return None, None
    return None, None


# Call the search function and retrieve the coordinates
latitude, longitude = search_address_and_fill_coordinates()

# Set the default location in case no search result is found
if latitude is None or longitude is None:
    latitude = default_location[0]  # Default latitude if no search is done
    longitude = default_location[1]  # Default longitude if no search is done

# Button to search for a location
if st.sidebar.button("Search Location"):
    default_location = [latitude, longitude]

# HTML and JS for Mapbox with Mapbox Draw plugin to add drawing functionalities
# HTML and JS for Mapbox with Mapbox Draw plugin to add drawing functionalities
mapbox_map_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Mapbox GL JS Drawing Tool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.10.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.10.0/mapbox-gl.css" rel="stylesheet" />
    <script src="https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.3.0/mapbox-gl-draw.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.3.0/mapbox-gl-draw.css" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/@turf/turf/turf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/0.4.1/html2canvas.min.js"></script>

    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
        #map {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
        }}
        .mapboxgl-ctrl {{
            margin: 10px;
        }}
        #sidebar {{
            position: absolute;
            top: 0;
            left: 0;
            width: 300px;
            height: 100%;
            background-color: white;
            border-right: 1px solid #ccc;
            z-index: 1;
            padding: 10px;
            transition: all 0.3s ease;
        }}
        #sidebar.collapsed {{
            width: 0;
            padding: 0;
            overflow: hidden;
        }}
        #toggleSidebar {{
            position: absolute;
            bottom: 290px;
            right: 10px;
            z-index: 2;
            background-color: white;
            color:black;
            border: 1px solid #ccc;
            padding: 10px 15px;
            cursor: pointer;
            margin-bottom: 10px;
        }}
        #sidebarContent {{
            max-height: 90%;
            overflow-y: auto;
        }}
        h3 {{
            margin-top: 0;
        }}
    </style>
</head>
<body>
<div id="sidebar" class="sidebar">
    <div id="sidebarContent">
        <h3>Measurements</h3>
        <div id="measurements"></div>
    </div>
</div>
<button id="toggleSidebar" onclick="toggleSidebar()">Collapse</button>
<button id="saveMapButton" onclick="saveMap()">Save Map</button>
<button id="loadMapButton" onclick="loadMap()">Load Map</button>
<div id="map"></div>
<script>
    let distanceListenerAdded = false;
    mapboxgl.accessToken = '{mapbox_access_token}';

    const map = new mapboxgl.Map({{
        container: 'map',
        style: 'mapbox://styles/mapbox/satellite-streets-v12',
        center: [{longitude}, {latitude}],
        zoom: 20,
        pitch: 45, // For 3D effect
        bearing: 0, // Rotation angle
        antialias: true
    }});

    // Add map controls for zoom, rotation, and fullscreen
    map.addControl(new mapboxgl.NavigationControl());
    map.addControl(new mapboxgl.FullscreenControl());

    // Enable rotation and pitch adjustments using right-click
    map.dragRotate.enable();
    map.touchZoomRotate.enableRotation();

    // Add the Draw control for drawing polygons, markers, lines, etc.
    const Draw = new MapboxDraw({{
        displayControlsDefault: false,
        controls: {{
            polygon: true,
            line_string: true,
            point: true,
            trash: true
        }},
    }});

    map.addControl(Draw);

     // Function to save the map data to the backend
    function saveMap() {{
        const mapData = Draw.getAll();  // Get all drawn features from Mapbox
        const user_id = "user1";  // Replace with dynamic user ID if needed

        // Save feature colors and names
        mapData.features.forEach((feature) => {{
            feature.properties.color = featureColors[feature.id] || 'defaultColor';
            feature.properties.name = featureNames[feature.id] || '';
        }});

        fetch("https://fastapi-test-production-1ba4.up.railway.app/save-map/", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
            }},
            body: JSON.stringify({{
                user_id: user_id,
                map_data: mapData
            }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.status === "success") {{
                alert("Map data saved successfully!");
            }} else {{
                alert("Failed to save map data.");
            }}
        }})
        .catch(error => {{
            console.error("Error saving map data:", error);
        }});
    }}

    // Function to load the saved map data from the backend
   function loadMap() {{
    const user_id = "user1";  // Replace with dynamic user ID if needed

    fetch(`https://fastapi-test-production-1ba4.up.railway.app/load-map/${{user_id}}`)
    .then(response => response.json())
    .then(data => {{
        if (data.status === "success") {{
            const savedMapData = data.map_data;

            // Clear existing drawings before loading new data
            Draw.deleteAll();
            
            // Add the saved features back to the map
            Draw.add(savedMapData);

            // Restore feature colors, names, and update pipeData for distances
            savedMapData.features.forEach((feature) => {{
                if (feature.properties.color) {{
                    featureColors[feature.id] = feature.properties.color;
                }}
                if (feature.properties.name) {{
                    featureNames[feature.id] = feature.properties.name;
                }}
                if (feature.geometry.type === 'LineString') {{
                    const length = turf.length(feature, {{ units: 'meters' }});
                    pipeData[feature.id] = {{
                        name: featureNames[feature.id],
                        distance: length
                    }};
                }}
            }});

            // Send the updated pipe data to the backend
            sendPipeDataToBackend();

            // Update the sidebar measurements with the loaded features
            updateSidebarMeasurements({{ features: savedMapData.features }});

            alert("Map data loaded successfully!");
        }} else {{
            alert("No saved map data found.");
        }}
    }})
    .catch(error => {{
        console.error("Error loading map data:", error);
    }});
}}


    window.onbeforeunload = function () {{
        if (!mapSaved) {{
            return "You have unsaved changes on the map. Are you sure you want to leave without saving?";
        }}
    }};

    // Add style and positioning for the buttons
    const saveButton = document.getElementById("saveMapButton");
    const loadButton = document.getElementById("loadMapButton");

    saveButton.style.position = "absolute";
    saveButton.style.bottom = "250px";
    saveButton.style.right = "10px";
    saveButton.style.zIndex = "2";
    saveButton.style.backgroundColor = "white";
    saveButton.style.color = "black";
    saveButton.style.border = "1px solid #ccc";
    saveButton.style.padding = "10px 15px";
    saveButton.style.cursor = "pointer";

    loadButton.style.position = "absolute";
    loadButton.style.bottom = "200px";
    loadButton.style.right = "10px";
    loadButton.style.zIndex = "2";
    loadButton.style.backgroundColor = "white";
    loadButton.style.color = "black";
    loadButton.style.border = "1px solid #ccc";
    loadButton.style.padding = "10px 15px";
    loadButton.style.cursor = "pointer";

    let landmarkCount = 0;
    let landmarks = [];
    let featureColors = {{}};
    let featureNames = {{}};

let mapSaved = true;

let pipeData = {{}};  // Global object to store pipe data, including names and distances

// Attach the updateMeasurements function to Mapbox draw events
let unnamedPipeCount = 1; // Global counter for unnamed pipes

map.on('draw.create', (e) => {{
    const feature = e.features[0];

    // Handle LineString creation
    if (feature.geometry.type === 'LineString') {{
        const name = prompt("Enter a name for this line:");
        feature.properties.name = name || `Unnamed Pipe ${{unnamedPipeCount}}`;
        featureNames[feature.id] = feature.properties.name;
        unnamedPipeCount++;

        // Calculate the length of the line and store it
        const length = turf.length(feature, {{ units: 'meters' }});
        pipeData[feature.id] = {{
            name: feature.properties.name,
            distance: length
        }};

        // Send updated pipe data to the backend
        sendPipeDataToBackend();
    }}

    // Handle Point creation (Landmarks)
    if (feature.geometry.type === 'Point') {{
        const name = prompt("Enter a name for this landmark:");
        feature.properties.name = name || `Landmark ${{landmarkCount + 1}}`;
        featureNames[feature.id] = feature.properties.name;
        landmarks.push(feature);
        landmarkCount++;

        // Send updated landmark data to the backend
        sendLandmarkDataToBackend();
    }}

    // Update the sidebar measurements
    updateSidebarMeasurements(e);
    mapSaved = false;
}});


map.on('draw.update', (e) => {{
    e.features.forEach((feature) => {{
        if (feature.geometry.type === 'LineString') {{
            // Ensure the line has a name
            if (!feature.properties.name) {{
                if (!featureNames[feature.id]) {{
                    featureNames[feature.id] = `Unnamed Pipe ${{unnamedPipeCount}}`;
                    unnamedPipeCount++;
                }}
                feature.properties.name = featureNames[feature.id];
            }}

            // Update the line's length in pipeData
            const length = turf.length(feature, {{ units: 'meters' }});
            pipeData[feature.id] = {{
                name: feature.properties.name,
                distance: length
            }};
        }}

        if (feature.geometry.type === 'Point') {{
            // Ensure the landmark has a name
            if (!feature.properties.name) {{
                if (!featureNames[feature.id]) {{
                    feature.properties.name = `Landmark ${{landmarkCount + 1}}`;
                    featureNames[feature.id] = feature.properties.name;
                }}
            }}

            // Update the landmark data in the landmarks array
            const existingLandmark = landmarks.find((lm) => lm.id === feature.id);
            if (existingLandmark) {{
                existingLandmark.geometry.coordinates = feature.geometry.coordinates;
                existingLandmark.properties.name = feature.properties.name;
            }} else {{
                landmarks.push(feature);
            }}

            // Update the backend with the modified landmark data
            sendLandmarkDataToBackend();
        }}
    }});

    // Send updated pipe data to the backend
    sendPipeDataToBackend();

    // Update the sidebar measurements
    updateSidebarMeasurements(e);
    mapSaved = false;
}});



map.on('draw.delete', (e) => {{
   deleteFeature(e);
   mapSaved = false
}});


function sendLandmarkDataToBackend() {{
    const landmarksData = landmarks.map((landmark) => ({{
        name: landmark.properties.name,
        coordinates: landmark.geometry.coordinates,
        color: featureColors[landmark.id] || "black"
    }}));

    fetch("https://fastapi-test-production-1ba4.up.railway.app/send-landmarks/", {{
        method: "POST",
        headers: {{
            "Content-Type": "application/json",
        }},
        body: JSON.stringify({{ landmarks: landmarksData }})
    }})
        .then((response) => response.json())
        .then((data) => {{
            if (data.status === "success") {{
                console.log("Landmarks sent successfully:", data);
            }} else {{
                console.error("Failed to send landmarks:", data.message);
            }}
        }})
        .catch((error) => {{
            console.error("Error sending landmarks:", error);
        }});
}}

function getSelectedDistances() {{
    let selectedPipes = [];

    document.querySelectorAll('input[type=checkbox]:checked').forEach(checkbox => {{
        const pipeId = checkbox.id;
        if (pipeData[pipeId]) {{
            const {{ name, distance }} = pipeData[pipeId];
            selectedPipes.push({{ name: name || 'Unnamed Pipe', distance: distance }});
        }}
    }});

    if (selectedPipes.length > 0) {{
        // Send the selected pipes (with names and distances) to the FastAPI backend
        fetch("https://fastapi-test-production-1ba4.up.railway.app/send-pipes/", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
            }},
            body: JSON.stringify({{ pipes: selectedPipes }})  // Sending the pipes with names and distances as a JSON body
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.status === "success") {{
                console.log("Pipes sent successfully:", data);
            }} else {{
                console.error("Failed to send pipes:", data.message);
            }}
        }})
        .catch(error => {{
            console.error("Error sending pipes:", error);
        }});
    }} else {{
        console.log("No pipes selected.");
    }}
}}

// Function to send the pipe data (names, distances, and coordinates) to the FastAPI backend
function sendPipeDataToBackend() {{
    const pipeList = Object.keys(pipeData).map(pipeId => {{
        const feature = Draw.get(pipeId);
        const startCoord = feature.geometry.coordinates[0];
        const endCoord = feature.geometry.coordinates[feature.geometry.coordinates.length - 1];

        // Identify landmarks for the start and end points of the line
        const startLandmark = landmarks.find(lm => turf.distance(lm.geometry.coordinates, startCoord) < 0.01);
        const endLandmark = landmarks.find(lm => turf.distance(lm.geometry.coordinates, endCoord) < 0.01);

        // Format the pipe name to include landmark names
        const pipeName = ` ${{pipeData[pipeId].name}}`;

        return {{
            name: pipeName, // Use the formatted name
            distance: pipeData[pipeId].distance,
            coordinates: feature ? feature.geometry.coordinates : []
        }};
    }});

    // Send the pipe list to the backend
    fetch("https://fastapi-test-production-1ba4.up.railway.app/send-pipes/", {{
        method: "POST",
        headers: {{
            "Content-Type": "application/json",
        }},
        body: JSON.stringify({{ pipes: pipeList }})
    }})
    .then(response => response.json())
    .then(data => {{
        if (data.status === "success") {{
            console.log("Pipes sent successfully:", data);
        }} else {{
            console.error("Failed to send pipes:", data.message);
        }}
    }})
    .catch(error => {{
        console.error("Error sending pipes:", error);
    }});
}}




 function updateSidebarMeasurements(e) {{
        const data = Draw.getAll();
        let sidebarContent = "";
        let totalDistances = []; 
        if (data.features.length > 0) {{
            const features = data.features;
            sidebarContent += '<h4>Select lines for price calculation:</h4>';
            features.forEach(function (feature, index) {{
                if (feature.geometry.type === 'LineString') {{
                    const length = turf.length(feature, {{ units: 'meters' }});
                    totalDistances.push(length);
                    const startCoord = feature.geometry.coordinates[0];
                    const endCoord = feature.geometry.coordinates[feature.geometry.coordinates.length - 1];
                    
                    
                    let distanceId = 'line' + index;
                    sidebarContent += '<input type="checkbox" id="' + distanceId + '" value="' + length + '" />';
                    sidebarContent += '<label for="' + distanceId + '">' + (featureNames[feature.id] || 'Line ' + (index + 1)) + ': ' + length.toFixed(2) + ' m</label><br>';


                    // Identify landmarks for the start and end points of the line
                    let startLandmark = landmarks.find(lm => turf.distance(lm.geometry.coordinates, startCoord) < 0.01);
                    let endLandmark = landmarks.find(lm => turf.distance(lm.geometry.coordinates, endCoord) < 0.01);

                    if (!featureNames[feature.id]) {{
                        const name = prompt("Enter a name for this line:");
                        featureNames[feature.id] = name || "Line " + (index + 1);
                        feature.properties.name = featureNames[feature.id];
                    }}

                    if (!featureColors[feature.id]) {{
                        const lineColor = prompt("Enter a color for this line (e.g., red, purple, cyan, pink):");
                        featureColors[feature.id] = lineColor || 'blue';
                    }}

                    // Update the feature's source when it's moved to ensure the color moves with it
                    map.getSource('line-' + feature.id)?.setData(feature);

                    map.addLayer({{
                        id: 'line-' + feature.id,
                        type: 'line',
                        source: {{
                            type: 'geojson',
                            data: feature
                        }},
                        layout: {{}},
                        paint: {{
                            'line-color': featureColors[feature.id],
                            'line-width': 4
                        }}
                    }});

                    let distanceUnit = 'm';
                    let distanceValue = length >= 1 ? length.toFixed(2) : (length * 1000).toFixed(2);
                    sidebarContent += '<p>Line ' + featureNames[feature.id] + ' belongs to ' + (startLandmark?.properties.name || 'Unknown') + ' - ' + (endLandmark?.properties.name || 'Unknown') + ': ' + distanceValue + ' ' + distanceUnit + '</p>';
                    

                    
                }} else if (feature.geometry.type === 'Polygon') {{
                    if (!feature.properties.name) {{
                        if (!featureNames[feature.id]) {{
                            const name = prompt("Enter a name for this polygon:");
                            feature.properties.name = name || "Polygon " + (index + 1);
                            featureNames[feature.id] = feature.properties.name;
                        }} else {{
                            feature.properties.name = featureNames[feature.id];
                        }}
                    }}

                    if (!featureColors[feature.id]) {{
                        const polygonColor = prompt("Enter a color for this polygon (e.g., green, yellow):");
                        featureColors[feature.id] = polygonColor || 'yellow';
                    }}

                    // Update the feature's source when it's moved to ensure the color moves with it
                    map.getSource('polygon-' + feature.id)?.setData(feature);

                    map.addLayer({{
                        id: 'polygon-' + feature.id,
                        type: 'fill',
                        source: {{
                            type: 'geojson',
                            data: feature
                        }},
                        paint: {{
                            'fill-color': featureColors[feature.id],
                            'fill-opacity': 0.6
                        }}
                    }});

                    const bbox = turf.bbox(feature);
                    const width = turf.distance([bbox[0], bbox[1]], [bbox[2], bbox[1]]);
                    const height = turf.distance([bbox[0], bbox[1]], [bbox[0], bbox[3]]);

                    let widthUnit = width >= 1 ? 'km' : 'm';
                    let heightUnit = height >= 1 ? 'km' : 'm';
                    let widthValue = width >= 1 ? width.toFixed(2) : (width * 1000).toFixed(2);
                    let heightValue = height >= 1 ? height.toFixed(2) : (height * 1000).toFixed(2);

                    sidebarContent += '<p>Polygon ' + feature.properties.name + ': Width = ' + widthValue + ' ' + widthUnit + ', Height = ' + heightValue + ' ' + heightUnit + '</p>';
                }} else if (feature.geometry.type === 'Point') {{
                    // Handle landmarks (points)
                    if (!feature.properties.name) {{
                        if (!featureNames[feature.id]) {{
                            const name = prompt("Enter a name for this landmark:");
                            feature.properties.name = name || "Landmark " + (landmarkCount + 1);
                            featureNames[feature.id] = feature.properties.name;
                            landmarks.push(feature);
                            landmarkCount++;
                        }} else {{
                            feature.properties.name = featureNames[feature.id];
                        }}
                    }}

                    if (!featureColors[feature.id]) {{
                        const markerColor = prompt("Enter a color for this landmark (e.g., black, white):");
                        featureColors[feature.id] = markerColor || 'black';
                    }}

                    map.getSource('marker-' + feature.id)?.setData(feature);

                    map.addLayer({{
                        id: 'marker-' + feature.id,
                        type: 'circle',
                        source: {{
                            type: 'geojson',
                            data: feature
                        }},
                        paint: {{
                            'circle-radius': 8,
                            'circle-color': featureColors[feature.id]
                        }}
                    }});

                    sidebarContent += '<p>Landmark ' + feature.properties.name + '</p>';
                }}
            }});
             sidebarContent += '<input type="checkbox" id="totalDistance" value="' + totalDistances.reduce((a, b) => a + b, 0) + '" />';
             sidebarContent += '<label for="totalDistance">Total Distance: ' + totalDistances.reduce((a, b) => a + b, 0).toFixed(2) + ' m</label><br>';
             sidebarContent += '<br><button onclick="getSelectedDistances()">Send Selected Distances</button>';
        }} else {{
            sidebarContent = "<p>No features drawn yet.</p>";
        }}
        document.getElementById('measurements').innerHTML = sidebarContent;
   }}
    
// Function to toggle the sidebar
    function toggleSidebar() {{
        var sidebar = document.getElementById('sidebar');
        var toggleButton = document.getElementById('toggleSidebar');

        if (sidebar.classList.contains('collapsed')) {{
            sidebar.classList.remove('collapsed');
            toggleButton.innerText = "Close Sidebar";
        }} else {{
            sidebar.classList.add('collapsed');
            toggleButton.innerText = "Open Sidebar";
        }}
    }}

    // Initialize the sidebar to be collapsed when the page loads
    document.addEventListener("DOMContentLoaded", function () {{
        var sidebar = document.getElementById('sidebar');
        var toggleButton = document.getElementById('toggleSidebar');

        // Add the 'collapsed' class to collapse the sidebar initially
        sidebar.classList.add('collapsed');
        toggleButton.innerText = "Open Sidebar";
    }});

  // Function to handle deletion of features
function deleteFeature(e) {{
    const features = e.features;
    features.forEach(function (feature) {{
        const featureId = feature.id;

        // Remove the feature's associated color and name from dictionaries
        delete featureColors[featureId];
        delete featureNames[featureId];
        delete pipeData[featureId];

        // Remove the layer associated with the feature, if it exists
        if (map.getLayer('line-' + featureId)) {{
            map.removeLayer('line-' + featureId);
            map.removeSource('line-' + featureId);
        }}

        if (map.getLayer('polygon-' + featureId)) {{
            map.removeLayer('polygon-' + featureId);
            map.removeSource('polygon-' + featureId);
        }}

        if (map.getLayer('marker-' + featureId)) {{
            map.removeLayer('marker-' + featureId);
            map.removeSource('marker-' + featureId);
        }}

        console.log(`Feature ${{featureId}} and its color have been removed.`);
    }});

   
    updateSidebarMeasurements(e)
}}


</script>
</body>
</html>
"""
components.html(mapbox_map_html, height=600)

################################### Pipe calculation ##################################################
#the pip price calculation par of the code:
# Pipe data dictionaries
B1001_data_dict = {
    'Nominal diameter (inches)': ['0.5', '0.75', '1', '1.5', '2', '3', '4', '5', '6', '8', '10', '12', '14', '16', '20'],
    'External diameter (mm)': ['21.3', '26.7', '33.4', '48.3', '60.3', '88.9', '114.3', '141.3', '168.3', '219.1', '273', '323.9', '355.6', '406.4', '508'],
    'Wall thickness (mm)': ['2.8', '2.9', '3.4', '3.7', '3.9', '5.5', '6', '6.6', '7.1', '8.2', '9.3', '9.5', '9.5', '9.5', '9.5'],
    'Weight (kg/m)': ['1.27', '1.68', '2.5', '4.05', '5.44', '11.3', '16.1', '21.8', '28.3', '42.5', '60.3', '73.8', '81.3', '93.3', '117'],
    'Cost per 100 m (Euro)': ['277', '338', '461', '707', '738', '1310', '1805', '2615', '3360', '5165', '7450', '9350', '11235', '13020', '16490'],
    'Pressure (bar)': ['215.59', '178.13', '166.95', '125.63', '106.07', '101.46', '86.09', '76.6', '69.19', '61.38', '55.87', '48.1', '43.81', '38.34', '30.67']
}

B1003_data_dict = {
    'Nominal diameter (inches)': ['0.5', '0.75', '1.0', '1.5', '2.0', '3.0', '4.0', '5.0', '6.0', '8.0', '10.0', '12.0', '14.0', '16.0', '20.0'],
    'External diameter (mm)': ['21.3', '26.7', '33.4', '48.3', '60.3', '88.9', '114.3', '141.3', '168.3', '219.1', '273.0', '323.9', '355.6', '406.4', '508.0'],
    'Wall thickness (mm)': ['3.7', '3.9', '4.5', '5.1', '5.5', '7.6', '8.6', '9.5', '11.0', '12.7', '12.7', '12.7', '12.7', '12.7', '12.7'],
    'Weight (kg/m)': ['1.62', '2.2', '3.24', '5.41', '7.48', '15.3', '22.3', '31.0', '42.6', '64.6', '81.6', '97.5', '107.0', '123.16', '155.0'],
    'Cost per 100 m (Euro)': ['315', '389', '536', '840', '1060', '1755', '2635', '3770', '4895', '8010', '10285', '12375', '14905', '17045', '21235'],
    'Pressure (bar)': ['158.27', '133.08', '122.75', '96.2', '83.1', '77.89', '68.55', '61.26', '59.55', '52.81', '42.39', '35.72', '32.54', '28.47', '22.78']
}

B1005_data_dict = {
    'Nominal diameter (inches)': ['0.5', '0.75', '1.0', '1.25', '1.5', '2.0', '2.5', '3.0', '4.0', '5.0', '6.0', '8.0', '10.0', '12.0'],
    'External diameter (mm)': ['21.34', '26.67', '33.4', '42.16', '48.26', '60.32', '73.02', '88.9', '114.3', '141.3', '168.27', '219.07', '273.05', '323.85'],
    'Wall thickness (mm)': ['2.11', '2.11', '2.77', '2.77', '2.77', '2.77', '3.05', '3.05', '3.05', '3.4', '3.4', '3.76', '4.19', '4.57'],
    'Weight (kg/m)': ['0.99', '1.27', '2.08', '2.69', '3.1', '3.92', '5.25', '6.44', '8.34', '11.56', '13.82', '19.92', '27.75', '35.96'],
    'Cost per m04 (Euro)': ['10.7', '14.0', '18.0', '22.2', '38.6', '24.0', '32.0', '40.0', '57.0', '75.0', '97.4', '104.0', '180.0', '194.0'],
    'Cost per m16 (Euro)': ['13.0', '18.0', '23.0', '26.0', '44.9', '34.0', '40.0', '49.0', '64.1', '93.0', '120.0', '133.0', '210.0', '228.0'],
    'Pressure (bar)': ['202.69', '162.19', '170.01', '134.69', '117.66', '94.14', '85.63', '70.33', '54.7', '49.33', '41.42', '35.19', '31.46', '28.93']
}

B10051_data_dict = {
    'Nominal diameter (inches)': ['0.5', '0.75', '1.0', '1.25', '1.5', '2.0', '2.5', '3.0', '4.0', '5.0', '6.0', '8.0', '10.0', '12.0'], 
    'External diameter (mm)': ['21.34', '26.67', '33.4', '42.16', '48.26', '60.32', '73.02', '88.9', '114.3', '141.3', '168.27', '219.07', '273.05', '323.85'], 
    'Wall thickness (mm)': ['2.11', '2.11', '2.77', '2.77', '2.77', '2.77', '3.05', '3.05', '3.05', '3.4', '3.4', '3.76', '4.19', '4.57'], 
    'Weight (kg/m)': ['0.99', '1.27', '2.08', '2.69', '3.1', '3.92', '5.25', '6.44', '8.34', '11.56', '13.82', '19.92', '27.75', '35.96'], 
    'Cost per m04 (Euro)': ['10.7', '14.0', '18.0', '22.2', '38.6', '24.0', '32.0', '40.0', '57.0', '75.0', '97.4', '104.0', '180.0', '194.0'], 
    'Cost per m16 (Euro)': ['13.0', '18.0', '23.0', '26.0', '44.9', '34.0', '40.0', '49.0', '64.1', '93.0', '120.0', '133.0', '210.0', '228.0'], 
    'Pressure (bar)': ['202.69', '162.19', '170.01', '134.69', '117.66', '94.14', '85.63', '70.33', '54.7', '49.33', '41.42', '35.19', '31.46', '28.93'],
}

B1008_data_dict = {
    'External diameter (mm)': ['25', '32', '40', '50', '50', '63', '63', '75', '75', '90', '90', '110', '110', '125', '125', '160', '160', '200', '200', '250'],
    'Wall thickness (mm)': ['1.5', '1.8', '1.9', '1.8', '2.4', '1.8', '3.0', '2.6', '3.6', '2.7', '4.3', '3.2', '5.3', '3.7', '6.0', '4.7', '7.7', '5.4', '6.3', '7.3'],
    'Pressure (bar)': ['10', '10', '10', '6', '10', '6', '10', '6', '10', '6', '10', '6', '10', '6', '10', '6', '10', '6', '10', '6'],
    'Cost per 100 m (Euro)': ['208', '243', '312', '370', '445', '531', '658', '728', '959', '1180', '1365', '1500', '1985', '2170', '2770', '3475', '4475', '5475', '7450', '9250']
}

# Function to calculate pressure using Barlow's formula
def Barlow(S, D, t):
    P = (2 * S * t) / D
    return P

# Streamlit user inputs
def get_user_inputs1():
    pressure = st.number_input("Enter the pressure (bar):", min_value=0.0, format="%.2f")
    temperature = st.number_input("Enter the temperature (°C):", min_value=0.0, format="%.2f")
    medium = st.selectbox(
    "Select the medium:",
    ["Steam", "Pressurized Water", "Water Glycol", "Thermal Oil"]
)
    return pressure, temperature, medium

# Function to choose pipe material based on user input
def choose_pipe_material(P, T, M):
   # Medium constraints
        if M.lower() in ('water glycol', 'water-glycol', 'pressurized water', 'pressurized-water'):
            if P > 10 and T < 425:
                return 'B1005'
            elif P > 10 and 425 <= T < 800:
                return 'B10051'
            else:
                return 'B1008'

        # Pipe material choices based on pressure and temperature
        if P <= 10:
            if T < 60:
                material = 'B1008'
            elif 60 <= T < 425:
                material = 'B1001'  # Specify both B1001 and B1003 as valid options
            else:
                material = 'B1008'
        else:
            if 0 <= T < 425:
                material = 'B1001'  # Specify both B1001 and B1003 as valid options
            elif 425 <= T < 600:
                material = 'B1005'
            else:
                material = 'B10051'

        # Medium-specific constraints
        if M.lower() in ('steam', 'thermal oil', 'thermal-oil'):
            return material
        else:
            # Handle the case for B1003 when applicable
            if M.lower() in ('water glycol', 'water-glycol', 'pressurized water', 'pressurized-water'):
                return 'B1008' if material != 'B1005' else material
            
def stress_b1001(T): #For T < 413 and not anti corrosion

    B1001_data_dict['External diameter (mm)'] = list(map(float, B1001_data_dict['External diameter (mm)']))
    B1001_data_dict['Wall thickness (mm)'] = list(map(float, B1001_data_dict['Wall thickness (mm)']))
    FOS = 3  # Updated to 3
    Bar_yield_strength = -2.10416*T + 2502.083 #Assumption ASTM A106 grade B
    Allowable_stress_bar = Bar_yield_strength / FOS
    
    x = [Barlow(Allowable_stress_bar, dia, thick) for dia, thick in zip(B1001_data_dict['External diameter (mm)'], B1001_data_dict['Wall thickness (mm)'])]
    Pressure_allowance = [round(i, 2) for i in x]
    B1001_data_dict.update({'Pressure (bar)': Pressure_allowance})

    return B1001_data_dict

def stress_b1005_304(T): #Stainless steel pipes corrosion  304L. -58 < T < 810 but goes to only 600
    B1005_data_dict['External diameter (mm)'] = list(map(float, B1005_data_dict['External diameter (mm)']))
    B1005_data_dict['Wall thickness (mm)'] = list(map(float, B1005_data_dict['External diameter (mm)']))
    FOS = 3  # Updated to 3

    match T:
        case T if 0 <= T < 175:
            Bar_yield_strength = (-40/11)*T + 2086.3636
        case T if 175 <= T < 290:
            Bar_yield_strength = (-34/23)*T + 1708.6956
        case T if 290 <= T < 460:
            Bar_yield_strength = (-12/17)*T + 1484.7058
        case T if 460 <= T < 600:
            Bar_yield_strength = -1*T + 1620

    Allowable_stress_bar = Bar_yield_strength / FOS 

    x = [Barlow(Allowable_stress_bar, dia, thick) for dia, thick in zip(B1005_data_dict['External diameter (mm)'],  B1005_data_dict['Wall thickness (mm)'])]
    Pressure_allowance = [round(i, 2) for i in x]
    B1005_data_dict.update({'Pressure bar': Pressure_allowance})

    return B1005_data_dict

def stress_b1003(T):# For T < 413 and not anti corrosion. This type is ticker than B1001
    B1003_data_dict['External diameter (mm)'] = list(map(float, B1003_data_dict['External diameter (mm)']))
    B1003_data_dict['Wall thickness (mm)'] = list(map(float, B1003_data_dict['Wall thickness (mm)']))
    FOS = 3  # Updated to 3
    Bar_yield_strength = -2.10416*T + 2502.083 #Assumption ASTM A106 grade B
    Allowable_stress_bar = Bar_yield_strength / FOS
    
    x = [Barlow(Allowable_stress_bar, dia, thick) for dia, thick in zip(B1003_data_dict['External diameter (mm)'],B1003_data_dict['Wall thickness (mm)'])]
    Pressure_allowance = [round(i, 2) for i in x]
    B1003_data_dict.update({'Pressure (bar)': Pressure_allowance})

    return B1003_data_dict

def stress_b1005_316L(T): #stainless steel pipes for corrosion that goes to 850 degrees celsius
    B10051_data_dict['External diameter (mm)'] = list(map(float, B10051_data_dict['External diameter (mm)']))
    B10051_data_dict['Wall thickness (mm)'] = list(map(float, B10051_data_dict['External diameter (mm)']))
    FOS = 3  # Updated to 3

    match T:
        case T if 10 <= T < 80:
            Bar_yield_strength = (-16/3)*T + 2386.6666
        case T if 80 <= T < 160:
            Bar_yield_strength = -3*T + 2200
        case T if 160 <= T < 270:
            Bar_yield_strength = (-27/11)*T + 2054.5454
        case T if 270 <= T < 350:
            Bar_yield_strength = -1*T + 1760
        case T if 350 <= T < 580:
            Bar_yield_strength = (-8/23)*T + 1531.7391
        case T if 580 <= T < 680:
            Bar_yield_strength = -1*T + 1910
        case T if 680 <= T < 850:
            Bar_yield_strength = (-23/12)*T + 2533.3333
        

    Allowable_stress_bar = Bar_yield_strength / FOS 

    x = [Barlow(Allowable_stress_bar, dia, thick) for dia, thick in zip(B10051_data_dict['External diameter (mm)'],  B10051_data_dict['Wall thickness (mm)'])]
    Pressure_allowance = [round(i, 2) for i in x]
    B10051_data_dict.update({'Pressure bar': Pressure_allowance})

    return B10051_data_dict


def stress_calculator(material, T):
    match material:
        case 'B1001':
            stress_b1001(T)
            stress_b1003(T)

        case 'B1005':
            stress_b1005_304(T)
            
        case 'B1008':
            pass
        
        case 'B10051':
            stress_b1005_316L(T)


def B1001_filter(P, distanceValue):
    # Process data as before
    B1001_data_dict['External diameter (mm)'] = list(map(float, B1001_data_dict['External diameter (mm)']))
    B1001_data_dict['Wall thickness (mm)'] = list(map(float, B1001_data_dict['Wall thickness (mm)']))
    B1001_data_dict['Cost per 100 m (Euro)'] = list(map(float, B1001_data_dict['Cost per 100 m (Euro)']))
    B1001_data_dict['Pressure (bar)'] = list(map(float, B1001_data_dict['Pressure (bar)']))

    B1001_data_dict['Cost per m (Euro)'] = [cost / 100 for cost in B1001_data_dict['Cost per 100 m (Euro)']]
    B1001_data_dict['Total Cost (Euro)'] = [round(p * distanceValue, 2) for p in B1001_data_dict['Cost per m (Euro)']]

    available_pipes = []
    for i in range(len(B1001_data_dict['Pressure (bar)'])):
        if B1001_data_dict['Pressure (bar)'][i] >= P:
            available_pipes.append({
                'External diameter (mm)': B1001_data_dict['External diameter (mm)'][i],
                'Wall thickness (mm)': B1001_data_dict['Wall thickness (mm)'][i],
                'Cost per m (Euro)': B1001_data_dict['Cost per m (Euro)'][i],
                'Total Cost (Euro)': B1001_data_dict['Total Cost (Euro)'][i]
            })

    # Return the filtered pipes
    return available_pipes



# Similar filters for B1003, B1005, and B1008 (will follow the same pattern)
def B1003_filter(P, distanceValue):
    B1003_data_dict['External diameter (mm)'] = list(map(float, B1003_data_dict['External diameter (mm)']))
    B1003_data_dict['Wall thickness (mm)'] = list(map(float, B1003_data_dict['Wall thickness (mm)']))
    B1003_data_dict['Cost per 100 m (Euro)'] = list(map(float, B1003_data_dict['Cost per 100 m (Euro)']))
    B1003_data_dict['Pressure (bar)'] = list(map(float, B1003_data_dict['Pressure (bar)']))
    
    B1003_data_dict['Cost per m (Euro)'] = [cost / 100 for cost in B1003_data_dict['Cost per 100 m (Euro)']]
    B1003_data_dict['Total Cost (Euro)'] = [round(p * distanceValue, 2) for p in B1003_data_dict['Cost per m (Euro)']]
    
    available_pipes = []
    for i in range(len(B1003_data_dict['Pressure (bar)'])):
        if B1003_data_dict['Pressure (bar)'][i] >= P:
            available_pipes.append({
                'External diameter (mm)': B1003_data_dict['External diameter (mm)'][i],
                'Wall thickness (mm)': B1003_data_dict['Wall thickness (mm)'][i],
                'Cost per m (Euro)': B1003_data_dict['Cost per m (Euro)'][i],
                'Total Cost (Euro)': B1003_data_dict['Total Cost (Euro)'][i]
            })


    # Return the filtered pipes
    return available_pipes

def B1005_filter(P, distanceValue):
    B1005_data_dict['External diameter (mm)'] = list(map(float, B1005_data_dict['External diameter (mm)']))
    B1005_data_dict['Wall thickness (mm)'] = list(map(float, B1005_data_dict['Wall thickness (mm)']))
    B1005_data_dict['Cost per m04 (Euro)'] = list(map(float, B1005_data_dict['Cost per m04 (Euro)']))
    B1005_data_dict['Pressure (bar)'] = list(map(float, B1005_data_dict['Pressure (bar)']))

    B1005_data_dict['Cost per m (Euro)'] = B1005_data_dict['Cost per m04 (Euro)']
    B1005_data_dict['Total Cost (Euro)'] = [round(p * distanceValue, 2) for p in B1005_data_dict['Cost per m (Euro)']]

    available_pipes = []
    for i in range(len(B1005_data_dict['Pressure (bar)'])):
        if B1005_data_dict['Pressure (bar)'][i] >= P:
            available_pipes.append({
                'External diameter (mm)': B1005_data_dict['External diameter (mm)'][i],
                'Wall thickness (mm)': B1005_data_dict['Wall thickness (mm)'][i],
                'Cost per m (Euro)': B1005_data_dict['Cost per m (Euro)'][i],
                'Total Cost (Euro)': B1005_data_dict['Total Cost (Euro)'][i]
            })


    # Return the filtered pipes
    return available_pipes

def B10051_filter(P, distanceValue):
    B10051_data_dict['External diameter (mm)'] = list(map(float, B10051_data_dict['External diameter (mm)']))
    B10051_data_dict['Wall thickness (mm)'] = list(map(float, B10051_data_dict['Wall thickness (mm)']))
    B10051_data_dict['Cost per m04 (Euro)'] = list(map(float, B10051_data_dict['Cost per m04 (Euro)']))
    B10051_data_dict['Pressure (bar)'] = list(map(float, B10051_data_dict['Pressure (bar)']))

    B10051_data_dict['Cost per m (Euro)'] = B10051_data_dict['Cost per m04 (Euro)']
    B10051_data_dict['Total Cost (Euro)'] = [round(p * distanceValue, 2) for p in B10051_data_dict['Cost per m (Euro)']]

    available_pipes = []
    for i in range(len(B10051_data_dict['Pressure (bar)'])):
        if B10051_data_dict['Pressure (bar)'][i] >= P:
            available_pipes.append({
                'External diameter (mm)': B10051_data_dict['External diameter (mm)'][i],
                'Wall thickness (mm)': B10051_data_dict['Wall thickness (mm)'][i],
                'Cost per m (Euro)': B10051_data_dict['Cost per m (Euro)'][i],
                'Total Cost (Euro)': B10051_data_dict['Total Cost (Euro)'][i]
            })

    # Return the filtered pipes
    return available_pipes


def B1008_filter(P, distanceValue):
    B1008_data_dict['External diameter (mm)'] = list(map(float, B1008_data_dict['External diameter (mm)']))
    B1008_data_dict['Wall thickness (mm)'] = list(map(float, B1008_data_dict['Wall thickness (mm)']))
    B1008_data_dict['Pressure (bar)'] = list(map(float, B1008_data_dict['Pressure (bar)']))
    B1008_data_dict['Cost per 100 m (Euro)'] = list(map(float, B1008_data_dict['Cost per 100 m (Euro)']))

    B1008_data_dict['Cost per m (Euro)'] = [cost / 100 for cost in B1008_data_dict['Cost per 100 m (Euro)']]
    B1008_data_dict['Total Cost (Euro)'] = [p * distanceValue for p in B1008_data_dict['Cost per m (Euro)']]

    available_pipes = []
    for i in range(len(B1008_data_dict['Pressure (bar)'])):
        if B1008_data_dict['Pressure (bar)'][i] >= P:
            available_pipes.append({
                'External diameter (mm)': B1008_data_dict['External diameter (mm)'][i],
                'Wall thickness (mm)': B1008_data_dict['Wall thickness (mm)'][i],
                'Cost per m (Euro)': B1008_data_dict['Cost per m (Euro)'][i],
                'Total Cost (Euro)': B1008_data_dict['Total Cost (Euro)'][i]
            })

    # Return the filtered pipes
    return available_pipes

# Function to choose pipe and filter based on material
def Pipe_finder(material, P, distanceValue):
    pipe_data = {}  # Dictionary to store results for all pipes

    if material == 'B1001':
        pipe_data['B1001'] = B1001_filter(P, distanceValue)
        pipe_data['B1003'] = B1003_filter(P, distanceValue)

    elif material == 'B1005':
        pipe_data['B1005'] = B1005_filter(P, distanceValue)
    
    elif material == 'B10051':
        pipe_data['B10051'] = B10051_filter(P, distanceValue)

    elif material == 'B1008':
        pipe_data['B1008'] = B1008_filter(P, distanceValue)

    else:
        st.write("Material not found")
        return {}

    return pipe_data  # Return all filtered pipe data as a dictionary
    
        
# Function to get user inputs including pressure, temperature, medium
def get_user_inputs():
    # Get pressure from user
    pressure = st.number_input("Enter the pressure (bar):", min_value=0.0, format="%.2f")

    # Get temperature from user
    temperature = st.number_input("Enter the temperature (°C):", min_value=0.0, format="%.2f")

    # Get medium from user
    medium = st.text_input("Enter the medium:")

    return pressure, temperature, medium
################################## API Data's ##################################################
# Function to check if FastAPI server is running
def check_server_status():
    try:
        response = requests.get("https://fastapi-test-production-1ba4.up.railway.app/")
        if response.status_code == 200:
            return True
        else:
            st.error(f"Server is not available. Status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to FastAPI server: {e}")
        return False


# Define API endpoints as constants for easy reusability
API_BASE_URL = "https://fastapi-test-production-1ba4.up.railway.app"
DISTANCES_ENDPOINT = f"{API_BASE_URL}/get-distances/"
LANDMARKS_ENDPOINT = f"{API_BASE_URL}/get-landmarks/"

def get_distance_values():
    """Fetch pipe data from the API and process it."""
    try:
        # Send GET request to the distances endpoint
        response = requests.get(DISTANCES_ENDPOINT)
        
        # Check if the response is successful
        if response.status_code != 200:
            st.error(f"API request failed with status code {response.status_code}: {response.text}")
            return None, None

        # Parse JSON data
        data = response.json()

        # Extract individual pipes and total distance
        individual_pipes = data.get("individual_pipes", [])
        total_distance = data.get("total_distance", 0)

        # Validate and return processed data
        if individual_pipes and total_distance > 0:
            return [
                {
                    "name": pipe.get("name", "Unnamed Pipe"),
                    "distance": pipe.get("distance", 0),
                    "coordinates": pipe.get("coordinates", [])
                }
                for pipe in individual_pipes
            ], total_distance
        else:
            st.warning("No valid pipe data available from the API.")
            return None, None
    except requests.exceptions.RequestException as req_error:
        st.error(f"Network error occurred while fetching distances: {req_error}")
        return None, None
    except ValueError as json_error:
        st.error(f"Error decoding JSON response: {json_error}")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None, None

def get_landmarks():
    """Fetch landmarks data from the FastAPI backend."""
    try:
        # Send GET request to the landmarks endpoint
        response = requests.get(LANDMARKS_ENDPOINT)
        
        # Check if the response is successful
        if response.status_code != 200:
            st.error(f"API request failed with status code {response.status_code}: {response.text}")
            return []

        # Parse JSON data
        data = response.json()

        # Validate and return landmarks data
        if data.get("status") == "success":
            return data.get("landmarks", [])
        else:
            st.warning("No landmarks data found.")
            return []
    except requests.exceptions.RequestException as req_error:
        st.error(f"Network error occurred while fetching landmarks: {req_error}")
        return []
    except ValueError as json_error:
        st.error(f"Error decoding JSON response: {json_error}")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return []
       


################################## Storage ##################################################

# File to store data persistently
DATA_FILE = "pipe_data.json"
PROCESSED_DATA_FILE = "processed_pipe_data.json"

def load_data():
    """Load pipe data from the JSON file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            st.error("Error decoding JSON file. Starting with empty data.")
            return {}
    return {}

def save_data(data):
    """Save pipe data to the JSON file safely."""
    temp_file = DATA_FILE + ".tmp"  # Temporary file
    try:
        with open(temp_file, "w") as file:
            json.dump(data, file, indent=4)
        os.replace(temp_file, DATA_FILE)  # Replace original file atomically
    except Exception as e:
        st.error(f"Failed to save data: {e}")

def validate_api_pipe(pipe):
    """Ensure a single pipe has all required fields."""
    required_keys = ["name", "coordinates", "distance"]
    return all(key in pipe for key in required_keys)

def integrate_api_data(pipe_data, api_pipes):
    """Integrate API data into the storage system."""
    for pipe in api_pipes:
        if not validate_api_pipe(pipe):
            st.warning(f"Skipping invalid pipe data: {pipe}")
            continue  # Skip invalid entries

        pipe_name = pipe["name"]
        if pipe_name not in pipe_data:  # Avoid duplicate entries
            pipe_data[pipe_name] = {
                "coordinates": pipe["coordinates"],
                "length": pipe["distance"]
            }
    save_data(pipe_data)  # Save updated data


def delete_pipe(pipe_data, pipe_name):
    """Delete a specific pipe by name from the storage."""
    # Check if the pipe exists
    if pipe_name in pipe_data:
        try:
            # Remove the pipe from the in-memory data
            del pipe_data[pipe_name]
            
            # Save the updated data to persistent storage atomically
            save_data(pipe_data)
            
            # Return success
            st.success(f"Pipe '{pipe_name}' deleted successfully.")
            return True
        except Exception as e:
            # Handle any errors during the save process
            st.error(f"Failed to delete pipe '{pipe_name}': {e}")
            return False
    else:
        # Warn if the pipe doesn't exist
        st.warning(f"Pipe '{pipe_name}' does not exist.")
        return False


def update_pipe_medium(pipe_data, pipe_name, medium):
    """Update the medium for a specific pipe in storage."""
    if pipe_name in pipe_data:
        try:
            # Update the medium for the specified pipe
            pipe_data[pipe_name]["medium"] = medium
            
            # Save the updated data to persistent storage
            save_data(pipe_data)
            
            # Return a success message
            return f"Success: Medium for pipe '{pipe_name}' updated to '{medium}'."
        except Exception as e:
            # Handle any errors during the save operation
            return f"Error: Failed to save updated data for pipe '{pipe_name}': {e}"
    else:
        # Feedback for a non-existent pipe
        return f"Error: Pipe '{pipe_name}' does not exist."
        

def find_closest_landmark(coord, landmarks, threshold=0.01):
    """Find the closest landmark to a given coordinate."""
    closest_landmark = None
    min_distance = float("inf")
    for landmark in landmarks:
        landmark_coord = landmark["coordinates"]
        distance = ((landmark_coord[0] - coord[0]) ** 2 + (landmark_coord[1] - coord[1]) ** 2) ** 0.5
        if distance <= threshold and distance < min_distance:
            closest_landmark = landmark["name"]
            min_distance = distance
    return closest_landmark or "Unknown"

def fetch_and_integrate_data(pipe_data):
    """Fetch API data for pipes and landmarks, and integrate it into storage."""
    api_pipes, total_distance = get_distance_values()
    landmarks = get_landmarks()
    
    if api_pipes:
        integrate_api_data(pipe_data, api_pipes)
       # st.success("Fetched and integrated pipe data from API successfully!")
        #st.write(f"Total Pipe Distance from API: {total_distance} meters")
    
    return landmarks
    

def add_landmarks_to_storage(pipe_data, landmarks):
    """Add landmarks to the storage, avoiding duplicates."""
    if landmarks:
        for landmark in landmarks:
            landmark_name = landmark["name"]
            if landmark_name not in pipe_data:
                pipe_data[landmark_name] = {
                    "coordinates": landmark["coordinates"],
                    "length": 0,  # Landmarks don't have a length
                    "medium": "N/A",  # Not applicable for landmarks
                }
    return pipe_data  # Return the updated data

def associate_pipes_with_landmarks(pipe_data, landmarks):
    """Associate each pipe with its closest landmarks."""
    associated_data = []
    for name, details in pipe_data.items():
        if "length" in details and details["length"] > 0:
            # Pipes: Associate with landmarks
            start_coord = details["coordinates"][0]
            end_coord = details["coordinates"][-1]
            start_landmark = find_closest_landmark(start_coord, landmarks)
            end_landmark = find_closest_landmark(end_coord, landmarks)
            formatted_name = f"Line {name} belongs to {start_landmark} - {end_landmark}"
        else:
            # Landmarks or others
            formatted_name = name
        associated_data.append(
            {
                "Name": formatted_name,
                "Coordinates": str(details["coordinates"]) if details["coordinates"] else "N/A",
                "Length (meters)": details.get("length", 0),
                "Medium": details.get("medium", "Not assigned"),
            }
        )
    return associated_data

def display_table(data): ## display tableeee
    """Display a given data table in Streamlit."""
    # Create a DataFrame
    df = pd.DataFrame(data)
    # Display the table
    st.subheader(title)
    st.table(df)
    return df

def display_data_table(pipe_data, landmarks): # LAndmarks and coords only
    """Display stored pipes and landmarks in a table."""
    # Step 1: Associate pipes with landmarks
    table_data = associate_pipes_with_landmarks(pipe_data, landmarks)
    # Step 2: Display the table
    return table_data #display_table(table_data)


def add_download_button(df):
    """Add a download button for the table data."""
    csv_data = io.StringIO()
    df.to_csv(csv_data, index=False)
    st.download_button(
        label="Download Table as CSV",
        data=csv_data.getvalue(),
        file_name="pipe_and_landmark_data.csv",
        mime="text/csv"
    )


def handle_delete_entry(pipe_data):
    """Allow the user to delete an entry by selecting from a dropdown menu."""
    st.header("Delete an Entry")

    # Get all stored pipe and landmark names
    entry_names = list(pipe_data.keys())

    # Dropdown for selecting an entry
    selected_entry = st.selectbox(
        "Select an Entry to Delete",
        options=["Select an entry"] + entry_names,  # Add a placeholder option
        help="Choose an entry (pipe or landmark) to delete from storage."
    )

    if selected_entry != "Select an entry":  # Ensure a valid selection
        # Add confirmation button
        if st.button(f"Confirm Deletion of '{selected_entry}'"):
            if delete_pipe(pipe_data, selected_entry):
                st.success(f"Entry '{selected_entry}' deleted successfully!")
            else:
                st.error(f"Failed to delete entry '{selected_entry}'.")



def refresh_data(pipe_data):
    """Clear all data and refresh the storage."""
    if st.button("Refresh Data"):
        pipe_data.clear()
        if save_data(pipe_data):  # Save the cleared data
            st.warning("All data has been refreshed.")
            return "Data refreshed successfully."  # Success message
        else:
            return "Error: Failed to refresh data."  # Error message


def select_pipes_for_calculation(pipe_data):
    """Allow users to select saved pipes and output their data for external calculations."""
    # Get a list of all saved pipe names
    pipe_names = [name for name, details in pipe_data.items() if details.get("length", 0) > 0]

    # Create a dropdown menu for selecting pipes
    selected_pipes = st.multiselect(
        label="",
        options=pipe_names,
        help="Choose the pipes you want to use for piping cost calculations."
    )

    # Fetch and display data for selected pipes
    if selected_pipes:
        selected_data = {name: pipe_data[name] for name in selected_pipes}
        #st.write("Selected Pipes Data:")
        #st.json(selected_data)  # Display as JSON for easy readability
        
        # Prepare data for external use
        return selected_data
    else:
        st.info("No pipes selected.")
        return {}
        
def add_landmarks_to_pipes(pipe_data, landmarks):
    """Update each pipe in pipe_data with its associated landmarks."""
    for name, details in pipe_data.items():
        if "length" in details and details["length"] > 0:
            # Pipes: Associate landmarks with start and end coordinates
            start_coord = details["coordinates"][0]
            end_coord = details["coordinates"][-1]
            start_landmark = find_closest_landmark(start_coord, landmarks)
            end_landmark = find_closest_landmark(end_coord, landmarks)
            
            # Add associated landmarks to pipe details
            details["start_landmark"] = start_landmark
            details["end_landmark"] = end_landmark
    return pipe_data  # Return the updated data


def main_storage():
    """Main function to run the Pipe Storage System app."""
    # Load existing pipe data
    pipe_data = load_data()

    #st.title("Pipe and Landmark Storage System")
    #st.subheader("Store and View Pipe and Landmark Details")

    # Fetch and integrate API data
    landmarks = fetch_and_integrate_data(pipe_data)

    # Add landmarks to storage
    pipe_data = add_landmarks_to_storage(pipe_data, landmarks)

    # Associate landmarks with pipes and update pipe data
    pipe_data = add_landmarks_to_pipes(pipe_data, landmarks)

    # Save updated storage
    if not save_data(pipe_data):
        st.error("Failed to save updated storage.")

    # Display stored pipes and landmarks
    st.header("Stored Pipes and Landmarks")
    if pipe_data:
        display_data_table(pipe_data, landmarks)
        #add_download_button(df)
        handle_delete_entry(pipe_data)
    else:
        st.info("No data stored yet. Add pipes or landmarks to get started.")

    # Add pipe selection functionality
    st.header("Select Pipes for Cost Calculation")
    selected_pipes = select_pipes_for_calculation(pipe_data)

    # Refresh data
    refresh_status = refresh_data(pipe_data)
    if refresh_status:
        st.info(refresh_status)

    # (Optional) Output selected pipes for further use
    if selected_pipes:
        st.success("Selected pipes ready for cost calculations.")
    
    return selected_pipes

############## Pipe_main ###############

def initialize_processed_data_file():
    """Ensure the processed data file exists, creating it if necessary."""
    if not os.path.exists(PROCESSED_DATA_FILE):
        try:
            with open(PROCESSED_DATA_FILE, "w") as file:
                json.dump({}, file)  # Create an empty JSON object
            st.info(f"Processed data file ({PROCESSED_DATA_FILE}) created.")
        except Exception as e:
            st.error(f"Failed to create processed data file: {e}")



def load_processed_data():
    """Load processed pipe data from the JSON file."""
    if os.path.exists(PROCESSED_DATA_FILE):
        try:
            with open(PROCESSED_DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.warning("Error decoding processed pipe data. Starting with empty data.")
            return {}
    return {}
    

def save_processed_data(data):
    """Save processed pipe data to a JSON file."""
    try:
        with open(PROCESSED_DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
        st.success(f"Processed data saved successfully to {PROCESSED_DATA_FILE}!")
    except Exception as e:
        st.error(f"Failed to save processed data: {e}")




def handle_delete_processed_data():
    """Allow the user to delete an entry from the processed JSON file."""
    st.header("Delete items in Processed Pipe ")

    # Load existing data
    try:
        with open(PROCESSED_DATA_FILE, "r") as f:
            processed_data = json.load(f)
    except FileNotFoundError:
        st.info(f"No processed data file ({PROCESSED_DATA_FILE}) found.")
        return

    # Check if data is empty
    if not processed_data:
        st.warning("No data available to delete.")
        return

    # Get a list of all pipe names from processed data
    processed_pipe_names = list(processed_data.keys())

    # Dropdown for selecting an entry to delete
    selected_entry = st.selectbox(
        "Select a Pipe in the Processed Pipe Data Table to delete",
        options=["Select an entry"] + processed_pipe_names,  # Add a placeholder option
        help="Choose a processed pipe entry to delete."
    )

    # Handle deletion after a valid selection
    if selected_entry != "Select an entry":
        # Add confirmation button for deletion
        if st.button(f"Confirm Deletion of '{selected_entry}'"):
            # Check if selected entry exists in the data
            if selected_entry in processed_data:
                try:
                    # Delete the selected entry
                    del processed_data[selected_entry]
                    
                    # Save the updated data to the processed JSON file
                    with open(PROCESSED_DATA_FILE, "w") as f:
                        json.dump(processed_data, f, indent=4)
                    
                    # Show success message
                    st.success(f"Processed entry '{selected_entry}' deleted successfully!")
                    st.rerun()  # Reload the page to reflect the change
                except Exception as e:
                    st.error(f"Failed to delete entry '{selected_entry}': {e}")
            else:
                st.warning(f"Entry '{selected_entry}' does not exist.")



def display_processed_data_table():
    """
    Display the contents of the processed JSON file as a table with added fields and expandable details.
    """
    st.header("Processed Pipe Data Table")

    try:
        # Load the JSON file
        with open(PROCESSED_DATA_FILE, "r") as file:
            processed_data = json.load(file)

        # Check if data is empty
        if not processed_data:
            st.warning("No processed pipe data available.")
            return

        # Prepare the data for display
        table_data = [
            {
                "Pipe Name": pipe_name,
                "Length (m)": details["Length"],
                "Material": details["Material"],
                "Medium": details["Medium"],
                "Pressure": details["Pressure"],
                "Temperature": details["Temperature"],
                "Start Landmark": details["Start Landmark"],
                "Start Coordinates": details["Start Coordinates"],
                "End Landmark": details["End Landmark"],
                "End Coordinates": details["End Coordinates"],
            }
            for pipe_name, details in processed_data.items()
        ]

        # Convert to DataFrame for display
        df = pd.DataFrame(table_data)

        # Display the table for all main details
        st.table(df)

        # Add expandable sections for detailed "Pipe Data"
        for index, row in df.iterrows():
            with st.expander(f"{row['Pipe Name']} (Details)"):
                st.write(f"**Length:** {row['Length (m)']} meters")
                st.write(f"**Material:** {row['Material']}")
                st.write(f"**Medium:** {row['Medium']}")
                st.write(f"**Pressure:** {row['Pressure']} bar")
                st.write(f"**Temperature:** {row['Temperature']} °C")
                st.write(f"**Start Landmark:** {row['Start Landmark']}")
                st.write(f"**Start Coordinates:** {row['Start Coordinates']}")
                st.write(f"**End Landmark:** {row['End Landmark']}")
                st.write(f"**End Coordinates:** {row['End Coordinates']}")
                # Keep the JSON display for detailed pipe data
                st.json(processed_data[row['Pipe Name']]["Pipe Data"])

    except FileNotFoundError:
        st.warning(f"No processed data file ({PROCESSED_DATA_FILE}) found.")
    except json.JSONDecodeError as e:
        st.error(f"Error decoding JSON: {e}")





def pipe_main(selected_pipes):
    """
    Pipe Selection Tool: Process user-selected pipes, calculate critical data,
    and save to the processed storage file.
    """
    st.title("Pipe Selection Tool")

    # Load existing processed data
    processed_pipes = load_processed_data()

    # User inputs for pressure, temperature, and medium
    pressure, temperature, medium = get_user_inputs1()

    if not selected_pipes:
        st.warning("No pipes selected. Please select pipes to proceed.")
        return

    # Handle the "Get Piping Info" button
    if st.button("Get Piping Info"):
        # Process each selected pipe
        for pipe_name, pipe_details in selected_pipes.items():
            st.markdown(f"### Processing {pipe_name}")

            # Display pipe details
            st.markdown(f"**Length:** {pipe_details['length']} meters")
            st.markdown(f"**Coordinates:** {pipe_details['coordinates']}")

            # Include landmarks
            start_landmark = pipe_details.get("start_landmark", "Unknown")
            end_landmark = pipe_details.get("end_landmark", "Unknown")
            st.markdown(f"**Start Landmark:** {start_landmark}")
            st.markdown(f"**Start Coordinates:** {pipe_details['coordinates'][0] if pipe_details['coordinates'] else 'N/A'}")
            st.markdown(f"**End Landmark:** {end_landmark}")
            st.markdown(f"**End Coordinates:** {pipe_details['coordinates'][-1] if pipe_details['coordinates'] else 'N/A'}")

            # Determine pipe material
            pipe_material = choose_pipe_material(pressure, temperature, medium)
            st.markdown(f"**Selected Pipe Material:** {pipe_material}")

            # Call Pipe_finder to get relevant data
            pipe_data = Pipe_finder(pipe_material, pressure, pipe_details['length'])
            if not pipe_data:
                st.warning(f"No data found for {pipe_name}. Skipping...")
                continue

            # Consolidate all data
            processed_pipes[pipe_name] = {
                "Length": pipe_details["length"],
                "Coordinates": pipe_details["coordinates"],
                "Start Landmark": start_landmark,
                "Start Coordinates": pipe_details["coordinates"][0] if pipe_details["coordinates"] else None,
                "End Landmark": end_landmark,
                "End Coordinates": pipe_details["coordinates"][-1] if pipe_details["coordinates"] else None,
                "Pressure": pressure,
                "Temperature": temperature,
                "Medium": medium,
                "Material": pipe_material,
                "Pipe Data": pipe_data,  # Contains all the filtered options
            }

        # Save updated processed data
        save_processed_data(processed_pipes)


        # Display summary table
        st.markdown("### Processed Pipe Data Summary")
        display_processed_data_table()
        
        st.rerun()






        

def reset_view_state():
    """Reset the view state to go back to processing view."""
    if 'show_processed_data' in st.session_state:
        del st.session_state['show_processed_data']
        
def main():
    """Main function to handle storage and processed data display."""

    # Ensure the processed data file is initialized
    initialize_processed_data_file()

    # Display the Processed Pipe Data Table at the beginning
    display_processed_data_table()

    # Add functionality to delete entries from the Processed Pipe Data Table
    handle_delete_processed_data()

    # Rest of the app logic (e.g., selecting pipes, assigning inputs)
    #st.subheader("Select and Process Pipes")
    selected_pipes = main_storage()
    if selected_pipes:
        pipe_main(selected_pipes)



main()
