// Header.js
import React from 'react';
import logo from '../assets/logo.png'; // Replace with your logo image file
import '../styles/Header.css'; // Optional CSS for styling the header

const Header = () => {
    return (
        <header className="header">
          <div className="banner">
            <img src={logo} alt="Logo" className="logo" />
            <h1>Mongolian Rangeland Monitoring</h1>
          </div>
          <nav className="navigation">
            <ul>
              <li><a href="#home">Home</a></li>
              <li><a href="#degradation">Degradation Management</a></li>
              {/* Add more navigation links as needed */}
            </ul>
          </nav>
        </header>
      );
};

export default Header;