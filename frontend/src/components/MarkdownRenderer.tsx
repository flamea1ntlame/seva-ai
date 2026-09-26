import React from "react";

/**
 * A tiny, safe, zero-dependency Markdown renderer for AI assistant messages.
 * Avoids dangerouslySetInnerHTML entirely.
 */

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  // Split content into blocks (paragraphs, lists) by double newlines
  const blocks = content.split(/\n{2,}/);

  return (
    <div className="space-y-3.5 text-[13px] leading-relaxed">
      {blocks.map((block, i) => (
        <MarkdownBlock key={i} text={block} />
      ))}
    </div>
  );
}

function MarkdownBlock({ text }: { text: string }) {
  // Check if this block is a list (every line starts with - or *)
  const lines = text.split('\n').filter(l => l.trim() !== '');
  if (lines.length === 0) return null;

  const isBulletList = lines.every(line => line.trim().startsWith('- ') || line.trim().startsWith('* '));
  const isNumberedList = lines.every(line => /^\d+\.\s/.test(line.trim()));

  if (isBulletList || isNumberedList) {
    return (
      <ul className="space-y-1.5 pl-0.5">
        {lines.map((line, i) => {
          const cleanedLine = line.replace(/^[-*]\s|^\d+\.\s/, '');
          return (
            <li key={i} className="flex items-start space-x-2.5">
              <span className="text-brand-500 font-bold mt-[1px] shrink-0">
                {isNumberedList ? `${i + 1}.` : '•'}
              </span>
              <span className="text-brand-900 leading-snug">
                {parseInline(cleanedLine)}
              </span>
            </li>
          );
        })}
      </ul>
    );
  }

  // Handle Headings (single line block starting with #)
  if (lines.length === 1 && lines[0].trim().startsWith('#')) {
    const trimmed = lines[0].trim();
    const headingLevel = trimmed.match(/^#+/)?.[0].length || 1;
    const content = trimmed.replace(/^#+\s/, '');
    
    if (headingLevel === 1) return <h1 className="text-lg font-extrabold text-brand-900 mt-3 mb-1">{parseInline(content)}</h1>;
    if (headingLevel === 2) return <h2 className="text-base font-bold text-brand-900 mt-2 mb-1">{parseInline(content)}</h2>;
    return <h3 className="text-sm font-bold text-brand-900 mt-1 mb-1 tracking-wide">{parseInline(content)}</h3>;
  }

  // Regular paragraph with soft line breaks
  return (
    <div className="text-brand-800">
      {lines.map((line, i) => (
        <React.Fragment key={i}>
          {parseInline(line)}
          {i < lines.length - 1 && <br />}
        </React.Fragment>
      ))}
    </div>
  );
}

function parseInline(text: string) {
  // Split by bold (**), italic (*), code (`), and links ([text](url))
  // The regex captures the entire matched token to process it.
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/g);
  
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-brand-900">{parseInline(part.slice(2, -2))}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="italic text-brand-800">{parseInline(part.slice(1, -1))}</em>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="bg-brand-100/70 border border-brand-200 text-brand-800 px-1.5 py-0.5 rounded-md text-[11px] font-mono whitespace-pre-wrap">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('[') && part.endsWith(')')) {
      const match = part.match(/\[(.*?)\]\((.*?)\)/);
      if (match) {
        return (
          <a 
            key={i} 
            href={match[2]} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="text-primary-600 hover:text-primary-800 font-medium underline underline-offset-2 transition-colors"
          >
            {match[1]}
          </a>
        );
      }
    }
    // Emojis and regular text are preserved naturally
    return part;
  });
}
