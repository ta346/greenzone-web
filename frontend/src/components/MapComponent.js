import React from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const MapComponent = () => {
  return (
    <MapContainer center={[46.8625, 103.8467]} zoom={5} style={{ width: '100%', height: '650px' }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="Map data © OpenStreetMap contributors"
      />
      {/* You can add layers here from the back end */}
    </MapContainer>
  );
};

export default MapComponent;
