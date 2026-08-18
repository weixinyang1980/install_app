/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        stall: "#0E2A3A",
        chili: "#E23D28",
        paper: "#F5E6C8",
        lantern: "#FF8A3D",
        nori: "#1F6F4A",
        milk: "#FFFAF3",
        ink: "#1A120C",
        ticket: "#FFF4D6",
      },
      fontFamily: {
        display: ['"Fredoka"', '"ZCOOL KuaiLe"', '"Noto Sans SC"', "sans-serif"],
        sans: ['"Noto Sans SC"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        stamp: "4px 4px 0 0 #1A120C",
        shelf: "0 18px 0 -8px #0A1C26, 0 28px 40px rgba(0,0,0,.35)",
      },
    },
  },
  plugins: [],
};
