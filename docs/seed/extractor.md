We need to build a tool to extract agent-accessible knowledge from from multiple inputs files.

Input:
- a deep file tree comprising several hundred files
- Sopported formats: MS Work, MS Powerpoint, MS Excel, PDF, JPEG, PNG. Other formats can be ignored.
- There is a lot of graphical material (figures, picture) that carry important information

Outputs:
- AI-agent accessible pure Markdown files
- No pictures, text only
- An index file as an entry point

Tasks as I see them:
- Extract textual and graphical information depending on a format
- Remove non-essential title pages, logos, headers, redundant information
- Run semantical analysis of the graphical information and convert to to eigher Mermaid diagrams or textual descriptions.

Debugging support:
- The tool shall save intermediate results (e.g., markdowns with original pictures) to allow for manual extraction process assessments.

Interface:
- CLI tool
- Parameters:
  - input directory
  - output directory (default: `/output`)
  - intermediate data directory (default: `/temp`)

Tooling:
- The tool can use external AI APIs through OpenRouter or local coding agents in headless mode.
- Python managed by UV
