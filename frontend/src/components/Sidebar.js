import React, { useState, useEffect } from 'react';
import Dropdown from './Dropdown';
import '../styles/App.css'; // Optional CSS for styling the dropdowns

const PastureOnlyCheckbox = () => {
    return (
      <div className="checkbox-container">
        <label>
          <input type="checkbox" className="checkbox-input" />
          Grazing Only
        </label>
      </div>
    );
  };


const Sidebar = ({ provinceData }) => {
  const provinces = Object.keys(provinceData);
  const [expanded, setExpanded] = useState(true);
  const [selectedProvince, setSelectedProvince] = useState(provinces[0]);
  const [selectedSoum, setSelectedSoum] = useState(provinceData[provinces[0]]);
  const vegetationIndices = ["NDVI", "EVI", "SAVI", /* ... */];
  const years = ["2023", "2022", "2021", "2020", "2019", "2018", "2017"];

  const handleToggleExpand = () => {
    setExpanded((prevExpanded) => !prevExpanded);
  };

  const handleProvinceChange = (selectedProvince) => {
    setSelectedProvince(selectedProvince);
    setSelectedSoum(provinceData[selectedProvince]);
  };

  const handleSoumChange = (selectedSoum) => {
    // Handle the selected soum here or pass the value to any parent component
    console.log(selectedSoum);
  };

  return (
    <div className={`sidebar ${expanded ? 'expanded' : ''}`}>
      <button onClick={handleToggleExpand}>
        {expanded ? 'Hide Sidebar' : 'Expand Sidebar'}
      </button>
      {expanded && (
        <>
          <div className="region-select">
            <h4>Select Region</h4>
            <Dropdown options={provinces} onSelect={handleProvinceChange} />
          </div>

          <div className="region-select">
            <h4>Select Soum</h4>
            <Dropdown options={selectedSoum} onSelect={handleSoumChange} />
          </div>

          <div className="region-select">
            <h4>Select Indicators</h4>
            <Dropdown options={vegetationIndices} />
          </div>

          <div className="region-select">
            <h4>Select Year</h4>
            <Dropdown options={years} />
          </div>

          <div className="region-select">
            <h4>Select Grazing</h4>
            <PastureOnlyCheckbox />
          </div>
          {/* Add other components or content as needed */}
        </>
      )}
    </div>
  );
};

export default Sidebar;