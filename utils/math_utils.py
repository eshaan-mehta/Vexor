def normalize_cosine_distance(n: float) -> float:
    """
    Normalize result from cosine similarity check using a sigmoid transformation.
    
    Args:
        n: float [0,2] (0 = perfectly similar, 1 = orthogonal, 2 = perfectly dissimilar)
        
    Returns:
        float: Normalized similarity score [0, 1] where:
            - 1.0 = perfectly similar
            - ~0.2 = orthogonal (no correlation)
            - ~0.0 = perfectly dissimilar
    """ 
    import numpy as np
    assert(0 <= n <= 2)
    
    # Sigmoid transformation parameters
    k = 10  # Controls steepness of the curve
    shift = 0.86  # Shift to center the sigmoid 

    return 1 / (1 + np.exp(k * (n - shift)))