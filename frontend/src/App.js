// App.js
import React from 'react';
import MapComponent from './components/MapComponent';
import FetchMap from './components/FetchMap';
import Header from './components/Header'; // Import the Header component
import './styles/Sidebar.css'; // Import the global CSS

// Your province and soum JSON data
import provinceData from './assets/soum_province_names.json';

function App() {
  return (
    <div>
      <Header /> {/* Add the Header component */}
      <div className="main-container">
        <FetchMap provinceData={provinceData} />
        <MapComponent />
      </div>
    </div>
  );
}

export default App;