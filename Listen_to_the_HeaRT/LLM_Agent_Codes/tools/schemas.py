RECENT_CRICKET_MATCHES_FUNCTION_SCHEMA = {
    "name": "get_recent_cricket_matches",
    "description": "Fetches the most recent cricket matches and their details from Cricbuzz. Returns the raw API JSON response.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

tools = [{"type": "function", "function": RECENT_CRICKET_MATCHES_FUNCTION_SCHEMA}]
