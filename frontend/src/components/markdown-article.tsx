import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownArticle({ children }: { children: string }) {
  return (
    <article className="markdown overflow-x-auto text-foreground/85">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ a: (props) => <a {...props} target="_blank" rel="noreferrer" /> }}
      >
        {children}
      </ReactMarkdown>
    </article>
  );
}
