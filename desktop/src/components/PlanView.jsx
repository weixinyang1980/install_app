import { useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, ChevronDown, ChevronRight, Copy } from "lucide-react";
import "highlight.js/styles/atom-one-dark.css";

function extractText(node) {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node?.props?.children) return extractText(node.props.children);
  return "";
}

function CodeBlock({ children }) {
  const [copied, setCopied] = useState(false);
  const text = extractText(children).replace(/\n$/, "");
  return (
    <div className="relative group">
      <button
        type="button"
        className="absolute right-3 top-3 z-10 rounded-full bg-lantern px-3 py-1 text-xs font-bold text-ink shadow-stamp"
        onClick={async () => {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        }}
      >
        {copied ? (
          <span className="inline-flex items-center gap-1">
            <Check size={12} /> 抄走了
          </span>
        ) : (
          <span className="inline-flex items-center gap-1">
            <Copy size={12} /> 抄脚本
          </span>
        )}
      </button>
      <pre>{children}</pre>
    </div>
  );
}

export default function PlanView({ plan }) {
  const [open, setOpen] = useState(false);
  const md = plan?.markdown || "";
  const components = useMemo(
    () => ({
      pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
    }),
    [],
  );
  if (!plan) return null;
  return (
    <article className="receipt rounded-sm px-6 py-3 shadow-shelf">
      <button type="button" className="flex w-full items-center justify-between gap-3 text-left" onClick={() => setOpen((v) => !v)}>
        <div>
          <p className="font-display text-xs tracking-widest text-chili">装了吗 · 热敏小票</p>
          <h2 className="font-display text-xl font-bold">
            {plan.software?.name} · {plan.version}
          </h2>
          <p className="font-mono text-[11px] opacity-70">
            #{plan.id} / {plan.platform} / {plan.source}
            {open ? "" : " · 脚本已收起"}
          </p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full border-2 border-ink bg-lantern px-3 py-1 text-xs font-bold">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {open ? "收起脚本" : "展开脚本"}
        </span>
      </button>
      {open ? (
        <div className="markdown-body mt-3 max-h-[40vh] space-y-3 overflow-auto border-t border-dashed border-ink/30 pt-3 text-sm leading-7">
          <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} components={components}>
            {md}
          </Markdown>
        </div>
      ) : null}
    </article>
  );
}
