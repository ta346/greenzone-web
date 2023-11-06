// import React, { useEffect } from 'react';
// import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
// import 'leaflet/dist/leaflet.css';

// const MapComponent = ({ geoJSONData }) => {
//   useEffect(() => {
//     // You can handle any map-related setup or interactions here
//   }, []);

//   return (
//     <MapContainer center={[46.8625, 103.8467]} zoom={5} style={{ width: '100%', height: '650px' }}>
//       <TileLayer
//         url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
//         attribution="Map data © OpenStreetMap contributors"
//       />

//       {/* Add a GeoJSON layer if GeoJSON data is available */}
//       {geoJSONData && (
//         <GeoJSON data={geoJSONData} />
//       )}
//     </MapContainer>
//   );
// };

// export default MapComponent;

import React from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const MapComponent = ({ geoJSONData }) => {
  // Generate a unique key whenever the geoJSONData changes
  const mapKey = geoJSONData ? JSON.stringify(geoJSONData) : null;

  return (
    <div className="map-container">
      <MapContainer
        center={[46.8625, 103.8467]}
        zoom={5}
        style={{ width: '100%', height: '650px' }}
        key={mapKey} // Use the mapKey as the key
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="Map data © OpenStreetMap contributors"
        />
        {/* Render the GeoJSON layer using the provided geoJSONData prop */}
        {geoJSONData && <GeoJSON data={geoJSONData.features} />}
      </MapContainer>
    </div>
  );
};

export default MapComponent;

