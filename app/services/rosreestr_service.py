class RosreestrService:
    def enrich(self, cadastral_number: str = None) -> dict:
        return {
            "cadastral_number": cadastral_number,
            "status": "mock",
            "message": "TODO: integrate with Rosreestr",
        }
