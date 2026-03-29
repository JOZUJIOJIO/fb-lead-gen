"""Abstract base class for platform adapters."""

from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    """All platform adapters (Facebook, Twitter, Instagram, ...) must implement this interface."""

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the browser / session. Must be called before any other method."""
        ...

    @abstractmethod
    async def search_people(
        self,
        keywords: str,
        region: str = "",
        industry: str = "",
    ) -> list[dict]:
        """Search for people on the platform.

        Returns:
            list of dicts, each containing:
                - platform_user_id: str
                - name: str
                - profile_url: str
                - snippet: str (short description / bio preview)
        """
        ...

    @abstractmethod
    async def get_profile(self, profile_url: str) -> dict:
        """Fetch full profile data for a given user.

        Returns:
            dict containing: name, bio, work, education, location,
            recent_posts (list[str]), raw_html (str), and any other
            platform-specific fields.
        """
        ...

    @abstractmethod
    async def send_message(self, profile_url: str, message: str) -> bool:
        """Send a direct message to the user.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up browser / session resources."""
        ...
