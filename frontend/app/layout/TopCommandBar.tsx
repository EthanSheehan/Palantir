import { useEffect, useRef } from 'react';
import { Navbar, NavbarGroup, NavbarHeading, NavbarDivider } from '@blueprintjs/core';

/**
 * Top toolbar bar — app title + tool palette.
 * Adopts tool buttons created by legacy MapToolController.
 */
export function TopCommandBar() {
  const paletteRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!paletteRef.current) return;

    // Find the temporary palette created by app.js for MapToolController
    const tempPalette = document.getElementById('ws-tool-palette');
    if (tempPalette && tempPalette !== paletteRef.current) {
      // Move all child buttons to our React-managed palette
      while (tempPalette.firstChild) {
        paletteRef.current.appendChild(tempPalette.firstChild);
      }
      // Remove the temp palette and take its ID
      tempPalette.remove();
    }

    paletteRef.current.id = 'ws-tool-palette';
  }, []);

  return (
    <Navbar className="ws-top-bar" fixedToTop={false}>
      <NavbarGroup>
        <NavbarHeading className="ws-app-title">System Dashboard</NavbarHeading>
        <NavbarDivider />
        <div ref={paletteRef} className="ws-tool-palette" />
      </NavbarGroup>
    </Navbar>
  );
}
