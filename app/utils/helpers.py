# Function to evaluate keyword feedback
def evaluate_keyword_feedback(keyword_feedback, predefined_keywords):
    """
    Evaluate keyword feedback by taking into account all received keywords (accepted and rejected)
    and compute simple metrics such as the accuracy rate.

    Args:
        keyword_feedback (list[dict]): Raw list of keyword feedback.
        predefined_keywords (list[str]): List of keywords proposed in the dropdown.
    
    Returns:
        dict: Contains lists of feedback and computed metrics.
    """

    # Separate accepted keywords into two groups:
    # 1. API accepted keywords: those with "accept" and no justification of manual addition or dropdown selection.
    api_accepted_keywords = [
        item for item in keyword_feedback 
        if item.get("accept", "").lower() == "accept" 
           and not (item.get("justification") 
                    and item.get("justification").strip().lower() in ["added manually by user", "selected from dropdown"])
    ]
    
    # 2. Manual added keywords: those with "accept" and a justification indicating manual addition or dropdown selection.
    manual_added_keywords = [
        item for item in keyword_feedback 
        if item.get("accept", "").lower() == "accept" 
           and item.get("justification") 
           and item.get("justification").strip().lower() in ["added manually by user", "selected from dropdown"]
    ]
    
    # Rejected keywords: those where "accept" is not "accept"
    rejected_keywords = [
        item for item in keyword_feedback if item.get("accept", "").lower() != "accept"
    ]
    
    # Simple metrics calculation
    total_keywords = len(keyword_feedback)
    api_accepted_count = len(api_accepted_keywords)
    manual_added_count = len(manual_added_keywords)
    final_true_count = api_accepted_count + manual_added_count
    count_rejected = len(rejected_keywords)
    
    # Accuracy rate: proportion of accepted keywords that come from the API proposals.
    accuracy_rate = (api_accepted_count / final_true_count) if final_true_count > 0 else 0

    return {
        "all_keywords": keyword_feedback,
        "api_accepted_keywords": api_accepted_keywords,
        "manual_added_keywords": manual_added_keywords,
        "rejected_keywords": rejected_keywords,
        "total_keywords": total_keywords,
        "api_accepted_count": api_accepted_count,
        "manual_added_count": manual_added_count,
        "final_true_count": final_true_count,
        "count_rejected": count_rejected,
        "accuracy_rate": round(accuracy_rate, 2),

    }
