# Session management for seller CLI
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class SellerSession:
    """Represents an active seller session"""
    session_id: Optional[str] = None
    seller_id: Optional[int] = None
    
    def clear(self):
        """Clear session data after logout"""
        self.session_id = None
        self.seller_id = None