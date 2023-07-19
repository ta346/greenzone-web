import React, { useState } from 'react';
import '../styles/Sidebar.css'; // Optional CSS for styling the dropdowns

const Dropdown = ({ options, onSelect }) => {
  const [selectedOption, setSelectedOption] = useState(options[0]);

  const handleChange = (event) => {
    setSelectedOption(event.target.value);
    onSelect(event.target.value); // Call the onSelect function with the selected value
  };

  return (
    <div className="dropdown-container">
      <select className="dropdown-select" value={selectedOption} onChange={handleChange}>
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
