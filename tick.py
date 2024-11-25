import streamlit as st

# Example data for demonstration (replace with your API data fetching logic)
landmarks = [
    {"name": "Landmark 1", "coordinates": [52.3676, 4.9041]},
    {"name": "Landmark 2", "coordinates": [52.3769, 4.9004]}
]

pipes = [
    {"name": "Pipe 1", "distance": 100.5, "coordinates": [[52.3676, 4.9041], [52.3769, 4.9004]]},
    {"name": "Pipe 2", "distance": 250.0, "coordinates": [[52.3769, 4.9004], [52.3879, 4.8995]]}
]

polygons = [
    {"name": "Polygon 1", "dimensions": {"width": 50, "height": 30}},
    {"name": "Polygon 2", "dimensions": {"width": 70, "height": 40}}
]

# Sidebar: Selection of feature type
st.sidebar.title("Feature Selector")
feature_type = st.sidebar.radio(
    "Select the feature type to interact with:",
    ["Landmarks", "Pipes", "Polygons"]
)

# Display data dynamically based on selection
if feature_type == "Landmarks":
    st.title("Landmark Selection")
    selected_landmarks = []
    for landmark in landmarks:
        if st.checkbox(f"{landmark['name']} ({landmark['coordinates']})"):
            selected_landmarks.append(landmark)
    
    if selected_landmarks:
        st.subheader("Selected Landmarks")
        for landmark in selected_landmarks:
            st.markdown(f"- **Name**: {landmark['name']}")
            st.markdown(f"  **Coordinates**: {landmark['coordinates']}")
    else:
        st.info("No landmarks selected.")

elif feature_type == "Pipes":
    st.title("Pipe Selection")
    selected_pipes = []
    for pipe in pipes:
        if st.checkbox(f"{pipe['name']} - {pipe['distance']} meters"):
            selected_pipes.append(pipe)
    
    if selected_pipes:
        st.subheader("Selected Pipes")
        for pipe in selected_pipes:
            st.markdown(f"- **Name**: {pipe['name']}")
            st.markdown(f"  **Distance**: {pipe['distance']} meters")
            st.markdown(f"  **Coordinates**: {pipe['coordinates']}")
    else:
        st.info("No pipes selected.")

elif feature_type == "Polygons":
    st.title("Polygon Selection")
    selected_polygons = []
    for polygon in polygons:
        if st.checkbox(f"{polygon['name']} - {polygon['dimensions']['width']}x{polygon['dimensions']['height']} meters"):
            selected_polygons.append(polygon)
    
    if selected_polygons:
        st.subheader("Selected Polygons")
        for polygon in selected_polygons:
            st.markdown(f"- **Name**: {polygon['name']}")
            st.markdown(f"  **Dimensions**: {polygon['dimensions']['width']}x{polygon['dimensions']['height']} meters")
    else:
        st.info("No polygons selected.")
