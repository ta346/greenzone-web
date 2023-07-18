import React, { useState } from 'react';
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

const Sidebar = () => {
  // Replace the options with your actual data from the back end
  const provinces = ["Province 1", "Province 2", "Province 3", /* ... */];
  const soums = ["Soum 1", "Soum 2", "Soum 3", /* ... */];
  const vegetationIndices = ["NDVI", "EVI", "SAVI", /* ... */];
  const years = ["2023", "2022", "2021", "2020", "2019", "2018", "2017"];

  const [expanded, setExpanded] = useState(true);

  const handleToggleExpand = () => {
    setExpanded(!expanded);
  };

  return (
    <div className={`sidebar ${expanded ? 'expanded' : ''}`}>
      <button onClick={handleToggleExpand}>
        {expanded ? 'Hide Sidebar' : 'Expand Sidebar'}
      </button>
      {expanded && (
        <>
          <div className="region-select">
            <h3>Select Region</h3>
            <Dropdown options={provinces} />
            <Dropdown options={soums} />
          </div>
          <Dropdown options={vegetationIndices} />
          <Dropdown options={years} />
          <PastureOnlyCheckbox /> {/* Nested component */}
          {/* Add other components or content as needed */}
        </>
      )}
    </div>
  );
};

export default Sidebar;
