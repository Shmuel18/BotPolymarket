# scanner.py
import requests
import re
import logging
from typing import Dict, List, Optional, Any
from .config import GAMMA_API_URL, MAX_RETRIES, RETRY_DELAY
import time

logger = logging.getLogger(__name__)

def extract_price_threshold(question: str) -> Optional[float]:
    """Extract numerical threshold from market question string.
    
    Args:
        question: Market question text (e.g., "BTC above $100k?")
    
    Returns:
        Threshold value as float, or None if extraction fails
    """
    try:
        clean_q = question.replace('$', '').replace(',', '').lower()
        # Pattern matches: "100" "100k" "100.5" "100.5k"
        match = re.search(r'(\d+(?:\.\d+)?)\s*k?(?:\s|$|\?)', clean_q)
        if not match:
            return None
            
        val = float(match.group(1))
        # Handle 'k' suffix (e.g., 100k = 100000)
        if 'k' in clean_q[match.start():match.end()+1] and val < 1000:
            val *= 1000
        return val
    except (ValueError, AttributeError) as e:
        logger.debug(f"Failed to extract threshold from '{question}': {e}")
        return None

def get_question_direction(question: str) -> Optional[str]:
    """Determine if question is 'above' or 'below' type.
    
    Args:
        question: Market question text
    
    Returns:
        'above' or 'below' or None if unclear
    """
    q_lower = question.lower()
    if any(word in q_lower for word in ['above', 'over', 'more than', 'exceed', 'higher']):
        return 'above'
    elif any(word in q_lower for word in ['below', 'under', 'less than', 'lower']):
        return 'below'
    return None

def extract_clob_token_id(market: Dict[str, Any]) -> Optional[str]:
    """Extract clobTokenId from market data, handling various formats.
    
    Args:
        market: Market dictionary from API response
    
    Returns:
        Clean token ID string, or None if not found
    """
    # Try clobTokenId field
    token_id = market.get("clobTokenId")
    if token_id:
        if isinstance(token_id, list) and len(token_id) > 0:
            token_id = token_id[0]
        if token_id:
            return str(token_id).strip()
    
    # Try clobTokenIds field
    token_ids = market.get("clobTokenIds")
    if isinstance(token_ids, list) and len(token_ids) > 0:
        return str(token_ids[0]).strip()
    
    return None

def scan_polymarket_for_hierarchical_markets(retry_count: int = 0) -> Dict[str, Any]:
    """Scan Gamma API for hierarchical/threshold-based markets.
    
    Hierarchical markets are identified by:
    1. Events with multiple markets (e.g., different dates/thresholds)
    2. Markets that share similar questions with different parameters
    
    Args:
        retry_count: Internal retry counter
    
    Returns:
        Dictionary mapping event titles to market data
    """
    url = f"{GAMMA_API_URL}/events?active=true&closed=false&limit=500"
    
    try:
        logger.info(f"Scanning Gamma API: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        events = response.json()
        
        if not isinstance(events, list):
            logger.error(f"Expected list from API, got: {type(events)}")
            return {}
            
    except requests.exceptions.Timeout:
        logger.error("Gamma API request timeout")
        if retry_count < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return scan_polymarket_for_hierarchical_markets(retry_count + 1)
        return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching from Gamma API: {e}")
        if retry_count < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return scan_polymarket_for_hierarchical_markets(retry_count + 1)
        return {}
    except Exception as e:
        logger.error(f"Unexpected error scanning markets: {e}")
        return {}

    hierarchical_markets = {}
    
    for event in events:
        try:
            event_title = event.get('title', '')
            markets = event.get("markets", [])
            
            # Only process events with 2+ markets (these are hierarchical by definition)
            if len(markets) < 2:
                continue

            market_pairs = []
            directions = []  # Track direction consistency
            
            # Extract token IDs for all markets in the event
            for market in markets:
                question = market.get('question', '')
                cond_id = market.get('conditionId', '')
                outcomes = market.get('outcomes', [])  # Get outcomes explicitly
                
                # Get token IDs (can be string or list)
                token_ids_raw = market.get('clobTokenIds', [])
                if not token_ids_raw:
                    token_ids_raw = market.get('clobTokenId', [])
                
                # Ensure it's a list
                if isinstance(token_ids_raw, str):
                    token_ids = [token_ids_raw]
                elif isinstance(token_ids_raw, list):
                    token_ids = [str(t) for t in token_ids_raw if t]
                else:
                    token_ids = []
                
                # Extract threshold for sorting
                threshold = extract_price_threshold(question)
                direction = get_question_direction(question)
                
                # Find YES token explicitly from outcomes
                yes_token = None
                if outcomes and len(outcomes) >= 2 and len(token_ids) >= 2:
                    # Match outcome to token
                    for i, outcome in enumerate(outcomes):
                        if outcome.lower() == 'yes' and i < len(token_ids):
                            yes_token = token_ids[i]
                            break
                    if not yes_token:  # Fallback: usually YES is second
                        yes_token = token_ids[1] if len(token_ids) >= 2 else token_ids[0]
                elif len(token_ids) >= 2:
                    yes_token = token_ids[1]  # Fallback
                elif len(token_ids) == 1:
                    yes_token = token_ids[0]
                
                if yes_token and direction:
                    market_pairs.append({
                        "question": question,
                        "conditionId": cond_id,
                        "clobTokenId": yes_token,  # YES token explicitly
                        "clobTokenIds": token_ids,  # All tokens for NO lookup
                        "threshold": threshold if threshold else 999999,
                        "direction": direction
                    })
                    directions.append(direction)
            
            # Check direction consistency - all must be same direction
            if directions and len(set(directions)) > 1:
                logger.warning(f"Mixed directions in {event_title}: {set(directions)} - skipping")
                continue
            
            # Sort by threshold (ascending) to ensure correct parent/child order
            market_pairs.sort(key=lambda m: m.get('threshold', 999999))
            
            # If we have 2+ markets with token IDs, it's hierarchical
            if len(market_pairs) >= 2:
                hierarchical_markets[event_title] = {
                    "clob_token_ids": [m["clobTokenId"] for m in market_pairs],
                    "questions": [m["question"] for m in market_pairs],
                    "thresholds": [m.get("threshold") for m in market_pairs],
                    "market_count": len(market_pairs),
                    "all_token_ids": [m["clobTokenIds"] for m in market_pairs]
                }
                logger.info(f"Found hierarchical market: {event_title} ({len(market_pairs)} markets)")
                
        except Exception as e:
            logger.warning(f"Error processing event {event.get('title', 'unknown')}: {e}")
            continue
            
    logger.info(f"Total hierarchical markets found: {len(hierarchical_markets)}")
    return hierarchical_markets