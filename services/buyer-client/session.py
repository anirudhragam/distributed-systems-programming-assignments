# Session management for buyer CLI
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class BuyerSession:
    """Represents an active buyer session"""
    session_id: Optional[str] = None
    buyer_id: Optional[int] = None
    
    def clear(self):
        """Clear session data after logout"""
        self.session_id = None
        self.buyer_id = None