def normalize_cosine_distance(n):
    """
    Normalize result from cosine similarity check.
    
    Args:
        n: float [0,2] (0 = perfectly similar, 1 = orthogonal, 2 = perfectly dissimilar)
        
    Returns:
        float: Normalized similarity score [0, 1] where 1 is perfectly similar
    """ 
    assert(0 <= n <= 2)
    return (2 - n) / 2