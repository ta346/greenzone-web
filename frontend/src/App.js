import React from 'react';
import MapComponent from './components/MapComponent';
import Sidebar from './components/Sidebar';
import './styles/App.css';

function App() {
  return (
    <div className="app-container">
      <h1>Mongolian Rangeland Monitoring Platform</h1>
      <div className="main-container">
        <Sidebar />
        <MapComponent />
      </div>
    </div>
  );
}

export default App;
