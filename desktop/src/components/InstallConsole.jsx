import { useEffect, useRef } from "react";
import { Square, Terminal } from "lucide-react";

export default function InstallConsole({ lines, running, onAbort }) {
  const boxRef = useRef(null);

  useEffect(() => {
    if (!running || !boxRef.current) return;
    boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [lines, running]);

  return (
    <section className="overflow-hidden rounded-2xl border-2 border-ink bg-[#07151c] shadow-stamp">
      <header className="flex items-center justify-between bg-nori px-4 py-2 text-milk">
        <p className="inline-flex items-center gap-2 font-display text-sm">
          <Terminal size={16} /> 后厨监视器
        </p>
        {running ? (
          <button type="button" className="inline-flex items-center gap-1 rounded-full bg-chili px-3 py-1 text-xs font-bold" onClick={onAbort}>
            <Square size={10} /> 停手
          </button>
        ) : (
          <span className="text-xs opacity-80">空闲</span>
        )}
      </header>
      <div ref={boxRef} className="max-h-64 overflow-auto p-3 font-mono text-[12px] leading-5">
        {lines.length === 0 ? (
          <p className="text-paper/50">还没开火。点「一键安装」后，日志会一行行冒出来。</p>
        ) : (
          lines.map((line, i) => (
            <p
              key={i}
              className={
                "console-line " +
                (line.type === "stderr" ? "text-chili" : line.type === "system" ? "text-lantern" : "text-paper")
              }
            >
              {line.text}
            </p>
          ))
        )}
      </div>
    </section>
  );
}
