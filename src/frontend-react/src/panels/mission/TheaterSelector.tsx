import React, { useEffect, useState } from 'react';
import { HTMLSelect } from '@blueprintjs/core';
import { fetchTheaters, switchTheater } from '../../shared/api';

export function TheaterSelector() {
  const [theaters, setTheaters] = useState<string[]>(['romania']);
  const [selected, setSelected] = useState('romania');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchTheaters()
      .then(setTheaters)
      .catch(() => setTheaters(['romania']));
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    const previous = selected;
    setSelected(value);
    setLoading(true);
    switchTheater(value)
      .catch((err) => {
        console.error(err);
        setSelected(previous);
      })
      .finally(() => setLoading(false));
  }

  function formatName(name: string) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  return (
    <div>
      <HTMLSelect
        value={selected}
        onChange={handleChange}
        iconName="caret-down"
        fill
        disabled={loading}
        options={theaters.map(t => ({ value: t, label: formatName(t) }))}
      />
    </div>
  );
}
