/**
 * Navigation Bar Component
 * Path: wealthineers/src/app/components/Navbar.jsx
 */

'use client';

import Link from 'next/link';
import { useState } from 'react';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav style={styles.navbar}>
      <div style={styles.container}>
        {/* Logo */}
        <Link href="/" style={styles.logo}>
          <h1 style={{ margin: 0 }}>Wealthineers</h1>
        </Link>

        {/* Hamburger Menu Icon (Mobile) */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          style={styles.hamburger}
        >
          ☰
        </button>

        {/* Navigation Links */}
        <div style={{
          ...styles.navLinks,
          display: isOpen ? 'flex' : 'none',
        }}>
          <Link href="/" style={styles.link}>
            Home
          </Link>
          <Link href="/dashboard" style={styles.link}>
            📊 Dashboard
          </Link>
          <Link href="/login" style={styles.link}>
            Login
          </Link>
          <Link href="/signup" style={styles.link}>
            Sign Up
          </Link>
        </div>
      </div>
    </nav>
  );
}

const styles = {
  navbar: {
    backgroundColor: '#1a1a1a',
    padding: '1rem 0',
    position: 'sticky',
    top: 0,
    zIndex: 1000,
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
  },
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '0 2rem',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logo: {
    textDecoration: 'none',
    color: '#05bfdb',
    fontSize: '1.5rem',
    fontWeight: 'bold',
  },
  navLinks: {
    display: 'flex',
    gap: '2rem',
    alignItems: 'center',
    width: '100%',
    justifyContent: 'flex-end',
  },
  link: {
    color: '#ffffff',
    textDecoration: 'none',
    fontSize: '1rem',
    padding: '0.5rem 1rem',
    cursor: 'pointer',
  },
  hamburger: {
    display: 'none',
    cursor: 'pointer',
    backgroundColor: 'transparent',
    border: 'none',
    color: '#05bfdb',
    fontSize: '1.5rem',
  },
};
