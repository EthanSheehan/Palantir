export default function App() {
  return (
    <div style={{ display: 'flex', flexDirection: 'row', height: '100vh', overflow: 'hidden' }}>
      <div style={{ width: 300, flexShrink: 0, background: '#252a31' }}>
        {/* Sidebar placeholder */}
      </div>
      <div style={{ flex: 1, minWidth: 0, position: 'relative', background: '#1c2127' }}>
        {/* CesiumContainer placeholder */}
      </div>
    </div>
  );
}
