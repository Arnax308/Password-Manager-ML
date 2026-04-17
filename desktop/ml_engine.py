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

    # ── Structural HMM Constants ──
    STATES = ['U', 'L', 'D', 'S']  # Upper, Lower, Digit, Symbol
    DAMPING = 0.80  # 80% personal emission, 20% random teleportation

    # Full character pools per class (used for the "teleport" branch)
    _POOL = {
        'U': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        'L': 'abcdefghijklmnopqrstuvwxyz',
        'D': '0123456789',
        'S': '!@#$%^&*-_=+.,:;?~',
    }

    @staticmethod
    def _classify(ch: str) -> str:
        """Map a character to its structural class."""
        if ch.isupper():  return 'U'
        if ch.islower():  return 'L'
        if ch.isdigit():  return 'D'
        return 'S'

    def _build_hmm(self, passwords: list[str]):
        """Parse passwords into structural sequences and build HMM parameters.

        Returns (start_dist, trans_matrix, emissions):
          - start_dist:   dict[state] -> float   (initial state probabilities)
          - trans_matrix:  dict[state] -> dict[state] -> float  (row-normalised)
          - emissions:    dict[state] -> dict[char] -> int  (raw counts)
        """
        start_counts = defaultdict(int)
        trans_counts = {s: defaultdict(int) for s in self.STATES}
        emissions    = {s: defaultdict(int) for s in self.STATES}

        for pw in passwords:
            if len(pw) < 2:
                continue
            seq = [self._classify(c) for c in pw]

            # Starting state
            start_counts[seq[0]] += 1

            # Transitions & emissions
            for i, (cls, ch) in enumerate(zip(seq, pw)):
                emissions[cls][ch] += 1
                if i < len(seq) - 1:
                    trans_counts[cls][seq[i + 1]] += 1

        # Normalise start distribution (add-1 smoothing)
        total_start = sum(start_counts.values()) + len(self.STATES)
        start_dist = {s: (start_counts[s] + 1) / total_start for s in self.STATES}

        # Normalise transition rows (add-1 smoothing)
        trans_matrix = {}
        for s in self.STATES:
            row_total = sum(trans_counts[s].values()) + len(self.STATES)
            trans_matrix[s] = {t: (trans_counts[s][t] + 1) / row_total for t in self.STATES}

        return start_dist, trans_matrix, emissions

    def _weighted_pick(self, dist: dict) -> str:
        """Pick a key from {key: probability} using weighted random selection."""
        keys = list(dist.keys())
        weights = [dist[k] for k in keys]
        return random.choices(keys, weights=weights, k=1)[0]

    def _emit_char(self, state: str, emissions: dict) -> str:
        """Emit a character for the given state using 80/20 damping.

        80% chance: pick proportionally from the user's observed characters.
        20% chance: pick uniformly from the full character pool (teleport).
        """
        if random.random() < self.DAMPING and emissions[state]:
            # Personal branch — weighted by user frequency
            return self._weighted_pick(emissions[state])
        else:
            # Teleport branch — uniform random from all chars in this class
            return secrets.choice(self._POOL[state])

    def generate_personalized_password(self, user_passwords: list[str]) -> str:
        """
        Structural HMM generator with PageRank-style damping.

        Learns the user's password *rhythm* (transitions between character classes)
        and character preferences, then generates a new password that feels personal
        without regurgitating existing ones.
        """
        if not user_passwords or len(user_passwords) < 3:
            # Fallback: fully random if vault is too sparse
            pool = self._POOL['U'] + self._POOL['L'] + self._POOL['D'] + self._POOL['S']
            return "".join(secrets.choice(pool) for _ in range(16))

        start_dist, trans_matrix, emissions = self._build_hmm(user_passwords)

        # Derive target length from user's password length distribution
        lengths = [len(p) for p in user_passwords if len(p) >= 4]
        avg_len = sum(lengths) / len(lengths) if lengths else 14
        target_len = max(14, min(24, int(avg_len + random.gauss(0, 2))))

        # Retry loop: generate, validate, retry if too weak (max 20 attempts)
        pw_set = set(user_passwords)
        best_candidate = None
        best_score = -1.0

        for _ in range(20):
            # 1. Pick starting state
            state = self._weighted_pick(start_dist)
            chars = []

            # 2. Walk the HMM
            for _ in range(target_len):
                chars.append(self._emit_char(state, emissions))
                state = self._weighted_pick(trans_matrix[state])

            candidate = "".join(chars)

            # 3. Reject exact duplicates
            if candidate in pw_set:
                continue

            # 4. Ensure all four character classes are present
            classes_present = set(self._classify(c) for c in candidate)
            if len(classes_present) < 4:
                # Inject one random char from each missing class
                for cls in self.STATES:
                    if cls not in classes_present:
                        pos = secrets.randbelow(len(candidate))
                        candidate = candidate[:pos] + secrets.choice(self._POOL[cls]) + candidate[pos + 1:]

            # 5. Score and keep the best
            score, _ = self.score_password(candidate, [])
            if score > best_score:
                best_score = score
                best_candidate = candidate

            # Accept immediately if score is strong enough
            if score >= 0.6:
                return candidate

        return best_candidate or "".join(secrets.choice(
            self._POOL['U'] + self._POOL['L'] + self._POOL['D'] + self._POOL['S']
        ) for _ in range(16))

ml_engine = MLEngine()
