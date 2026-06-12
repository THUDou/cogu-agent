from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


def _stock_quote(symbol: str) -> str:
    try:
        import yfinance as yf
    except ImportError:
        return "Error: yfinance not installed. Run: pip install yfinance"
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or "symbol" not in info:
            return f"Error: no data for symbol '{symbol}'"
        lines = [
            f"Symbol: {info.get('symbol', symbol)}",
            f"Name: {info.get('longName', info.get('shortName', 'N/A'))}",
            f"Price: {info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))}",
            f"Change: {info.get('regularMarketChange', 'N/A')} ({info.get('regularMarketChangePercent', 'N/A')})",
            f"Market Cap: {info.get('marketCap', 'N/A')}",
            f"PE Ratio: {info.get('trailingPE', 'N/A')}",
            f"52w High: {info.get('fiftyTwoWeekHigh', 'N/A')}",
            f"52w Low: {info.get('fiftyTwoWeekLow', 'N/A')}",
            f"Volume: {info.get('volume', 'N/A')}",
            f"Dividend Yield: {info.get('dividendYield', 'N/A')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Stock error: {e}"


def _stock_history(symbol: str, period: str = "1mo") -> str:
    try:
        import yfinance as yf
    except ImportError:
        return "Error: yfinance not installed. Run: pip install yfinance"
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return f"No history data for {symbol}"
        return hist.tail(20).to_string()
    except Exception as e:
        return f"Stock error: {e}"


def register_stock_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_stock_quote, name="stock_quote", description="Get real-time stock quote with key metrics (PE, market cap, 52w range, dividend). Supports A-share (.SS/.SZ), US, HK stocks.").with_capability(ToolCapability.NETWORK).mark_concurrency_safe().with_group("stock"))
    registry.register(FunctionTool(_stock_history, name="stock_history", description="Get historical stock price data. Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max.").with_capability(ToolCapability.NETWORK).mark_concurrency_safe().with_group("stock"))
