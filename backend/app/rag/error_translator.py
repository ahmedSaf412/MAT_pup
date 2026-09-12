def translate_errors(move_id: str, user_angles: dict, pro_angles: dict) -> list[str]:
    """
    Compares user angles to pro angles and generates natural language queries for the RAG search.
    Returns a list of error queries (one for each joint that is significantly out of bounds).
    """
    if not pro_angles:
        return []
        
    error_queries = []
    
    # Threshold for considering an error significant enough to query RAG
    # Use a generous threshold (e.g. 15 degrees) so we don't spam minor errors
    ERROR_THRESHOLD = 15.0
    
    for joint, user_val in user_angles.items():
        if joint not in pro_angles:
            continue
            
        pro_stat = pro_angles[joint]
        p_mean = pro_stat.get("mean", 90)
        p_std = pro_stat.get("std", 15)
        
        # Determine strict bounds: moving joints get a wider range, static joints get a strict range.
        window = max(p_std * 1.25, 12.0)
        p_min = p_mean - window
        p_max = p_mean + window
        
        error_msg = None
        
        if user_val < p_min - ERROR_THRESHOLD:
            diff = round((p_min - user_val), 1)
            error_msg = f"User's {joint} is {diff} degrees too small/bent during {move_id}."
        elif user_val > p_max + ERROR_THRESHOLD:
            diff = round((user_val - p_max), 1)
            error_msg = f"User's {joint} is {diff} degrees too large/extended during {move_id}."
            
        if error_msg:
            error_queries.append({
                "joint": joint,
                "query": error_msg,
                "user_val": user_val,
                "target_range": f"{p_min}-{p_max}"
            })
            
    return error_queries
