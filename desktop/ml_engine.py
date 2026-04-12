import math
import secrets
import random
from collections import defaultdict

class MLEngine:
    def __init__(self):
        # Load the 100k RockYou derived wordlist
        self.common_patterns = set()
        import os
        try:
            path = os.path.join(os.path.dirname(__file__), "common_passwords.txt")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.common_patterns = set(line.strip().lower() for line in f if line.strip())
            else:
                self.common_patterns = set(['password', '123456', 'qwerty', 'admin', 'welcome', 'letmein', 'monkey'])
        except Exception:
            self.common_patterns = set(['password', '123456', 'qwerty', 'admin', 'welcome', 'letmein', 'monkey'])
        
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
        
        # Penalize if it contains personal info (Negative Dictionary generation)
        negative_dict = set()
        import re
        for info in user_info:
            if not info: continue
            info_clean = info.lower()
            negative_dict.add(info_clean)
            parts = re.split(r'[\s.,_-]+', info_clean)
            for p in parts:
                if len(p) >= 3:
                    negative_dict.add(p)
                    negative_dict.add(p + "123")
                    negative_dict.add(p + "1234")
                    negative_dict.add(p + "2024")
                    negative_dict.add(p + "2025")
                    
        for nd in negative_dict:
            if len(nd) >= 3 and nd in password_lower:
                score -= 0.6
                
        # Penalize common breach patterns via fast substring subset matching
        breach_applied = False
        for i in range(len(password_lower)):
            for j in range(i + 4, len(password_lower) + 1):
                sub = password_lower[i:j]
                if sub in self.common_patterns:
                    if not breach_applied:
                        score -= 0.5
                        breach_applied = True
                
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
        target_len = random.randint(14, 20)
        current = random.choice(starts) if starts else "Ab"
        res = current
        
        while len(res) < target_len:
            gram = res[-2:]
            if gram in chain and chain[gram]:
                res += secrets.choice(chain[gram])
            else:
                # Add random valid char if chain breaks
                res += secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%")

        # --- Chunk Jumbling ---
        # Split into chunks of size 4 to 6
        chunk_size = max(4, target_len // 3)
        chunks = [res[i:i+chunk_size] for i in range(0, len(res), chunk_size)]
        random.shuffle(chunks)
        res = "".join(chunks)

        # --- Leetspeak Substitution ---
        leetspeak_map = {
            'a': '4', 'A': '4',
            'e': '3', 'E': '3',
            'i': '1', 'I': '1',
            'o': '0', 'O': '0',
            's': '5', 'S': '5',
            't': '7', 'T': '7',
            'b': '8', 'B': '8',
            'g': '9', 'G': '9'
        }
        
        final_res = []
        for char in res:
            # 40% chance of replacing eligible characters
            if char in leetspeak_map and random.random() < 0.4:
                final_res.append(leetspeak_map[char])
            else:
                final_res.append(char)
        res = "".join(final_res)

        # To ensure it doesn't exactly match an old one
        if res in user_passwords:
            res += secrets.choice("!@#$%^&*0123456789")
            
        # Ensure at least one special character is present for baseline metric safety
        if not any(not c.isalnum() for c in res):
            res += secrets.choice("!@#$%^&*")
            
        return res

ml_engine = MLEngine()
