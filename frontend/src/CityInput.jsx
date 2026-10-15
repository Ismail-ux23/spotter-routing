import React, { useEffect, useRef, useState } from "react";

export default function CityInput({ label, name, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [message, setMessage] = useState("");
  const [active, setActive] = useState(-1);
  const version = useRef(0);
  const id = `${name}-suggestions`;
  useEffect(() => {
    const current = ++version.current;
    const controller = new AbortController();
    setItems([]);
    setActive(-1);
    if (!open) return;
    if (value.trim().length < 2) {
      setMessage("Type at least 2 letters to search cities.");
      return;
    }
    setMessage("Searching cities...");
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/cities?q=${encodeURIComponent(value.trim())}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw Error();
        const data = await response.json();
        if (current !== version.current) return;
        setItems(data.cities);
        setMessage(
          data.cities.length ? "" : "No matching cities. Try a different name.",
        );
      } catch (error) {
        if (error.name !== "AbortError" && current === version.current)
          setMessage(
            "Suggestions unavailable. You can still type a city name.",
          );
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, open]);
  const select = (city) => {
    ++version.current;
    onChange(city.name, city);
    setOpen(false);
  };
  return (
    <div
      className="city-field"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
    >
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        name={name}
        value={value}
        required
        autoComplete="off"
        placeholder="City or town"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={id}
        aria-activedescendant={
          open && active >= 0 ? `${id}-${active}` : undefined
        }
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setOpen(true);
          onChange(e.target.value, null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            setOpen(false);
          }
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            setActive((i) =>
              items.length
                ? (i + (e.key === "ArrowDown" ? 1 : -1) + items.length) %
                  items.length
                : -1,
            );
          }
          if (e.key === "Enter" && open && active >= 0 && items[active]) {
            e.preventDefault();
            select(items[active]);
          }
        }}
      />
      {open && (
        <div className="city-menu">
          <ul id={id} role="listbox" aria-label={`${label} suggestions`}>
            {items.map((city, i) => (
              <li
                key={`${city.lat},${city.lon},${i}`}
                id={`${id}-${i}`}
                role="option"
                aria-selected={i === active}
                className={i === active ? "active" : ""}
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => select(city)}
              >
                {city.name}
              </li>
            ))}
          </ul>
          {message && <p role="status">{message}</p>}
        </div>
      )}
    </div>
  );
}
