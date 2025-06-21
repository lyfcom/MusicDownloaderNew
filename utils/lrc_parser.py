import re

# Regex to parse [mm:ss.xx] or [mm:ss] timestamps
TIMESTAMP_REGEX = re.compile(r'\[(\d{2}):(\d{2})\.?(\d{2})?\]')

def parse_lrc_line(line):
    """
    Parses a single LRC format lyric line to extract timestamp and text.
    Returns a tuple (timestamp_in_ms, text) or None if parsing fails.
    Timestamp is converted to milliseconds.
    """
    match = TIMESTAMP_REGEX.match(line)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        # Milliseconds part is optional
        milliseconds = int(match.group(3)) if match.group(3) else 0
        # Calculate total milliseconds
        timestamp_ms = (minutes * 60 + seconds) * 1000 + milliseconds * 10 # Assuming xx is 10ms units if present

        # Find the text part after the last timestamp
        text_start_index = line.rfind(']') + 1
        text = line[text_start_index:].strip()

        return (timestamp_ms, text)
    return None 