import os
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from tqdm import tqdm
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResourceScraper:
    """A class to search and download academic papers from arXiv, Semantic Scholar, and PMC."""
    
    def __init__(self, output_dir="downloads"):
        """Initialize the scraper with an output directory."""
        self.output_dir = output_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._create_output_dir()
        
        # Base URLs
        self.arxiv_url = 'https://export.arxiv.org/api/query?search_query='
        self.semantic_url = 'https://api.semanticscholar.org/graph/v1/paper/search'
        self.pmc_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

    def _create_output_dir(self):
        """Create the output directory if it doesn't exist."""
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            logger.info(f"Output directory ready: {self.output_dir}")
        except Exception as e:
            logger.error(f"Error creating output directory: {str(e)}")
            raise

    def sanitize_filename(self, filename):
        """Clean filename by removing invalid characters and limiting length."""
        # Remove invalid characters
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.'))
        # Replace multiple spaces with single space
        filename = ' '.join(filename.split())
        # Limit filename length (150 chars max)
        if len(filename) > 150:
            filename = filename[:147] + "..."
        return filename

    def search_arxiv(self, query, max_results=10):
        """Search arXiv for papers."""
        try:
            # Encode query and create search URL
            encoded_query = quote_plus(query)
            search_url = f"{self.arxiv_url}all:{encoded_query}&start=0&max_results={max_results}"
            
            logger.info(f"Searching arXiv for: {query}")
            
            # Make the request
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code == 200:
                # Parse XML response
                root = ET.fromstring(response.content)
                
                # Define XML namespaces
                namespaces = {
                    'atom': 'http://www.w3.org/2005/Atom',
                    'arxiv': 'http://arxiv.org/schemas/atom'
                }
                
                results = []
                
                # Process each entry
                for entry in root.findall('atom:entry', namespaces):
                    try:
                        # Extract paper details
                        title = entry.find('atom:title', namespaces).text.strip()
                        authors = [author.find('atom:name', namespaces).text 
                                 for author in entry.findall('atom:author', namespaces)]
                        published = entry.find('atom:published', namespaces).text
                        summary = entry.find('atom:summary', namespaces).text.strip()
                        
                        # Get PDF link
                        links = entry.findall('atom:link', namespaces)
                        pdf_url = None
                        for link in links:
                            if link.get('title') == 'pdf' or link.get('type') == 'application/pdf':
                                pdf_url = link.get('href')
                                if 'pdf' not in pdf_url:
                                    pdf_url = pdf_url.replace('abs', 'pdf') + '.pdf'
                                break
                        
                        if pdf_url:
                            results.append({
                                'title': title,
                                'url': pdf_url,
                                'authors': authors,
                                'published': published,
                                'summary': summary
                            })
                            
                            logger.info(f"Found paper: {title}")
                    
                    except Exception as e:
                        logger.error(f"Error parsing arXiv entry: {str(e)}")
                        continue
                
                return results
            else:
                logger.error(f"Failed to access arXiv. Status code: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching arXiv: {str(e)}")
            return []

    def search_semantic_scholar(self, query, max_results=10):
        """Search Semantic Scholar for papers."""
        try:
            params = {
                'query': query,
                'limit': max_results,
                'fields': 'title,authors,year,abstract,url,openAccessPdf'
            }
            
            logger.info(f"Searching Semantic Scholar for: {query}")
            
            response = self.session.get(self.semantic_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for paper in data.get('data', []):
                    try:
                        title = paper.get('title')
                        if not title:
                            continue
                            
                        # Get PDF URL if available
                        pdf_url = paper.get('openAccessPdf', {}).get('url')
                        if not pdf_url:
                            continue
                        
                        # Get metadata
                        authors = [author.get('name', '') for author in paper.get('authors', [])]
                        year = paper.get('year', '')
                        abstract = paper.get('abstract', '')
                        
                        results.append({
                            'title': title,
                            'url': pdf_url,
                            'authors': authors,
                            'published': str(year),
                            'summary': abstract[:200] + '...' if abstract and len(abstract) > 200 else abstract
                        })
                        
                        logger.info(f"Found paper: {title}")
                    
                    except Exception as e:
                        logger.error(f"Error parsing Semantic Scholar result: {str(e)}")
                        continue
                
                return results
            else:
                logger.error(f"Failed to access Semantic Scholar. Status code: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching Semantic Scholar: {str(e)}")
            return []

    def search_pmc(self, query, max_results=10):
        """Search PubMed Central for papers."""
        try:
            # First search for IDs
            esearch_url = f"{self.pmc_url}esearch.fcgi"
            search_params = {
                'db': 'pmc',
                'term': query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            logger.info(f"Searching PMC for: {query}")
            
            response = self.session.get(esearch_url, params=search_params, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to search PMC. Status code: {response.status_code}")
                return []
                
            data = response.json()
            pmcids = data.get('esearchresult', {}).get('idlist', [])
            
            if not pmcids:
                return []
                
            # Then fetch details for each ID
            efetch_url = f"{self.pmc_url}efetch.fcgi"
            fetch_params = {
                'db': 'pmc',
                'id': ','.join(pmcids),
                'retmode': 'xml'
            }
            
            response = self.session.get(efetch_url, params=fetch_params, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to fetch PMC details. Status code: {response.status_code}")
                return []
                
            # Parse XML response
            root = ET.fromstring(response.content)
            results = []
            
            for article in root.findall('.//article'):
                try:
                    # Get title
                    title_elem = article.find('.//article-title')
                    if title_elem is None:
                        continue
                    title = ''.join(title_elem.itertext()).strip()
                    
                    # Get authors
                    authors = []
                    for author in article.findall('.//contrib[@contrib-type="author"]'):
                        surname = author.find('.//surname')
                        given_names = author.find('.//given-names')
                        if surname is not None and given_names is not None:
                            authors.append(f"{given_names.text} {surname.text}")
                    
                    # Get year
                    year = ''
                    pub_date = article.find('.//pub-date')
                    if pub_date is not None:
                        year_elem = pub_date.find('year')
                        if year_elem is not None:
                            year = year_elem.text
                    
                    # Get abstract
                    abstract = ''
                    abstract_elem = article.find('.//abstract')
                    if abstract_elem is not None:
                        abstract = ' '.join(abstract_elem.itertext()).strip()
                    
                    # Get PMC ID for PDF URL
                    pmcid = article.find('.//article-id[@pub-id-type="pmc"]')
                    if pmcid is None:
                        continue
                        
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid.text}/pdf"
                    
                    results.append({
                        'title': title,
                        'url': pdf_url,
                        'authors': authors,
                        'published': year,
                        'summary': abstract[:200] + '...' if abstract and len(abstract) > 200 else abstract
                    })
                    
                    logger.info(f"Found paper: {title}")
                    
                    if len(results) >= max_results:
                        break
                
                except Exception as e:
                    logger.error(f"Error parsing PMC result: {str(e)}")
                    continue
            
            return results
                
        except Exception as e:
            logger.error(f"Error searching PMC: {str(e)}")
            return []

    def download_paper(self, url, title):
        """Download a paper with progress tracking."""
        try:
            # Ensure output directory exists
            self._create_output_dir()
            
            # Create a safe filename
            safe_title = self.sanitize_filename(title)
            if not safe_title.endswith('.pdf'):
                safe_title += '.pdf'
                
            filepath = os.path.join(self.output_dir, safe_title)
            
            # Check if file already exists
            if os.path.exists(filepath):
                logger.info(f"File already exists: {safe_title}")
                return True, filepath
            
            # Download the file
            response = self.session.get(url, stream=True, timeout=30)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logger.info(f"Downloaded: {safe_title}")
                return True, filepath
            else:
                logger.error(f"Failed to download {safe_title}. Status code: {response.status_code}")
                return False, None
                
        except Exception as e:
            logger.error(f"Error downloading {title}: {str(e)}")
            return False, None

    def search_and_download(self, query, max_results=10):
        """Search all sources and download papers."""
        all_papers = []
        
        # Search PMC first
        logger.info("\nSearching PMC...")
        pmc_papers = self.search_pmc(query, max_results)
        if pmc_papers:
            logger.info(f"\nFound {len(pmc_papers)} papers on PMC:")
            for i, paper in enumerate(pmc_papers, 1):
                logger.info(f"\n{i}. {paper['title']}")
                logger.info(f"   Authors: {', '.join(paper['authors'][:3])}")
                logger.info(f"   Published: {paper['published']}")
                if paper.get('summary'):
                    logger.info(f"   Summary: {paper['summary']}")
        all_papers.extend(pmc_papers)
        
        # Then search arXiv
        logger.info("\nSearching arXiv...")
        arxiv_papers = self.search_arxiv(query, max_results)
        if arxiv_papers:
            logger.info(f"\nFound {len(arxiv_papers)} papers on arXiv:")
            for i, paper in enumerate(arxiv_papers, 1):
                logger.info(f"\n{i}. {paper['title']}")
                logger.info(f"   Authors: {', '.join(paper['authors'][:3])}")
                logger.info(f"   Published: {paper['published'][:10]}")
                logger.info(f"   Summary: {paper['summary'][:200]}...")
        all_papers.extend(arxiv_papers)
        
        # Finally search Semantic Scholar
        logger.info("\nSearching Semantic Scholar...")
        semantic_papers = self.search_semantic_scholar(query, max_results)
        if semantic_papers:
            logger.info(f"\nFound {len(semantic_papers)} papers on Semantic Scholar:")
            for i, paper in enumerate(semantic_papers, 1):
                logger.info(f"\n{i}. {paper['title']}")
                logger.info(f"   Authors: {', '.join(paper['authors'][:3])}")
                logger.info(f"   Published: {paper['published']}")
                if paper.get('summary'):
                    logger.info(f"   Summary: {paper['summary']}")
        all_papers.extend(semantic_papers)
        
        if not all_papers:
            logger.info("No papers found.")
            return []
        
        # Download papers concurrently
        downloaded = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_paper = {
                executor.submit(
                    self.download_paper,
                    paper['url'],
                    paper['title']
                ): paper for paper in all_papers
            }
            
            for future in concurrent.futures.as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    success, filepath = future.result()
                    if success:
                        downloaded.append((paper['title'], filepath))
                except Exception as e:
                    logger.error(f"Error downloading {paper['title']}: {str(e)}")
        
        return downloaded

def main():
    """Main function to run the scraper."""
    scraper = ResourceScraper()
    
    while True:
        query = input("\nEnter your search query (or 'quit' to exit): ")
        if query.lower() == 'quit':
            break
            
        try:
            limit = int(input("How many resources would you like to download? (default: 5): ") or 5)
        except ValueError:
            limit = 5
            
        downloaded_files = scraper.search_and_download(query, limit)

if __name__ == "__main__":
    main()
