import React from 'react';
import '../styles/App.css'; // Optional CSS for styling the dropdowns

const Dropdown = ({ options }) => {
  return (
    <div className="dropdown-container">
      <select className="dropdown-select">
        {options.map((option, index) => (
          <option key={index} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
};

export default Dropdown;
