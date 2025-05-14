import requests
from ..config import CODEWARS_API_BASE, logger


def get_user_profile(username):
    """Get user profile from Codewars API."""
    try:
        response = requests.get(f"{CODEWARS_API_BASE}{username}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        return None


def get_completed_challenges(username):
    """Get completed challenges from Codewars API."""
    try:
        challenges = []
        page = 0

        while True:
            response = requests.get(
                f"{CODEWARS_API_BASE}{username}/code-challenges/completed?page={page}"
            )
            if response.status_code != 200:
                break

            data = response.json()
            if not data["data"]:
                break

            challenges.extend(data["data"])
            page += 1

            # Limit to last 100 challenges for performance
            if len(challenges) >= 100:
                challenges = challenges[:100]
                break

        return challenges
    except Exception as e:
        logger.error(f"Error fetching completed challenges: {e}")
        return []
