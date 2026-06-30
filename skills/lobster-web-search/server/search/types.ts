
export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  source: 'bing' | 'google';
  position: number;
}

export interface SearchResponse {
  query: string;
  engine: 'bing' | 'google';
  results: SearchResult[];
  totalResults: number;
  timestamp: number;
  duration: number;
}
