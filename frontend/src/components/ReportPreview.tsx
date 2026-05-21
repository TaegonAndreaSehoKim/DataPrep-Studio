type MarkdownBlock =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "code"; language: string; text: string }
  | { type: "table"; rows: string[][] };

interface ReportSection {
  title: string;
  blocks: MarkdownBlock[];
}

function trimInlineCode(value: string) {
  return value.replace(/`([^`]+)`/g, "$1");
}

function parseTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => trimInlineCode(cell.trim()));
}

function isTableDivider(line: string) {
  return /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
}

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const lines = markdown.split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const codeMatch = trimmed.match(/^```(\w+)?$/);
    if (codeMatch) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "code", language: codeMatch[1] ?? "", text: codeLines.join("\n") });
      index += 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length as 1 | 2 | 3,
        text: trimInlineCode(headingMatch[2])
      });
      index += 1;
      continue;
    }

    if (trimmed.startsWith("|") && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      const rows: string[][] = [parseTableRow(trimmed)];
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        rows.push(parseTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ type: "table", rows });
      continue;
    }

    if (trimmed.startsWith("- ")) {
      const items: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith("- ")) {
        items.push(trimInlineCode(lines[index].trim().slice(2)));
        index += 1;
      }
      blocks.push({ type: "list", items });
      continue;
    }

    const paragraphs: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().startsWith("#") &&
      !lines[index].trim().startsWith("- ") &&
      !lines[index].trim().startsWith("```") &&
      !lines[index].trim().startsWith("|")
    ) {
      paragraphs.push(trimInlineCode(lines[index].trim()));
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraphs.join(" ") });
  }

  return blocks;
}

function buildSections(blocks: MarkdownBlock[]) {
  const titleBlock = blocks.find((block) => block.type === "heading" && block.level === 1);
  const introBlocks: MarkdownBlock[] = [];
  const sections: ReportSection[] = [];
  let currentSection: ReportSection | null = null;

  for (const block of blocks) {
    if (block.type === "heading" && block.level === 1) {
      continue;
    }

    if (block.type === "heading" && block.level === 2) {
      currentSection = { title: block.text, blocks: [] };
      sections.push(currentSection);
      continue;
    }

    if (currentSection) {
      currentSection.blocks.push(block);
    } else {
      introBlocks.push(block);
    }
  }

  return {
    title: titleBlock?.type === "heading" ? titleBlock.text : "Analysis Report",
    introBlocks,
    sections
  };
}

function splitFact(item: string) {
  const separatorIndex = item.indexOf(": ");
  if (separatorIndex < 1) {
    return null;
  }
  return {
    label: item.slice(0, separatorIndex),
    value: item.slice(separatorIndex + 2)
  };
}

function renderList(items: string[], key: string) {
  const facts = items.map(splitFact);
  const canRenderAsFacts = facts.every(Boolean);

  if (canRenderAsFacts) {
    return (
      <dl className="report-fact-grid" key={key}>
        {facts.map((fact, index) =>
          fact ? (
            <div key={`${fact.label}-${index}`}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ) : null
        )}
      </dl>
    );
  }

  return (
    <ul key={key}>
      {items.map((item, itemIndex) => (
        <li key={`${item}-${itemIndex}`}>{item}</li>
      ))}
    </ul>
  );
}

function renderBlock(block: MarkdownBlock, index: number) {
  if (block.type === "heading") {
    const HeadingTag = `h${block.level}` as "h1" | "h2" | "h3";
    return <HeadingTag key={`${block.type}-${index}`}>{block.text}</HeadingTag>;
  }
  if (block.type === "list") {
    return renderList(block.items, `${block.type}-${index}`);
  }
  if (block.type === "code") {
    return <pre key={`${block.type}-${index}`}>{block.text}</pre>;
  }
  if (block.type === "table") {
    const [header, ...rows] = block.rows;
    return (
      <div className="report-table-wrap" key={`${block.type}-${index}`}>
        <table className="report-table">
          <thead>
            <tr>
              {header.map((cell, cellIndex) => (
                <th key={`${cell}-${cellIndex}`}>{cell}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`${cell}-${cellIndex}`}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return <p key={`${block.type}-${index}`}>{block.text}</p>;
}

export function ReportPreview({ markdown }: { markdown: string }) {
  const blocks = parseMarkdown(markdown);
  const report = buildSections(blocks);

  return (
    <article className="report-viewer">
      <header className="report-document-header">
        <p className="eyebrow">DataPrep Studio</p>
        <h1>{report.title}</h1>
      </header>
      {report.introBlocks.length ? <section className="report-section">{report.introBlocks.map(renderBlock)}</section> : null}
      {report.sections.map((section, sectionIndex) => (
        <section className="report-section" key={`${section.title}-${sectionIndex}`}>
          <h2 className="report-section-title">{section.title}</h2>
          <div className="report-section-body">{section.blocks.map(renderBlock)}</div>
        </section>
      ))}
    </article>
  );
}
