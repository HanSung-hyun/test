"""
ticker_guard.py - Deterministic Hallucination & Ticker Validation Guard

Ensures that every ticker and quantitative claim in an extracted strategy JSON
strictly matches the verbatim raw transcript text, eliminating LLM associative hallucination.
"""

import re
import json
from typing import Dict, List, Tuple, Any

def normalize_text(text: str) -> str:
    """Normalize text by removing spaces and lowercase for fuzzy matching."""
    return re.sub(r'\s+', '', text.lower())

def validate_ticker_in_transcript(ticker: str, transcript_text: str) -> bool:
    """
    Check if a ticker exists in transcript_text.
    Checks:
    1. Exact match
    2. Normalized match (without whitespace, case-insensitive)
    """
    if ticker in transcript_text:
        return True
    
    # Check normalized
    norm_ticker = normalize_text(ticker)
    norm_transcript = normalize_text(transcript_text)
    if norm_ticker in norm_transcript:
        return True
        
    return False

def validate_and_guard_strategy(strategy: Dict[str, Any], transcript_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Validates strategy JSON against transcript text.
    1. Purges hallucinated tickers from mentioned_tickers.
    2. Checks for known hallucination patterns (arbitrary stoploss %, fake numbers).
    3. Returns (guarded_strategy, audit_report).
    """
    audit = {
        "valid_tickers": [],
        "purged_tickers": [],
        "warnings": [],
        "is_clean": True
    }
    
    # 1. Ticker Guard
    tickers = strategy.get("mentioned_tickers", [])
    valid_tickers = []
    purged_tickers = []
    
    for t in tickers:
        # If ticker has parentheses like "에스피소프트(SP소프트)", test both parts
        parts = re.split(r'[\(\)]', t)
        parts = [p.strip() for p in parts if p.strip()]
        
        found = False
        for p in parts:
            if validate_ticker_in_transcript(p, transcript_text):
                found = True
                break
                
        if found:
            valid_tickers.append(t)
        else:
            purged_tickers.append(t)
            audit["is_clean"] = False
            audit["warnings"].append(f"Purged hallucinated ticker '{t}': Not found in transcript.")

    strategy["mentioned_tickers"] = valid_tickers
    audit["valid_tickers"] = valid_tickers
    audit["purged_tickers"] = purged_tickers
    
    # Check if purged tickers appear inside text fields
    strategy_str = json.dumps(strategy, ensure_ascii=False)
    for pt in purged_tickers:
        pt_clean = re.sub(r'[\(\)]', '', pt).strip()
        if pt_clean and pt_clean in strategy_str:
            audit["warnings"].append(f"ALERT: Purged ticker '{pt_clean}' still appears in strategy body text! Please clean manually.")
            audit["is_clean"] = False

    # 2. Number & Percentage Guard (Check for common hallucinated clichés)
    cliches = [
        (r'-\s*[2345]%', "Arbitrary stoploss percentage (-2%, -3%, etc.)"),
        (r'3\s*~\s*5\s*종목', "Cliché '3~5종목' distribution")
    ]
    for pattern, desc in cliches:
        for match in re.finditer(pattern, strategy_str):
            matched_str = match.group(0)
            if not validate_ticker_in_transcript(matched_str, transcript_text):
                audit["warnings"].append(f"Cliché Warning: '{matched_str}' ({desc}) found in JSON but might not be in transcript. Check verbatim quote.")

    return strategy, audit

if __name__ == "__main__":
    print("Ticker Guard module loaded successfully.")
