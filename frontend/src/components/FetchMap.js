// FetchMap.js
import React, { useState } from 'react';
import SidebarForm from './SidebarForm';
import MapComponent from './MapComponent';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';

const FetchMap = ({ provinceData }) => {
  const [geoJSONData, setGeoJSONData] = useState(null);

  const fetchGeoJSONData = (data) => {
    axios
      .post('http://127.0.0.1:5000/api/fetch_anomaly_map_data', data)
      .then((response) => {
        console.log(response.data);
        setGeoJSONData(response.data);
      })
      .catch((error) => {
        console.error('Error making API request:', error);
      });
  };

  return (
    <><div>
      <SidebarForm provinceData={provinceData} onApplyLayer={fetchGeoJSONData} />
    </div><div className='map-container'>
        <MapComponent geoJSONData={geoJSONData} />
      </div></>
  );
};

export default FetchMap;
