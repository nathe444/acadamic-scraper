# Academic Paper Scraper

## Overview
A powerful Python tool for searching and downloading academic papers from multiple sources. Perfect for building research datasets for NotebookLM and other AI-powered research tools.

## Features
- Multi-source paper retrieval:
  - PubMed Central (PMC) - Biomedical and life sciences
  - arXiv - Physics, Mathematics, Computer Science, etc.
  - Semantic Scholar - Cross-disciplinary academic search
  - Google Scholar - Wide academic coverage

- Advanced capabilities:
  - Concurrent downloads (up to 3 simultaneous)
  - Automatic PDF retrieval
  - Rich metadata extraction
  - Smart file naming
  - Progress tracking
  - Detailed logging

- NotebookLM Integration:
  - Downloads papers in PDF format ready for NotebookLM import
  - Extracts rich metadata for better context
  - Organizes papers systematically for easy upload
  - Supports building comprehensive research datasets
  - Perfect for training domain-specific AI models

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

```python
from scholarly_scraper import ResourceScraper

# Initialize scraper
scraper = ResourceScraper(output_dir="downloads")

# Search and download papers
results = scraper.search_and_download("your search query", max_results=5)
```

Or run directly from command line:
```bash
python scholarly_scraper.py
```

## Search Order

Papers are searched in the following order:
1. PubMed Central (PMC) - Peer-reviewed biomedical literature
2. arXiv - Preprints in sciences and mathematics
3. Semantic Scholar - Wide academic coverage
4. Google Scholar

## Output

- Downloads are saved to the `downloads` directory (created automatically)
- File names are sanitized for compatibility
- PDF format optimized for NotebookLM ingestion

## Requirements

- Python 3.8+
- See `requirements.txt` for package dependencies

## Error Handling

- Robust error recovery
- Automatic retry on failed downloads
- Comprehensive logging
- Safe file naming

## Limitations

- Depends on source API availability
- Subject to rate limiting by sources
- Some papers may require institutional access

## NotebookLM Integration Guide

1. Use the scraper to download relevant papers
2. Papers are saved in PDF format in the `downloads` directory
3. Upload the downloaded PDFs to NotebookLM
4. Use NotebookLM's AI capabilities to:
   - Extract key insights
   - Generate summaries
   - Create research notes
   - Find connections between papers
   - Build knowledge graphs

## Contributing

Feel free to open issues or submit pull requests for improvements.

## License

MIT License - See LICENSE file for details

---
*Last updated: December 8, 2024*