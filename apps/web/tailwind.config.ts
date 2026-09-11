import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forge: {
          base: "#3B3939",
          panel: "#262B3D",
          border: "#74638A",
          text: "#FFF7ED",
          muted: "#D8C5D0",
          accent: "#7DD3FC",
          highlight: "#F9C784",
        },
      },
    },
  },
  plugins: [],
};

export default config;
