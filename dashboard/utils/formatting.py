def format_nepalese_number(number):
    """
    Format a number in Nepalese/Indian counting format (e.g., 1,23,45,678).
    """
    try:
        val = int(number)
    except (ValueError, TypeError):
        return str(number)
    
    is_negative = val < 0
    num_str = str(abs(val))
    
    if len(num_str) <= 3:
        formatted = num_str
    else:
        last_three = num_str[-3:]
        remaining = num_str[:-3]
        groups = []
        while len(remaining) > 2:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.append(remaining)
        formatted = ",".join(reversed(groups)) + "," + last_three
        
    return f"-{formatted}" if is_negative else formatted
