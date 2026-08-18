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
      },
      fontFamily: {
        display: ['"Fredoka"', '"Noto Sans SC"', "sans-serif"],
        sans: ['"Noto Sans SC"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
