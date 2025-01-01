import os
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from tqdm import tqdm
import concurrent.futures
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResourceScraper:
    """A class to search and download academic papers from arXiv, Semantic Scholar, PMC, Google Books, and Wikibooks."""
    
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
        self.scholar_url = 'https://scholar.google.com/scholar'
        self.google_books_url = 'https://www.googleapis.com/books/v1/volumes'
        self.wikibooks_url = 'https://en.wikibooks.org'
        self.eric_url = 'https://eric.ed.gov'
        self.openlibrary_url = 'https://openlibrary.org'

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
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.'))
        filename = ' '.join(filename.split())
        if len(filename) > 150:
            filename = filename[:147] + "..."
        return filename

    def search_arxiv(self, query, max_results=10):
        """Search arXiv for papers."""
        try:
            encoded_query = quote_plus(query)
            search_url = f"{self.arxiv_url}all:{encoded_query}&start=0&max_results={max_results}"
            
            logger.info(f"Searching arXiv for: {query}")
            
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code == 200:
                
                root = ET.fromstring(response.content)
                
                
                namespaces = {
                    'atom': 'http://www.w3.org/2005/Atom',
                    'arxiv': 'http://arxiv.org/schemas/atom'
                }
                
                results = []
                
                
                for entry in root.findall('atom:entry', namespaces):
                    try:
                        
                        title = entry.find('atom:title', namespaces).text.strip()
                        authors = [author.find('atom:name', namespaces).text 
                                 for author in entry.findall('atom:author', namespaces)]
                        published = entry.find('atom:published', namespaces).text
                        summary = entry.find('atom:summary', namespaces).text.strip()
                        
                        
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
                        title = paper.get('title', '')
                        if not title:
                            logger.debug(f"No title found in paper data: {paper}")
                            continue
                        
                        
                        pdf_url = paper.get('openAccessPdf', {}).get('url', '')
                        if not pdf_url:
                            logger.debug(f"No PDF URL found for paper: {title}")
                            continue
                        
                        
                        authors = [author.get('name', '') for author in paper.get('authors', []) if author.get('name')]
                        year = paper.get('year', '') or 'Unknown'
                        abstract = paper.get('abstract', '') or 'No abstract available'
                        
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
                        logger.debug(f"Problematic data: {paper}")
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

    def search_google_scholar(self, query, max_results=10):
        """Search Google Scholar for papers."""
        try:
            params = {
                'q': query,
                'hl': 'en',
                'num': max_results,
                'as_sdt': '0,5'
            }
            
            logger.info(f"Searching Google Scholar for: {query}")
            
            response = self.session.get(
                self.scholar_url,
                params=params,
                timeout=30
            )
            
            results = []
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all('div', class_='gs_r gs_or gs_scl')
                
                for article in articles[:max_results]:
                    try:
                        title_elem = article.find('h3', class_='gs_rt')
                        if not title_elem:
                            continue
                            
                        title = title_elem.get_text(strip=True)
                        
                        meta = article.find('div', class_='gs_a')
                        authors = []
                        published = ''
                        if meta:
                            meta_text = meta.get_text(strip=True)
                            parts = meta_text.split('-')
                            if len(parts) > 0:
                                authors = [a.strip() for a in parts[0].split(',')]
                            if len(parts) > 1:
                                year_match = re.search(r'\d{4}', parts[1])
                                if year_match:
                                    published = year_match.group(0)
                        
                        summary_elem = article.find('div', class_='gs_rs')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ''
                        
                        pdf_link = None
                        for link in article.find_all('a'):
                            if '[PDF]' in link.get_text() or 'pdf' in link.get('href', '').lower():
                                pdf_link = link.get('href')
                                break
                        
                        if pdf_link:
                            results.append({
                                'title': title,
                                'url': pdf_link,
                                'authors': authors,
                                'published': published,
                                'summary': summary[:200] + '...' if summary else ''
                            })
                    except Exception as e:
                        logger.error(f"Error parsing Google Scholar entry: {str(e)}")
                        continue
                        
            return results
            
        except Exception as e:
            logger.error(f"Error searching Google Scholar: {str(e)}")
            return []

    def search_google_books(self, query, max_results=10):
        """Search Google Books for documents."""
        try:
            logger.info(f"Searching Google Books for: {query}")
            
            params = {
                'q': query,
                'maxResults': max_results,
                'filter': 'free-ebooks',  # Only get free and downloadable books
                'download': 'epub',  
                'printType': 'books'
            }
            
            response = self.session.get(self.google_books_url, params=params, timeout=30)
            
            results = []
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                for item in items[:max_results]:
                    try:
                        volume_info = item.get('volumeInfo', {})
                        access_info = item.get('accessInfo', {})
                        
                        
                        if not access_info.get('pdf', {}).get('downloadLink') and not access_info.get('epub', {}).get('downloadLink'):
                            continue
                        
                        title = volume_info.get('title', '')
                        if not title:
                            continue
                        
                        
                        authors = volume_info.get('authors', [])
                        
                        
                        published = volume_info.get('publishedDate', '')
                        if published:
                            
                            published = published.split('-')[0]
                        
                        
                        summary = volume_info.get('description', '')
                        
                        
                        download_url = (access_info.get('pdf', {}).get('downloadLink') or 
                                      access_info.get('epub', {}).get('downloadLink'))
                        
                        if download_url:
                            results.append({
                                'title': title,
                                'url': download_url,
                                'authors': authors,
                                'published': published,
                                'summary': summary[:200] + '...' if summary else ''
                            })
                            
                            logger.info(f"Found book: {title}")
                    
                    except Exception as e:
                        logger.error(f"Error parsing Google Books entry: {str(e)}")
                        continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Google Books: {str(e)}")
            return []

    def search_wikibooks(self, query, max_results=10):
        """Search Wikibooks for educational content."""
        try:
            logger.info(f"Searching Wikibooks for: {query}")
            
            # Wikibooks search URL
            search_url = f"{self.wikibooks_url}/w/index.php"
            params = {
                'search': query,
                'title': 'Special:Search',
                'profile': 'advanced',
                'fulltext': '1',
                'ns0': '1'  # Search in main namespace
            }
            
            response = self.session.get(search_url, params=params, timeout=30)
            results = []
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                search_results = soup.find_all('div', class_='mw-search-result-heading')
                
                for result in search_results[:max_results]:
                    try:
                        
                        title_elem = result.find('a')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        book_url = title_elem.get('href', '')
                        
                        if not book_url:
                            continue
                        
                        
                        if book_url.startswith('/'):
                            book_url = self.wikibooks_url + book_url
                        
                       
                        book_response = self.session.get(book_url, timeout=30)
                        if book_response.status_code == 200:
                            book_soup = BeautifulSoup(book_response.text, 'html.parser')
                            
                            
                            authors = []
                            author_links = book_soup.find_all('a', class_='mw-userlink')
                            if author_links:
                                authors = [a.get_text(strip=True) for a in author_links[:3]]  
                            
                            
                            published = ''
                            footer = book_soup.find('div', id='footer-info-lastmod')
                            if footer:
                                date_match = re.search(r'\d{1,2}\s+\w+\s+\d{4}', footer.get_text())
                                if date_match:
                                    published = date_match.group(0)
                            
                            
                            summary = ''
                            content = book_soup.find('div', id='mw-content-text')
                            if content:
                                paragraphs = content.find_all('p', recursive=False)
                                if paragraphs:
                                    summary = paragraphs[0].get_text(strip=True)
                            
                           
                            printable_url = f"{book_url}?printable=yes"
                            
                            results.append({
                                'title': title,
                                'url': printable_url,
                                'authors': authors,
                                'published': published,
                                'summary': summary[:200] + '...' if summary else ''
                            })
                            
                            logger.info(f"Found book: {title}")
                            
                            if len(results) >= max_results:
                                break
                    
                    except Exception as e:
                        logger.error(f"Error parsing Wikibooks entry: {str(e)}")
                        continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Wikibooks: {str(e)}")
            return []

    def search_eric(self, query, max_results=10):
        """
        Search ERIC (Education Resources Information Center) database.
        Uses their web interface since it's more reliable than the API.
        
        Args:
            query (str): Search term
            max_results (int): Maximum number of results to return
        
        Returns:
            list: List of dictionaries containing document information
        """
        try:
            search_url = f'{self.eric_url}/'
            params = {
                'q': query,
                'pg': 1,
                'nfq': max_results,
                'ft': 'on'  
            }
            
            logger.info(f"Searching ERIC for: {query}")
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            documents = []
            
           
            results = soup.find_all('div', class_='r_i')
            
            for result in results[:max_results]:
                try:
                    title_elem = result.find('div', class_='r_t')
                    if not title_elem:
                        continue
                        
                    title = title_elem.text.strip()
                    
                    link = result.find('a', href=True)
                    if not link:
                        continue
                    
                    doc_id = link['href'].split('id=')[-1] if 'id=' in link['href'] else None
                    if not doc_id:
                        continue
                    
                    pdf_available = False
                    pdf_link = result.find('img', {'alt': 'PDF'})
                    if pdf_link:
                        pdf_url = f'https://files.eric.ed.gov/fulltext/{doc_id}.pdf'
                        pdf_check = self.session.head(pdf_url)
                        if pdf_check.status_code == 200:
                            pdf_available = True
                    
                    authors = []
                    author_elem = result.find('div', class_='r_a')
                    if author_elem:
                        authors = [a.strip() for a in author_elem.text.split(';') if a.strip()]
                    
                    year = ''
                    year_elem = result.find('div', class_='r_y')
                    if year_elem:
                        year = year_elem.text.strip()
                    
                    summary = ''
                    desc_elem = result.find('div', class_='r_d')
                    if desc_elem:
                        summary = desc_elem.text.strip()
                    
                    url = f'{self.eric_url}/?id={doc_id}'
                    
                    doc_info = {
                        'title': title,
                        'authors': authors,
                        'url': url,
                        'published': year,
                        'summary': summary,
                        'source': 'ERIC'
                    }
                    
                    if pdf_available:
                        doc_info['pdf_url'] = f'https://files.eric.ed.gov/fulltext/{doc_id}.pdf'
                    
                    documents.append(doc_info)
                    
                    logger.info(f"Found ERIC document: {title}")
                    if pdf_available:
                        logger.info(f"PDF available at: {doc_info['pdf_url']}")
                    
                except Exception as e:
                    logger.error(f"Error processing ERIC result: {str(e)}")
                    continue
            
            return documents
            
        except requests.RequestException as e:
            logger.error(f"ERIC search error: {e}")
            return []

    def search_openlibrary(self, query, max_results=10):
        """
        Search OpenLibrary catalog.
        OpenLibrary provides a comprehensive catalog of books and academic resources.
        
        Args:
            query (str): Search term
            max_results (int): Maximum number of results to return
        
        Returns:
            list: List of dictionaries containing document information
        """
        try:
            search_url = f'{self.openlibrary_url}/search.json'
            params = {
                'q': query,
                'limit': max_results,
                'fields': 'title,author_name,first_publish_year,number_of_pages_median,ebook_count_i,edition_count,subject,key'
            }
            
            logger.info(f"Searching OpenLibrary for: {query}")
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            documents = []
            
            for doc in data.get('docs', [])[:max_results]:
                try:
                    title = doc.get('title', '').strip()
                    if not title:
                        continue
                    
                    # Get authors
                    authors = doc.get('author_name', [])
                    
                    # Get year
                    year = str(doc.get('first_publish_year', '')) if doc.get('first_publish_year') else ''
                    
                    # Create OpenLibrary URL
                    key = doc.get('key', '')
                    url = f'https://openlibrary.org{key}' if key else None
                    
                    # Create summary with available information
                    summary_parts = []
                    if doc.get('edition_count'):
                        summary_parts.append(f"Available in {doc['edition_count']} editions")
                    if doc.get('ebook_count_i'):
                        summary_parts.append(f"{doc['ebook_count_i']} ebook versions")
                    if doc.get('number_of_pages_median'):
                        summary_parts.append(f"~{doc['number_of_pages_median']} pages")
                    if doc.get('subject', []):
                        subjects = doc['subject'][:3]  # Get first 3 subjects
                        summary_parts.append(f"Subjects: {', '.join(subjects)}")
                    
                    summary = '. '.join(summary_parts)
                    
                    doc_info = {
                        'title': title,
                        'authors': authors,
                        'url': url,
                        'published': year,
                        'summary': summary,
                        'source': 'OpenLibrary'
                    }
                    
                    documents.append(doc_info)
                    logger.info(f"Found document: {title}")
                    
                except Exception as e:
                    logger.error(f"Error parsing OpenLibrary entry: {str(e)}")
                    continue
            
            return documents
            
        except Exception as e:
            logger.error(f"Error searching OpenLibrary: {str(e)}")
            return []

    def search_and_download(self, query, max_results=10):
        """Search all sources and download papers."""
        all_results = []
        
        # Search each source
        arxiv_results = self.search_arxiv(query, max_results)
        semantic_results = self.search_semantic_scholar(query, max_results)
        pmc_results = self.search_pmc(query, max_results)
        scholar_results = self.search_google_scholar(query, max_results)
        books_results = self.search_google_books(query, max_results)
        wiki_results = self.search_wikibooks(query, max_results)
        eric_results = self.search_eric(query, max_results)
        openlibrary_results = self.search_openlibrary(query, max_results)
        
        # Combine all results
        all_results.extend(arxiv_results)
        all_results.extend(semantic_results)
        all_results.extend(pmc_results)
        all_results.extend(scholar_results)
        all_results.extend(books_results)
        all_results.extend(wiki_results)
        all_results.extend(eric_results)
        all_results.extend(openlibrary_results)
        
        if not all_results:
            logger.info("No papers found.")
            return []
        
        downloaded = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_paper = {
                executor.submit(
                    self.download_paper,
                    paper.get('pdf_url', paper.get('url')),
                    paper['title']
                ): paper for paper in all_results if paper.get('pdf_url') or paper.get('url')
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

    def download_paper(self, url, title):
        """Download a paper with progress tracking."""
        try:
            self._create_output_dir()
            
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

def main():
    """Main function to run the scraper."""
    scraper = ResourceScraper()
    
    while True:
        query = input("\nEnter your search query (or 'quit' to exit): ")
        if query.lower() == 'quit':
            break
            
        try:
            limit = int(input("How many resources would you like to download from each source? (default: 5): ") or 5)
        except ValueError:
            limit = 5
            
        downloaded_files = scraper.search_and_download(query, limit)

if __name__ == "__main__":
    main()
