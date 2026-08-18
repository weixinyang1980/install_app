import { clsx } from "clsx";

export function cn(...inputs) {
  return clsx(inputs);
}

export const PLATFORM_LABEL = {
  windows: "Windows",
  macos: "macOS",
  linux: "Linux",
};

export const KIND_FLAVOR = {
  runtime: { tag: "汽水", color: "bg-sky-300" },
  tool: { tag: "干脆面", color: "bg-amber-300" },
  database: { tag: "辣条", color: "bg-red-300" },
  ide: { tag: "冰棍", color: "bg-violet-300" },
  server: { tag: "关东煮", color: "bg-orange-300" },
  library: { tag: "口香糖", color: "bg-lime-300" },
  other: { tag: "神秘包装", color: "bg-pink-300" },
};
