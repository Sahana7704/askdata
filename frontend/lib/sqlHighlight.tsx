import React from "react";

const KEYWORDS = new Set(
  ("select from where group by order having limit offset join inner left right full outer cross on as and or not in is null like ilike " +
    "between case when then else end union all distinct with over partition asc desc exists filter using true false interval cast extract").split(" "),
);

// Minimal SQL tokenizer for display only: comments, strings, numbers, keywords, functions.
export function highlightSql(sql: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /(--[^\n]*)|('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)(\s*\()?|([\s\S])/g;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(sql))) {
    const [full, comment, str, num, word, paren] = m;
    const key = i++;
    if (comment) out.push(<span key={key} className="text-[#7d8590] italic">{full}</span>);
    else if (str) out.push(<span key={key} className="text-[#6cc28a]">{full}</span>);
    else if (num) out.push(<span key={key} className="text-[#6cc28a]">{full}</span>);
    else if (word) {
      if (paren && !KEYWORDS.has(word.toLowerCase())) {
        out.push(<span key={key}><span className="text-[#e3a857]">{word}</span>{paren}</span>);
      } else if (KEYWORDS.has(word.toLowerCase())) {
        out.push(<span key={key}><span className="text-[#5b9cf0] font-medium">{word}</span>{paren ?? ""}</span>);
      } else out.push(<span key={key}>{full}</span>);
    } else out.push(<span key={key}>{full}</span>);
  }
  return out;
}
