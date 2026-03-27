import math
import secrets
import random
from collections import defaultdict

class MLEngine:
    def __init__(self):
        # A lightweight set of "breach patterns" and common dictionary words for scoring.
        self.common_patterns = ['password', '123456', 'qwerty', 'admin', 'welcome', 'letmein', 'monkey']
        
    def score_password(self, password: str, user_info: list[str]) -> tuple[float, int]:
        """
        Returns a (strength_score 0.0-1.0, ttl_days)
        """
        score = 0.0
        length = len(password)
        
        # Length check
        if length >= 8: score += 0.2
        if length >= 12: score += 0.2
        if length >= 16: score += 0.1
        
        # Complexity check
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)
        
        complexity_score = sum([has_lower, has_upper, has_digit, has_symbol]) * 0.1
        score += complexity_score
        
        password_lower = password.lower()
        
        # Penalize if it contains personal info
        for info in user_info:
            if info and len(info) > 3 and info.lower() in password_lower:
                score -= 0.3
                
        # Penalize common patterns
        for pat in self.common_patterns:
            if pat in password_lower:
                score -= 0.3
                
        # Entropy approximation
        charset_size = 0
        if has_lower: charset_size += 26
        if has_upper: charset_size += 26
        if has_digit: charset_size += 10
        if has_symbol: charset_size += 32
        
        entropy = length * math.log2(charset_size) if charset_size > 0 else 0
        if entropy > 60: score += 0.1
        if entropy > 80: score += 0.1
        
        score = max(0.0, min(1.0, score))
        
        # Calculate dynamic TTL (e.g. min 30 days, max 2 years)
        ttl_days = int(30 + (score * 700)) 
        
        return score, ttl_days

    def generate_personalized_password(self, user_passwords: list[str]) -> str:
        """
        Uses a lightweight Markov Chain trained on the user's provided passwords to
        generate a new password that matches their syntactic "style" but is randomly generated.
        """
        if not user_passwords or len(user_passwords) < 3:
            # Fallback if vault is too small
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            return "".join(secrets.choice(chars) for _ in range(16))
            
        # Build 2-gram (Bigram) Markov chain
        chain = defaultdict(list)
        starts = []
        
        for pw in user_passwords:
            if len(pw) < 2: continue
            starts.append(pw[:2])
            for i in range(len(pw) - 2):
                gram = pw[i:i+2]
                next_char = pw[i+2]
                chain[gram].append(next_char)
                
        # Generate new password
        target_len = random.randint(12, 18)
        current = random.choice(starts) if starts else "Ab"
        res = current
        
        while len(res) < target_len:
            gram = res[-2:]
            if gram in chain and chain[gram]:
                res += secrets.choice(chain[gram])
            else:
                # Add random valid char if chain breaks
                res += secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%")
                
        # To ensure it doesn't exactly match an old one and meets complexity
        if res in user_passwords:
            res += secrets.choice("!@#$%^&*0123456789")
            
        return res

ml_engine = MLEngine()
